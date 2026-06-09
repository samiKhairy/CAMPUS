#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <time.h>
#include <unistd.h>
#include <nng/nng.h>
#include <nng/mqtt/mqtt_client.h>
#include <nng/mqtt/mqtt_quic.h>
#include "cJSON.h"

static volatile int running = 1;
static nng_socket   g_sock;
static const char  *g_device_id;
static char         g_ack_topic[128];
static nng_aio     *g_recv_aio;

static void sig_handler(int sig) { (void)sig; running = 0; }

static uint64_t mono_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static void process_msg(nng_msg *msg) {
    uint8_t  type = nng_mqtt_msg_get_packet_type(msg);

    if (type == NNG_MQTT_PUBLISH) {
        uint32_t  payload_len;
        uint8_t  *payload  = nng_mqtt_msg_get_publish_payload(msg, &payload_len);
        char     *json_str = strndup((char *)payload, payload_len);
        uint64_t  recv_ns  = mono_ns();

        cJSON *root = cJSON_Parse(json_str);
        free(json_str);

        if (root) {
            cJSON *ts_item = cJSON_GetObjectItem(root, "ts_edge_ns");
            if (ts_item) {
                uint64_t ts_edge_ns = (uint64_t)ts_item->valuedouble;

                cJSON *ack = cJSON_CreateObject();
                cJSON_AddStringToObject(ack, "device_id",    g_device_id);
                cJSON_AddStringToObject(ack, "status",       "OK");
                cJSON_AddNumberToObject(ack, "ts_edge_ns",   (double)ts_edge_ns);
                cJSON_AddNumberToObject(ack, "ts_device_ns", (double)recv_ns);
                char *ack_str = cJSON_PrintUnformatted(ack);
                cJSON_Delete(ack);

                nng_msg *pub;
                nng_mqtt_msg_alloc(&pub, 0);
                nng_mqtt_msg_set_packet_type(pub,     NNG_MQTT_PUBLISH);
                nng_mqtt_msg_set_publish_topic(pub,   g_ack_topic);
                nng_mqtt_msg_set_publish_payload(pub, (uint8_t *)ack_str, strlen(ack_str));
                nng_mqtt_msg_set_publish_qos(pub,     1);
                nng_sendmsg(g_sock, pub, NNG_FLAG_NONBLOCK);
                free(ack_str);
            }
            cJSON_Delete(root);
        }
    }
}

static void recv_cb(void *arg) {
    (void)arg;
    nng_aio *aio = g_recv_aio;
    if (nng_aio_result(aio) != 0) {
        if (running) nng_recv_aio(g_sock, aio);
        return;
    }

    nng_msg *msg  = nng_aio_get_msg(aio);

    process_msg(msg);

    nng_msg_free(msg);
    nng_recv_aio(g_sock, aio);
}

static int quic_connect_cb(void *rmsg, void *arg) {
    (void)rmsg;
    (void)arg;
    printf("[%s] [DEBUG] QUIC Connected callback triggered\n", g_device_id);
    return 0;
}

static int quic_disconnect_cb(void *rmsg, void *arg) {
    (void)rmsg;
    (void)arg;
    printf("[%s] [DEBUG] QUIC Disconnected callback triggered\n", g_device_id);
    return 0;
}

static int quic_recv_cb(void *rmsg, void *arg) {
    (void)arg;
    nng_msg *msg = rmsg;

    process_msg(msg);

    return 0;
}

