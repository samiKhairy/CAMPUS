"""
DDS Device Simulator — CAMPUS Protocol Benchmark

Eclipse Cyclone DDS implementation of a simulated vehicle/device.
Subscribes to commands from the edge on topic 'campus_cmd_{device_id}',
immediately publishes an ack on topic 'campus_ack_{device_id}' echoing
the edge's send timestamp so the edge can compute RTT.

No broker, no router — DDS SPDP discovers the edge participant directly
over the Docker bridge network.
"""

import argparse
import os
import sys
import time
import threading

from dataclasses import dataclass
from cyclonedds.domain import DomainParticipant
from cyclonedds.core import Qos, Policy
from cyclonedds.pub import DataWriter
from cyclonedds.sub import DataReader
from cyclonedds.topic import Topic
from cyclonedds.idl import IdlStruct
from cyclonedds.util import duration

# ---------------------------------------------------------------------------
# IDL data types — must match edge_dds.py exactly
# ---------------------------------------------------------------------------

@dataclass
class CampusCommand(IdlStruct, typename="campus::Command"):
    device_id: str
    payload: str
    ts_edge_ns: int


@dataclass
class CampusAck(IdlStruct, typename="campus::Ack"):
    device_id: str
    status: str
    ts_edge_ns: int
    ts_device_ns: int


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VERBOSE = os.getenv("VERBOSE", "0") == "1"


def parse_args():
    parser = argparse.ArgumentParser(description="DDS Device Simulator (Cyclone DDS)")
    parser.add_argument(
        "device_id",
        nargs="?",
        default=os.getenv("DEVICE_ID", "device-1"),
        help="Device identifier",
    )
    return parser.parse_args()


args = parse_args()
device_id = args.device_id

# ---------------------------------------------------------------------------
# DDS setup
# ---------------------------------------------------------------------------

dp = DomainParticipant()

qos = Qos(
    Policy.Reliability.Reliable(max_blocking_time=duration(seconds=1)),
    Policy.History.KeepLast(100),
)

# Command topic: edge publishes, this device subscribes
cmd_topic_name = f"campus_cmd_{device_id.replace('-', '_')}"
cmd_topic = Topic(dp, cmd_topic_name, CampusCommand, qos=qos)
cmd_reader = DataReader(dp, cmd_topic, qos=qos)

# Ack topic: this device publishes, edge subscribes
ack_topic_name = f"campus_ack_{device_id.replace('-', '_')}"
ack_topic = Topic(dp, ack_topic_name, CampusAck, qos=qos)
ack_writer = DataWriter(dp, ack_topic, qos=qos)

print(f"[{device_id}] DDS device started. Listening on topic '{cmd_topic_name}', acks on '{ack_topic_name}'")

# ---------------------------------------------------------------------------
# Main loop — poll for commands and send acks
# ---------------------------------------------------------------------------

try:
    while True:
        samples = cmd_reader.take()
        for sample in samples:
            ts_device_ns = time.monotonic_ns()

            if VERBOSE:
                print(f"[{device_id}] Received command ({len(sample.payload)} bytes)")

            ack = CampusAck(
                device_id=device_id,
                status="OK",
                ts_edge_ns=sample.ts_edge_ns,
                ts_device_ns=ts_device_ns,
            )
            ack_writer.write(ack)

        time.sleep(0.002)  # 2ms poll interval

except KeyboardInterrupt:
    print(f"\n[{device_id}] Exiting...")
