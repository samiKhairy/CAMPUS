# this file run the matrix experiment and does the following things :  
# 1. spin up the docker compose file for the given protocol 
# 2. create a temporary docker compose file for the given protocol 
# 3. apply the netem rule for the given protocol 
# 4. run the experiment for the given protocol 
# 5. clean up the docker compose file for the given protocol 

    

import argparse
import os
import subprocess
import sys
import time
import yaml

# Profiles definition
PROFILES = {
    "clean": None,
    "good_5g": {"delay": "20ms", "jitter": "1ms", "loss": "0.1%"},
    "degraded_5g": {"delay": "80ms", "jitter": "10ms", "loss": "1%"}
}

def check_docker():
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_container_id(compose_path, service_name):
    try:
        res = subprocess.run(
            ["docker", "compose", "-f", compose_path, "ps", "-a", "-q", service_name],
            capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError:
        return ""

def generate_compose(protocol, n, payload_bytes, interval_sec, run_duration, output_dir, filename, root_dir):
    compose = {"version": "3.8", "services": {}}
    devices_list = [f"device-{i}" for i in range(1, n + 1)]
    devices_str = ",".join(devices_list)
    
    # Path mappings (resolving relative paths to absolute to avoid docker mount issues)
    abs_output_dir = os.path.abspath(output_dir)
    abs_root_dir = os.path.abspath(root_dir)

    if protocol == "grpc":
        # 1. Edge Server
        compose["services"]["grpc-server"] = {
            "build": {
                "context": os.path.join(abs_root_dir, "gRPC"),
                "dockerfile": "docker/Dockerfile.server"
            },
            "ports": ["50051:50051"],
            "environment": [
                f"TARGET_DEVICES={devices_str}",
                f"PAYLOAD_BYTES={payload_bytes}",
                f"INTERVAL_SEC={interval_sec}",
                f"RUN_DURATION={run_duration}",
                "PYTHONUNBUFFERED=1",
                f"OUTPUT_CSV=/app/results/{filename}"
            ],
            "volumes": [f"{abs_output_dir}:/app/results"],
            "cap_add": ["NET_ADMIN"],
            "networks": ["campus-net"]
        }
        
        # 2. Devices
        for dev in devices_list:
            compose["services"][dev] = {
                "build": {
                    "context": os.path.join(abs_root_dir, "gRPC"),
                    "dockerfile": "docker/Dockerfile.client"
                },
                "command": ["python", "client.py", dev, "--server", "grpc-server:50051"],
                "environment": [
                    "GRPC_SERVER=grpc-server:50051",
                    "PYTHONUNBUFFERED=1"
                ],
                "depends_on": ["grpc-server"],
                "cap_add": ["NET_ADMIN"],
                "networks": ["campus-net"]
            }

    elif protocol == "zenoh":
        # 1. Zenoh Router
        compose["services"]["zenoh-router"] = {
            "image": "eclipse/zenoh:latest",
            "ports": ["7447:7447"],
            "networks": ["campus-net"]
        }
        
        # 2. Edge Node
        compose["services"]["edge-node"] = {
            "build": {
                "context": os.path.join(abs_root_dir, "zenoh"),
                "dockerfile": "docker/Dockerfile.edge"
            },
            "environment": [
                "ZENOH_ROUTER=tcp/zenoh-router:7447",
                f"TARGET_DEVICES={devices_str}",
                f"PAYLOAD_BYTES={payload_bytes}",
                f"INTERVAL_SEC={interval_sec}",
                f"RUN_DURATION={run_duration}",
                f"OUTPUT_CSV=/app/results/{filename}"
            ],
            "volumes": [f"{abs_output_dir}:/app/results"],
            "depends_on": ["zenoh-router"],
            "cap_add": ["NET_ADMIN"],
            "networks": ["campus-net"]
        }
        
        # 3. Devices
        for dev in devices_list:
            compose["services"][dev] = {
                "build": {
                    "context": os.path.join(abs_root_dir, "zenoh"),
                    "dockerfile": "docker/Dockerfile.device"
                },
                "command": ["python", "device_zenoh.py", dev, "--router", "tcp/zenoh-router:7447"],
                "depends_on": ["zenoh-router"],
                "cap_add": ["NET_ADMIN"],
                "networks": ["campus-net"]
            }

    elif protocol == "zenoh-quic":
        # 1. Zenoh Router (QUIC/UDP with TLS certs)
        compose["services"]["zenoh-router"] = {
            "image": "eclipse/zenoh:latest",
            "command": [
                "--listen", "quic/0.0.0.0:7447",
                "--no-multicast-scouting",
                "--cfg", "transport/link/tls/listen_certificate:\"/etc/zenoh/cert.pem\"",
                "--cfg", "transport/link/tls/listen_private_key:\"/etc/zenoh/key.pem\""
            ],
            "ports": ["7447:7447/udp"],
            "volumes": [f"{os.path.join(abs_root_dir, 'certs')}:/etc/zenoh"],
            "networks": ["campus-net"]
        }
        
        # 2. Edge Node
        compose["services"]["edge-node"] = {
            "build": {
                "context": os.path.join(abs_root_dir, "zenoh-quic"),
                "dockerfile": "docker/Dockerfile.edge"
            },
            "environment": [
                "ZENOH_ROUTER=quic/zenoh-router:7447",
                f"TARGET_DEVICES={devices_str}",
                f"PAYLOAD_BYTES={payload_bytes}",
                f"INTERVAL_SEC={interval_sec}",
                f"RUN_DURATION={run_duration}",
                f"OUTPUT_CSV=/app/results/{filename}"
            ],
            "volumes": [
                f"{abs_output_dir}:/app/results",
                f"{os.path.join(abs_root_dir, 'certs')}:/etc/zenoh"
            ],
            "depends_on": ["zenoh-router"],
            "cap_add": ["NET_ADMIN"],
            "networks": ["campus-net"]
        }
        
        # 3. Devices
        for dev in devices_list:
            compose["services"][dev] = {
                "build": {
                    "context": os.path.join(abs_root_dir, "zenoh-quic"),
                    "dockerfile": "docker/Dockerfile.device"
                },
                "command": ["python", "device_zenoh.py", dev, "--router", "quic/zenoh-router:7447"],
                "volumes": [f"{os.path.join(abs_root_dir, 'certs')}:/etc/zenoh"],
                "depends_on": ["zenoh-router"],
                "cap_add": ["NET_ADMIN"],
                "networks": ["campus-net"]
            }

    elif protocol == "mqtt":
        # 1. Mosquitto Broker
        compose["services"]["mqtt-broker"] = {
            "image": "eclipse-mosquitto:2",
            "ports": ["1883:1883"],
            "volumes": [f"{os.path.join(abs_root_dir, 'mqtt', 'mosquitto.conf')}:/mosquitto/config/mosquitto.conf"],
            "networks": ["campus-net"]
        }
        
        # 2. Edge Node
        compose["services"]["edge-node"] = {
            "build": {
                "context": os.path.join(abs_root_dir, "mqtt"),
                "dockerfile": "docker/Dockerfile.edge"
            },
            "environment": [
                "MQTT_BROKER=mqtt-broker:1883",
                f"TARGET_DEVICES={devices_str}",
                f"PAYLOAD_BYTES={payload_bytes}",
                f"INTERVAL_SEC={interval_sec}",
                f"RUN_DURATION={run_duration}",
                f"OUTPUT_CSV=/app/results/{filename}",
                "MQTT_QOS=1"
            ],
            "volumes": [f"{abs_output_dir}:/app/results"],
            "depends_on": ["mqtt-broker"],
            "cap_add": ["NET_ADMIN"],
            "networks": ["campus-net"]
        }
        
        # 3. Devices
        for dev in devices_list:
            compose["services"][dev] = {
                "build": {
                    "context": os.path.join(abs_root_dir, "mqtt"),
                    "dockerfile": "docker/Dockerfile.device"
                },
                "command": ["python", "device_mqtt.py", dev, "--broker", "mqtt-broker:1883"],
                "depends_on": ["mqtt-broker"],
                "cap_add": ["NET_ADMIN"],
                "networks": ["campus-net"]
            }

    elif protocol == "mqtt-tcp-c":
        # 1. NanoMQ Broker (TCP only for this variant)
        compose["services"]["mqtt-broker"] = {
            "image": "emqx/nanomq:latest-full",
            "ports": ["1883:1883"],
            "volumes": [
                f"{os.path.join(abs_root_dir, 'mqtt-quic', 'nanomq.conf')}:/etc/nanomq.conf",
                f"{os.path.join(abs_root_dir, 'mqtt-quic', 'nanomq.conf')}:/usr/local/nanomq/nanomq.conf",
                f"{os.path.join(abs_root_dir, 'certs')}:/etc/certs"
            ],
            "command": ["nanomq", "start", "--conf", "/etc/nanomq.conf"],
            "networks": ["campus-net"]
        }
        
        # 2. Edge Node (C client)
        compose["services"]["edge-node"] = {
            "build": {
                "context": os.path.join(abs_root_dir, "mqtt-quic"),
                "dockerfile": "docker/Dockerfile.edge"
            },
            "environment": [
                "MQTT_BROKER_URL=mqtt-tcp://mqtt-broker:1883",
                f"TARGET_DEVICES={devices_str}",
                f"PAYLOAD_BYTES={payload_bytes}",
                f"INTERVAL_SEC={interval_sec}",
                f"RUN_DURATION={run_duration}",
                f"OUTPUT_CSV=/app/results/{filename}"
            ],
            "volumes": [f"{abs_output_dir}:/app/results"],
            "depends_on": ["mqtt-broker"],
            "cap_add": ["NET_ADMIN"],
            "networks": ["campus-net"]
        }
        
        # 3. Devices (C client)
        for dev in devices_list:
            compose["services"][dev] = {
                "build": {
                    "context": os.path.join(abs_root_dir, "mqtt-quic"),
                    "dockerfile": "docker/Dockerfile.device"
                },
                "environment": [
                    f"DEVICE_ID={dev}",
                    "MQTT_BROKER_URL=mqtt-tcp://mqtt-broker:1883"
                ],
                "depends_on": ["mqtt-broker"],
                "cap_add": ["NET_ADMIN"],
                "networks": ["campus-net"]
            }

    elif protocol == "mqtt-quic":
        # 1. EMQX Broker - the only broker that supports accepting incoming MQTT-over-QUIC
        #    NanoMQ only supports QUIC for outbound bridging, not as a server listener.
        #    We use EMQX's built-in default self-signed certs; clients skip TLS verification.
        compose["services"]["mqtt-broker"] = {
            "image": "emqx/emqx:latest",
            "ports": ["1883:1883", "14567:14567/udp"],
            "environment": [
                "EMQX_LISTENERS__QUIC__DEFAULT__ENABLED=true",
                "EMQX_LISTENERS__QUIC__DEFAULT__BIND=0.0.0.0:14567",
                "EMQX_LISTENERS__QUIC__DEFAULT__ENABLE_AUTHN=false",
                "EMQX_ALLOW_ANONYMOUS=true",
                "EMQX_LOG__CONSOLE__LEVEL=warning"
            ],
            "networks": ["campus-net"],
            "healthcheck": {
                "test": ["CMD", "emqx", "ping"],
                "interval": "5s",
                "timeout": "5s",
                "retries": 10,
                "start_period": "30s"
            }
        }
        
        # 2. Edge Node (C client using NanoSDK with QUIC transport)
        compose["services"]["edge-node"] = {
            "build": {
                "context": os.path.join(abs_root_dir, "mqtt-quic"),
                "dockerfile": "docker/Dockerfile.edge"
            },
            "environment": [
                "MQTT_BROKER_URL=mqtt-quic://mqtt-broker:14567",
                f"TARGET_DEVICES={devices_str}",
                f"PAYLOAD_BYTES={payload_bytes}",
                f"INTERVAL_SEC={interval_sec}",
                f"RUN_DURATION={run_duration}",
                f"OUTPUT_CSV=/app/results/{filename}",
                "START_DELAY_SEC=2"
            ],
            "volumes": [f"{abs_output_dir}:/app/results"],
            "depends_on": {
                "mqtt-broker": {
                    "condition": "service_healthy"
                }
            },
            "cap_add": ["NET_ADMIN"],
            "networks": ["campus-net"]
        }
        
        # 3. Devices (C client using NanoSDK with QUIC transport)
        for dev in devices_list:
            compose["services"][dev] = {
                "build": {
                    "context": os.path.join(abs_root_dir, "mqtt-quic"),
                    "dockerfile": "docker/Dockerfile.device"
                },
                "environment": [
                    f"DEVICE_ID={dev}",
                    "MQTT_BROKER_URL=mqtt-quic://mqtt-broker:14567"
                ],
                "depends_on": {
                    "mqtt-broker": {
                        "condition": "service_healthy"
                    }
                },
                "cap_add": ["NET_ADMIN"],
                "networks": ["campus-net"]
            }

    compose["networks"] = {"campus-net": {"driver": "bridge"}}
    return compose

def apply_netem(container, impairment):
    if not impairment:
        return True
    
    delay = impairment["delay"]
    jitter = impairment["jitter"]
    loss = impairment["loss"]
    
    print(f"  -> Injecting netem in {container} (delay: {delay} ± {jitter}, loss: {loss})...")
    # First delete existing qdisc if any (ignore errors if none)
    subprocess.run(
        ["docker", "exec", container, "tc", "qdisc", "del", "dev", "eth0", "root"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    # Apply new netem rule
    res = subprocess.run([
        "docker", "exec", container, "tc", "qdisc", "add", "dev", "eth0", "root", "netem",
        "delay", delay, jitter, "distribution", "normal", "loss", loss
    ], capture_output=True, text=True)
    
    if res.returncode != 0:
        print(f"  [WARNING] Failed to apply netem to {container}: {res.stderr.strip()}")
        return False
    return True

def main():
    parser = argparse.ArgumentParser(description="Unified Experiment Matrix Runner")
    parser.add_argument("--protocols", default="grpc,zenoh,mqtt,zenoh-quic,mqtt-tcp-c,mqtt-quic", help="Comma-separated protocols")
    parser.add_argument("--profiles", default="clean,good_5g,degraded_5g", help="Comma-separated profiles")
    parser.add_argument("--devices", default="1,2,5,10", help="Comma-separated device counts N")
    parser.add_argument("--payloads", default="100,2000", help="Comma-separated payloads in bytes")
    parser.add_argument("--rates", default="5,10", help="Comma-separated rates in Hz")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds per run")
    parser.add_argument("--dry-run", action="store_true", help="Print plans without running")
    args = parser.parse_args()

    # Parse sweep dimensions
    protocols = [p.strip() for p in args.protocols.split(",") if p.strip()]
    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
    devices = [int(d.strip()) for d in args.devices.split(",") if d.strip()]
    payloads = [int(p.strip()) for p in args.payloads.split(",") if p.strip()]
    rates = [int(r.strip()) for r in args.rates.split(",") if r.strip()]

    print("==================================================")
    print(" UNIFIED EXPERIMENT MATRIX RUNNER")
    print("==================================================")
    print(f"Protocols    : {protocols}")
    print(f"Profiles     : {profiles}")
    print(f"Device Sweeps: {devices}")
    print(f"Payloads     : {payloads} bytes")
    print(f"Rates        : {rates} Hz")
    print(f"Run Duration : {args.duration} s")
    print("==================================================\n")

    if not args.dry_run and not check_docker():
        print("[ERROR] Docker daemon is not running or docker CLI not found!")
        print("Please start Docker Desktop on your system and try again.")
        sys.exit(1)

    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_compose_path = os.path.join(root_dir, "scripts", "temp-compose.yml")

    total_runs = len(protocols) * len(profiles) * len(devices) * len(payloads) * len(rates)
    run_idx = 0

    for protocol in protocols:
        for profile in profiles:
            for n in devices:
                for payload in payloads:
                    for rate in rates:
                        run_idx += 1
                        interval = 1.0 / rate
                        filename = f"N_{n}_pay_{payload}_rate_{rate}.csv"
                        output_dir = os.path.join(root_dir, "results", "matrix", protocol, profile)
                        
                        print(f"[{run_idx}/{total_runs}] Running {protocol.upper()} | {profile.upper()} | N={n} | Payload={payload}B | Rate={rate}Hz")
                        
                        if args.dry_run:
                            continue
                        
                        # Ensure output directory exists
                        os.makedirs(output_dir, exist_ok=True)
                        
                        # Generate compose dictionary
                        compose_dict = generate_compose(
                            protocol=protocol,
                            n=n,
                            payload_bytes=payload,
                            interval_sec=interval,
                            run_duration=args.duration,
                            output_dir=output_dir,
                            filename=filename,
                            root_dir=root_dir
                        )
                        
                        # Write compose file
                        with open(temp_compose_path, "w") as f:
                            yaml.safe_dump(compose_dict, f)
                            
                        # Preemptively clean up any lingering resources from a crashed previous run
                        subprocess.run(
                            ["docker", "compose", "-f", temp_compose_path, "down"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )

                        # Spin up services
                        print("  -> Spinning up docker services...")
                        res_up = subprocess.run(
                            ["docker", "compose", "-f", temp_compose_path, "up", "-d", "--build"],
                            capture_output=True, text=True
                        )
                        if res_up.returncode != 0:
                            print(f"  [ERROR] Failed to start services:\n{res_up.stderr}")
                            sys.exit(1)
                        
                        # Give containers a couple of seconds to boot up and initialize networks
                        time.sleep(3)
                        
                        # Identify containers to inject impairment
                        impairment = PROFILES[profile]
                        edge_service = "grpc-server" if protocol == "grpc" else "edge-node"
                        edge_container = get_container_id(temp_compose_path, edge_service)
                        
                        # Apply netem to edge node
                        if edge_container:
                            apply_netem(edge_container, impairment)
                        
                        # Apply netem to all device containers
                        for i in range(1, n + 1):
                            dev_service = f"device-{i}"
                            dev_container = get_container_id(temp_compose_path, dev_service)
                            if dev_container:
                                apply_netem(dev_container, impairment)
                        
                        # Wait for edge node to finish its run duration
                        print(f"  -> Experiment in progress (waiting {args.duration}s for edge-node)...")
                        if edge_container:
                            subprocess.run(
                                ["docker", "wait", edge_container],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                            )
                        else:
                            print("  [ERROR] Edge container not found! Sleeping instead...")
                            time.sleep(args.duration)
                        
                        # Print logs for debugging
                        print("  -> Printing logs for debugging...")
                        for service_name in compose_dict["services"].keys():
                            container_id = get_container_id(temp_compose_path, service_name)
                            if container_id:
                                print(f"\n========================================\n--- LOGS FOR {service_name} ---\n========================================")
                                logs_res = subprocess.run(["docker", "logs", container_id], capture_output=True, text=True)
                                print(logs_res.stdout)
                                print(logs_res.stderr)
                                print("========================================\n")
                        
                        # Clean up docker compose setup
                        print("  -> Shutting down and cleaning up containers...")
                        subprocess.run(
                            ["docker", "compose", "-f", temp_compose_path, "down"],
                            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                        
                        # Remove temporary compose file
                        if os.path.exists(temp_compose_path):
                            os.remove(temp_compose_path)
                            
                        print(f"  -> Run complete. Results saved in: {os.path.join(output_dir, filename)}\n")

if __name__ == "__main__":
    main()
