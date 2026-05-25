import argparse
import os
import sys
import time
import json
import zenoh


# this function is used to parse the arguments passed to the script 
def parse_args():
    # parser is used to parse the arguments passed to the script 
    # argparse itself is a module which is used to parse the arguments passed to the script 
    # argumentparser is a object which is used to parse the arguments passed to the script   
    # description is used to provide a description of the script 
    parser = argparse.ArgumentParser(description="Zenoh Device Simulator")
    # device_id is the id of the device 
    # nargs="?" is used to specify that the device_id is optional 
    # default=os.getenv("DEVICE_ID", "device-1") is used to specify the default value of the device_id 
    # help is used to provide a description of the device_id 
    parser.add_argument(
        "device_id",
        nargs="?",
        default=os.getenv("DEVICE_ID", "device-1"),
        help="Device Identifier (default: DEVICE_ID env var or 'device-1')"
    )
    # --router is used to specify the address of the router 
    # default=os.getenv("ZENOH_ROUTER", "tcp/localhost:7447") is used to specify the default value of the router 
    # help is used to provide a description of the router 
    parser.add_argument(
        "--router",
        default=os.getenv("ZENOH_ROUTER", "tcp/localhost:7447"),
        help="Zenoh router endpoint (default: ZENOH_ROUTER env var or 'tcp/localhost:7447')"
    )
    return parser.parse_args()


# parse the arguments and get the device id and the router address
args = parse_args()
device_id = args.device_id
ZENOH_ROUTER = args.router

# zenoh configuration and session creation which connects to the router
conf = zenoh.Config()
# insert_json5 is used to insert the configuration of the zenoh 
# connect/endpoints is used to specify the address of the router 
# session = zenoh.open(conf) is used to open the session 
conf.insert_json5("connect/endpoints", f'["{ZENOH_ROUTER}"]')
session = zenoh.open(conf)

# defines the command key and ack key and publisher which are used to send and receive messages    
# cmd_key is the key which is used to receive commands from the edge node 
# ack_key is the key which is used to send acks to the edge node
cmd_key = f"campus/cmd/{device_id}"
ack_key = f"campus/ack/{device_id}"

# session.declare_publisher is used to declare a publisher which is used to send messages to the router meaning that router will know that this device is online and will send messages to this device through this key  .
# basically it is like creating a channel for the device to send messages
pub_ack = session.declare_publisher(ack_key)

# callback function for command handling 
def on_command(sample):

    # sample.payload.to_string() is used to convert the payload to a string
    # json.loads() is used to convert the string to a dictionary
    # so finally data is a dictionary which is actually the payload of the command from the edge node 
    data = json.loads(sample.payload.to_string())

    # ts_edge_ns is the timestamp of the command from the edge node 
    # ts_device_ns is the timestamp of the command from the device 
    ts_edge_ns = data["ts_edge_ns"]
    ts_device_ns = time.time_ns()

    # print the command
    print(f"[{device_id}] Received command: {data['payload']}")

    # create ack dictionary 
    # status is OK which means the command was received successfully 
    # ts_edge_ns is the timestamp of the command from the edge node 
    # ts_device_ns is the timestamp of the command from the device 
    ack = {
        "device_id": device_id,
        "status": "OK",
        "ts_edge_ns": ts_edge_ns,
        "ts_device_ns": ts_device_ns,
    }
    # pub_ack.put(json.dumps(ack)) is used to send the ack to the router 
    # json.dumps() is used to convert the dictionary to a string 
    pub_ack.put(json.dumps(ack))

# session.declare_subscriber is used to declare a subscriber which is used to receive messages from the router meaning that router will know that this device is online and will send messages to this device through this key  .
# basically it is like creating a channel for the device to receive messages
sub = session.declare_subscriber(cmd_key, on_command)
print(f"[{device_id}] Subscribed to {cmd_key}, acks to {ack_key}")
# loop forever to keep subscriber threads alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print(f"\n[{device_id}] Exiting...")
    session.close()