int main(void) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    signal(SIGTERM, sig_handler);
    signal(SIGINT,  sig_handler);

    const char *device_id  = getenv("DEVICE_ID");
    const char *broker_url = getenv("MQTT_BROKER_URL");
    if (!device_id)  device_id  = "device-1";
    if (!broker_url) broker_url = "mqtt-tcp://localhost:1883";

    g_device_id = device_id;

    double start_delay = atof(getenv("START_DELAY_SEC") ? getenv("START_DELAY_SEC") : "10.0");
    if (start_delay > 0) {
        printf("[%s] Sleeping %.0fs for network setup...\n", device_id, start_delay);
        usleep((useconds_t)(start_delay * 1e6));
    }

    char cmd_topic[128];
    snprintf(cmd_topic,   sizeof(cmd_topic),   "campus/cmd/%s", device_id);
    snprintf(g_ack_topic, sizeof(g_ack_topic), "campus/ack/%s", device_id);

    int is_quic = (strncmp(broker_url, "mqtt-quic://", 12) == 0);

    if (is_quic) {
        printf("[%s] [DEBUG] Opening QUIC client socket for url: %s...\n", device_id, broker_url);
        int rv = nng_mqtt_quic_client_open(&g_sock, broker_url);
        if (rv != 0) {
            fprintf(stderr, "[%s] [ERROR] Failed to open QUIC client: %s\n", device_id, nng_strerror(rv));
            exit(1);
        }

        nng_mqtt_quic_set_connect_cb(&g_sock, quic_connect_cb, NULL);
        nng_mqtt_quic_set_disconnect_cb(&g_sock, quic_disconnect_cb, NULL);

        nng_msg *conn_msg;
        nng_mqtt_msg_alloc(&conn_msg, 0);
        nng_mqtt_msg_set_packet_type(conn_msg,           NNG_MQTT_CONNECT);
        nng_mqtt_msg_set_connect_proto_version(conn_msg, MQTT_PROTOCOL_VERSION_v311);
        nng_mqtt_msg_set_connect_keep_alive(conn_msg,    60);
        nng_mqtt_msg_set_connect_client_id(conn_msg,     device_id);
        nng_mqtt_msg_set_connect_clean_session(conn_msg, true);

        printf("[%s] [DEBUG] Sending QUIC connect message...\n", device_id);
        nng_sendmsg(g_sock, conn_msg, 0);
        printf("[%s] [DEBUG] QUIC client started successfully.\n", device_id);
    } else {
        printf("[%s] [DEBUG] Opening TCP client socket...\n", device_id);
        nng_mqtt_client_open(&g_sock);

        nng_msg *conn_msg;
        nng_mqtt_msg_alloc(&conn_msg, 0);
        nng_mqtt_msg_set_packet_type(conn_msg,           NNG_MQTT_CONNECT);
        nng_mqtt_msg_set_connect_proto_version(conn_msg, MQTT_PROTOCOL_VERSION_v311);
        nng_mqtt_msg_set_connect_keep_alive(conn_msg,    60);
        nng_mqtt_msg_set_connect_client_id(conn_msg,     device_id);
        nng_mqtt_msg_set_connect_clean_session(conn_msg, true);

        nng_dialer dialer;
        printf("[%s] [DEBUG] Creating dialer for url: %s...\n", device_id, broker_url);
        nng_dialer_create(&dialer, g_sock, broker_url);
        nng_dialer_set_ptr(dialer, NNG_OPT_MQTT_CONNMSG, conn_msg);
        printf("[%s] [DEBUG] Starting dialer...\n", device_id);
        nng_dialer_start(dialer, 0);
        printf("[%s] [DEBUG] Dialer started successfully.\n", device_id);
    }

    nng_mqtt_topic_qos sub_topics[1];
    memset(sub_topics, 0, sizeof(sub_topics));
    sub_topics[0].topic.buf    = (uint8_t *)cmd_topic;
    sub_topics[0].topic.length = strlen(cmd_topic);
    sub_topics[0].qos          = 1;

    nng_msg *sub_msg;
    nng_mqtt_msg_alloc(&sub_msg, 0);
    nng_mqtt_msg_set_packet_type(sub_msg, NNG_MQTT_SUBSCRIBE);
    nng_mqtt_msg_set_subscribe_topics(sub_msg, sub_topics, 1);
    nng_sendmsg(g_sock, sub_msg, 0);

    printf("[%s] Connected to %s, subscribed to %s\n", device_id, broker_url, cmd_topic);

    if (is_quic) {
        nng_mqtt_quic_set_msg_recv_cb(&g_sock, quic_recv_cb, NULL);
    } else {
        nng_aio_alloc(&g_recv_aio, recv_cb, NULL);
        nng_recv_aio(g_sock, g_recv_aio);
    }

    while (running) usleep(500000);

    printf("[%s] Shutting down.\n", device_id);
    nng_close(g_sock);
    nng_aio_free(g_recv_aio);
    return 0;
}
