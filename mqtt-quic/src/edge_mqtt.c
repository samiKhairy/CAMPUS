#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <time.h>
#include <unistd.h>
#include <pthread.h>
#include <nng/nng.h>
#include <nng/mqtt/mqtt_client.h>
#include <nng/mqtt/mqtt_quic.h>
#include "cJSON.h"

#define MAX_DEVICES  64
#define MAX_RECORDS  50000

typedef struct {
    uint64_t send_ts_ns;
    uint64_t recv_ts_ns;
    double   latency_ms;
} Record;

typedef struct {
    char     device_id[64];
    Record  *records;
    int      count;
    int      capacity;
    pthread_mutex_t mu;
} DeviceStats;

static volatile int  running = 1;
static nng_socket    g_sock;
static DeviceStats   g_stats[MAX_DEVICES];
static int           g_n_devices = 0;
static nng_aio      *g_recv_aio;
/* VERBOSE=1 enables per-message stdout logging; off by default to keep sweep logs small. */
static int           g_verbose = 0;
static int           g_e2e = 0;
static char         *g_payload_data = NULL;

static void sig_handler(int sig) { (void)sig; running = 0; }

static uint64_t mono_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static DeviceStats *find_stats(const char *device_id) {
    for (int i = 0; i < g_n_devices; i++) {
        if (strcmp(g_stats[i].device_id, device_id) == 0)
            return &g_stats[i];
    }
    return NULL;
}

static void process_msg(nng_msg *msg, uint64_t recv_ns) {
    uint8_t   type    = nng_mqtt_msg_get_packet_type(msg);

    if (type == NNG_MQTT_PUBLISH) {
        uint32_t  payload_len;
        uint8_t  *payload  = nng_mqtt_msg_get_publish_payload(msg, &payload_len);
        char     *json_str = strndup((char *)payload, payload_len);

        cJSON *root = cJSON_Parse(json_str);
        free(json_str);

        if (root) {
            cJSON *dev_item = cJSON_GetObjectItem(root, "device_id");
            cJSON *ts_item  = cJSON_GetObjectItem(root, "ts_edge_ns");

            if (dev_item && ts_item) {
                const char *dev_id     = dev_item->valuestring;
                uint64_t    send_ts_ns = (uint64_t)ts_item->valuedouble;
                double      rtt_ms     = (double)(recv_ns - send_ts_ns) / 1e6;

                DeviceStats *ds = find_stats(dev_id);
                if (ds && ds->count < ds->capacity) {
                    if (g_e2e) {
                        if (strcmp(dev_id, g_stats[0].device_id) == 0) {
                            // device-1 is the uplink trigger source. Forward the update to targets.
                            cJSON *cmd = cJSON_CreateObject();
                            cJSON_AddStringToObject(cmd, "device_id", "");
                            cJSON_AddStringToObject(cmd, "payload",   g_payload_data);
                            cJSON_AddNumberToObject(cmd, "ts_edge_ns", (double)send_ts_ns); // carry the original T0
                            char *cmd_str = cJSON_PrintUnformatted(cmd);
                            cJSON_Delete(cmd);

                            for (int i = 1; i < g_n_devices; i++) {
                                char topic[128];
                                snprintf(topic, sizeof(topic), "campus/cmd/%s", g_stats[i].device_id);

                                nng_msg *pub_msg;
                                nng_mqtt_msg_alloc(&pub_msg, 0);
                                nng_mqtt_msg_set_packet_type(pub_msg,     NNG_MQTT_PUBLISH);
                                nng_mqtt_msg_set_publish_topic(pub_msg,   topic);
                                nng_mqtt_msg_set_publish_payload(pub_msg, (uint8_t *)cmd_str, strlen(cmd_str));
                                nng_mqtt_msg_set_publish_qos(pub_msg,     1);
                                nng_sendmsg(g_sock, pub_msg, NNG_FLAG_NONBLOCK);
                            }
                            free(cmd_str);
                        } else {
                            // Target device: compute E2E latency = RTT / 2
                            pthread_mutex_lock(&ds->mu);
                            ds->records[ds->count].send_ts_ns = send_ts_ns;
                            ds->records[ds->count].recv_ts_ns = recv_ns;
                            ds->records[ds->count].latency_ms = rtt_ms / 2.0;
                            ds->count++;
                            pthread_mutex_unlock(&ds->mu);
                            if (g_verbose)
                                printf("[EDGE] E2E Ack from %s -> E2E=%.2f ms\n", dev_id, rtt_ms / 2.0);
                        }
                    } else {
                        pthread_mutex_lock(&ds->mu);
                        ds->records[ds->count].send_ts_ns = send_ts_ns;
                        ds->records[ds->count].recv_ts_ns = recv_ns;
                        ds->records[ds->count].latency_ms = rtt_ms;
                        ds->count++;
                        pthread_mutex_unlock(&ds->mu);
                        if (g_verbose)
                            printf("[EDGE] Ack from %s -> RTT=%.2f ms\n", dev_id, rtt_ms);
                    }
                }
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

    uint64_t  recv_ns = mono_ns();
    nng_msg  *msg     = nng_aio_get_msg(aio);

    process_msg(msg, recv_ns);

    nng_msg_free(msg);
    nng_recv_aio(g_sock, aio);
}

static int quic_connect_cb(void *rmsg, void *arg) {
    (void)rmsg;
    (void)arg;
    printf("[EDGE] [DEBUG] QUIC Connected callback triggered\n");
    return 0;
}

static int quic_disconnect_cb(void *rmsg, void *arg) {
    (void)rmsg;
    (void)arg;
    printf("[EDGE] [DEBUG] QUIC Disconnected callback triggered\n");
    return 0;
}

static int quic_recv_cb(void *rmsg, void *arg) {
    (void)arg;
    uint64_t recv_ns = mono_ns();
    nng_msg *msg = rmsg;

    process_msg(msg, recv_ns);

    return 0;
}

static int cmp_double(const void *a, const void *b) {
    double x = *(double *)a, y = *(double *)b;
    return (x > y) - (x < y);
}

int main(void) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    signal(SIGTERM, sig_handler);
    signal(SIGINT,  sig_handler);

    const char *broker_url    = getenv("MQTT_BROKER_URL");
    const char *devices_env   = getenv("TARGET_DEVICES");
    int         payload_bytes = atoi(getenv("PAYLOAD_BYTES")   ? getenv("PAYLOAD_BYTES")   : "100");
    double      interval_sec  = atof(getenv("INTERVAL_SEC")    ? getenv("INTERVAL_SEC")    : "0.1");
    double      run_duration  = atof(getenv("RUN_DURATION")    ? getenv("RUN_DURATION")    : "30.0");
    double      start_delay   = atof(getenv("START_DELAY_SEC") ? getenv("START_DELAY_SEC") : "5.0");
    const char *output_csv    = getenv("OUTPUT_CSV");
    g_verbose = (getenv("VERBOSE") && atoi(getenv("VERBOSE")) == 1);
    g_e2e = (getenv("E2E_MODE") && atoi(getenv("E2E_MODE")) == 1);

    if (start_delay > 0) {
        printf("[EDGE] Sleeping %.0fs for network setup...\n", start_delay);
        usleep((useconds_t)(start_delay * 1e6));
    }

    if (!broker_url)  broker_url  = "mqtt-tcp://localhost:1883";
    if (!devices_env) devices_env = "device-1";
    if (!output_csv)  output_csv  = "/app/results/out.csv";

    char dev_buf[512];
    strncpy(dev_buf, devices_env, sizeof(dev_buf) - 1);
    char *device_ids[MAX_DEVICES];

    if (atoi(dev_buf) > 0) {
        int n = atoi(dev_buf);
        g_n_devices = n;
        for (int i = 0; i < n; i++) {
            device_ids[i] = malloc(32);
            snprintf(device_ids[i], 32, "device-%d", i + 1);
        }
    } else {
        char *tok = strtok(dev_buf, ",");
        while (tok && g_n_devices < MAX_DEVICES) {
            device_ids[g_n_devices] = strdup(tok);
            tok = strtok(NULL, ",");
            g_n_devices++;
        }
    }

    for (int i = 0; i < g_n_devices; i++) {
        strncpy(g_stats[i].device_id, device_ids[i], 63);
        g_stats[i].capacity = MAX_RECORDS;
        g_stats[i].count    = 0;
        g_stats[i].records  = calloc(MAX_RECORDS, sizeof(Record));
        pthread_mutex_init(&g_stats[i].mu, NULL);
    }

    int is_quic = (strncmp(broker_url, "mqtt-quic://", 12) == 0);

    if (is_quic) {
        printf("[EDGE] [DEBUG] Opening QUIC client socket for url: %s...\n", broker_url);
        int rv = nng_mqtt_quic_client_open(&g_sock, broker_url);
        if (rv != 0) {
            fprintf(stderr, "[EDGE] [ERROR] Failed to open QUIC client: %s\n", nng_strerror(rv));
            exit(1);
        }

        nng_mqtt_quic_set_connect_cb(&g_sock, quic_connect_cb, NULL);
        nng_mqtt_quic_set_disconnect_cb(&g_sock, quic_disconnect_cb, NULL);

        nng_msg *conn_msg;
        nng_mqtt_msg_alloc(&conn_msg, 0);
        nng_mqtt_msg_set_packet_type(conn_msg,           NNG_MQTT_CONNECT);
        nng_mqtt_msg_set_connect_proto_version(conn_msg, MQTT_PROTOCOL_VERSION_v311);
        nng_mqtt_msg_set_connect_keep_alive(conn_msg,    60);
        nng_mqtt_msg_set_connect_client_id(conn_msg,     "edge-node");
        nng_mqtt_msg_set_connect_clean_session(conn_msg, true);

        printf("[EDGE] [DEBUG] Sending QUIC connect message...\n");
        nng_sendmsg(g_sock, conn_msg, 0);
        printf("[EDGE] [DEBUG] QUIC client started successfully.\n");
    } else {
        printf("[EDGE] [DEBUG] Opening TCP client socket...\n");
        nng_mqtt_client_open(&g_sock);

        nng_msg *conn_msg;
        nng_mqtt_msg_alloc(&conn_msg, 0);
        nng_mqtt_msg_set_packet_type(conn_msg,           NNG_MQTT_CONNECT);
        nng_mqtt_msg_set_connect_proto_version(conn_msg, MQTT_PROTOCOL_VERSION_v311);
        nng_mqtt_msg_set_connect_keep_alive(conn_msg,    60);
        nng_mqtt_msg_set_connect_client_id(conn_msg,     "edge-node");
        nng_mqtt_msg_set_connect_clean_session(conn_msg, true);

        nng_dialer dialer;
        printf("[EDGE] [DEBUG] Creating dialer for url: %s...\n", broker_url);
        nng_dialer_create(&dialer, g_sock, broker_url);
        nng_dialer_set_ptr(dialer, NNG_OPT_MQTT_CONNMSG, conn_msg);
        printf("[EDGE] [DEBUG] Starting dialer...\n");
        nng_dialer_start(dialer, 0);
        printf("[EDGE] [DEBUG] Dialer started successfully.\n");
    }

    nng_mqtt_topic_qos sub_topics[1];
    memset(sub_topics, 0, sizeof(sub_topics));
    sub_topics[0].topic.buf    = (uint8_t *)"campus/ack/#";
    sub_topics[0].topic.length = strlen("campus/ack/#");
    sub_topics[0].qos          = 1;

    nng_msg *sub_msg;
    nng_mqtt_msg_alloc(&sub_msg, 0);
    nng_mqtt_msg_set_packet_type(sub_msg, NNG_MQTT_SUBSCRIBE);
    nng_mqtt_msg_set_subscribe_topics(sub_msg, sub_topics, 1);
    nng_sendmsg(g_sock, sub_msg, 0);

    if (is_quic) {
        nng_mqtt_quic_set_msg_recv_cb(&g_sock, quic_recv_cb, NULL);
    } else {
        nng_aio_alloc(&g_recv_aio, recv_cb, NULL);
        nng_recv_aio(g_sock, g_recv_aio);
    }



    printf("[EDGE] broker=%s devices=%d payload=%dB interval=%.3fs duration=%.0fs\n",
           broker_url, g_n_devices, payload_bytes, interval_sec, run_duration);

    g_payload_data = malloc(payload_bytes + 1);
    memset(g_payload_data, 'x', payload_bytes);
    g_payload_data[payload_bytes] = '\0';

    struct timespec start_ts;
    clock_gettime(CLOCK_MONOTONIC, &start_ts);

    while (running) {
        struct timespec now_ts;
        clock_gettime(CLOCK_MONOTONIC, &now_ts);
        double elapsed = (now_ts.tv_sec  - start_ts.tv_sec) +
                         (now_ts.tv_nsec - start_ts.tv_nsec) / 1e9;
        if (elapsed >= run_duration) break;

        if (g_e2e) {
            uint64_t ts_ns = mono_ns();
            cJSON *cmd = cJSON_CreateObject();
            cJSON_AddStringToObject(cmd, "device_id", device_ids[0]);
            cJSON_AddStringToObject(cmd, "payload",   g_payload_data);
            cJSON_AddNumberToObject(cmd, "ts_edge_ns", (double)ts_ns);
            char *cmd_str = cJSON_PrintUnformatted(cmd);
            cJSON_Delete(cmd);

            char topic[128];
            snprintf(topic, sizeof(topic), "campus/cmd/%s", device_ids[0]);

            nng_msg *pub_msg;
            nng_mqtt_msg_alloc(&pub_msg, 0);
            nng_mqtt_msg_set_packet_type(pub_msg,     NNG_MQTT_PUBLISH);
            nng_mqtt_msg_set_publish_topic(pub_msg,   topic);
            nng_mqtt_msg_set_publish_payload(pub_msg, (uint8_t *)cmd_str, strlen(cmd_str));
            nng_mqtt_msg_set_publish_qos(pub_msg,     1);
            nng_sendmsg(g_sock, pub_msg, NNG_FLAG_NONBLOCK);
            free(cmd_str);
        } else {
            for (int i = 0; i < g_n_devices; i++) {
                uint64_t ts_ns = mono_ns();

                cJSON *cmd = cJSON_CreateObject();
                cJSON_AddStringToObject(cmd, "device_id", device_ids[i]);
                cJSON_AddStringToObject(cmd, "payload",   g_payload_data);
                cJSON_AddNumberToObject(cmd, "ts_edge_ns", (double)ts_ns);
                char *cmd_str = cJSON_PrintUnformatted(cmd);
                cJSON_Delete(cmd);

                char topic[128];
                snprintf(topic, sizeof(topic), "campus/cmd/%s", device_ids[i]);

                nng_msg *pub_msg;
                nng_mqtt_msg_alloc(&pub_msg, 0);
                nng_mqtt_msg_set_packet_type(pub_msg,     NNG_MQTT_PUBLISH);
                nng_mqtt_msg_set_publish_topic(pub_msg,   topic);
                nng_mqtt_msg_set_publish_payload(pub_msg, (uint8_t *)cmd_str, strlen(cmd_str));
                nng_mqtt_msg_set_publish_qos(pub_msg,     1);
                nng_sendmsg(g_sock, pub_msg, NNG_FLAG_NONBLOCK);
                free(cmd_str);
            }
        }

        usleep((useconds_t)(interval_sec * 1e6));
    }

    running = 0;
    printf("[EDGE] Run complete. Waiting 1s for in-flight acks...\n");
    sleep(1);
    printf("[EDGE] [DEBUG] Closing socket...\n");
    nng_close(g_sock);
    printf("[EDGE] [DEBUG] Freeing AIO...\n");
    nng_aio_free(g_recv_aio);
    printf("[EDGE] [DEBUG] Freeing payload data...\n");
    free(g_payload_data);
    printf("[EDGE] [DEBUG] Opening CSV file: %s\n", output_csv);
    FILE *f = fopen(output_csv, "w");
    if (f) {
        fprintf(f, "device_id,send_ts_ns,recv_ts_ns,latency_ms\n");
        for (int i = 0; i < g_n_devices; i++) {
            for (int j = 0; j < g_stats[i].count; j++) {
                fprintf(f, "%s,%llu,%llu,%.4f\n",
                        g_stats[i].device_id,
                        (unsigned long long)g_stats[i].records[j].send_ts_ns,
                        (unsigned long long)g_stats[i].records[j].recv_ts_ns,
                        g_stats[i].records[j].latency_ms);
            }
        }
        fclose(f);
        printf("[EDGE] Results written to %s\n", output_csv);
    }

    printf("\n==================================================\n");
    for (int i = 0; i < g_n_devices; i++) {
        int n = g_stats[i].count;
        if (n == 0) { printf("%-15s | N/A\n", g_stats[i].device_id); continue; }
        double *lats = malloc(n * sizeof(double));
        for (int j = 0; j < n; j++) lats[j] = g_stats[i].records[j].latency_ms;
        qsort(lats, n, sizeof(double), cmp_double);
        double sum_l = 0;
        for (int j = 0; j < n; j++) sum_l += lats[j];
        printf("%-15s | min=%.2f avg=%.2f p95=%.2f count=%d\n",
               g_stats[i].device_id, lats[0], sum_l / n, lats[(int)(n * 0.95)], n);
        free(lats);
        free(g_stats[i].records);
        free(device_ids[i]);
        pthread_mutex_destroy(&g_stats[i].mu);
    }

    return 0;
}
