import os
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def parse_filename(filename):
    # Matches N_1_pay_100_rate_10.csv
    match = re.match(r"N_(\d+)_pay_(\d+)_rate_(\d+)\.csv", filename)
    if match:
        return {
            "devices": int(match.group(1)),
            "payload": int(match.group(2)),
            "rate": int(match.group(3))
        }
    return None

def process_results(root_dir, output_base, e2e=False):
    data_list = []
    matrix_dir = os.path.join(root_dir, output_base)
    
    if not os.path.exists(matrix_dir):
        print(f"[ERROR] Directory does not exist: {matrix_dir}")
        return None

    # Recurse through matrix directory
    for protocol in os.listdir(matrix_dir):
        protocol_path = os.path.join(matrix_dir, protocol)
        if not os.path.isdir(protocol_path):
            continue
            
        for profile in os.listdir(protocol_path):
            profile_path = os.path.join(protocol_path, profile)
            if not os.path.isdir(profile_path):
                continue
                
            for file in os.listdir(profile_path):
                if not file.endswith(".csv"):
                    continue
                    
                params = parse_filename(file)
                if not params:
                    continue
                    
                file_path = os.path.join(profile_path, file)
                try:
                    df = pd.read_csv(file_path)
                    if df.empty:
                        continue
                        
                    latencies = df["latency_ms"].values
                    # Sort to calculate percentiles
                    sorted_lats = np.sort(latencies)
                    n_rec = len(sorted_lats)
                    
                    p50 = np.percentile(sorted_lats, 50)
                    p95 = np.percentile(sorted_lats, 95)
                    p99 = np.percentile(sorted_lats, 99)
                    mean_lat = np.mean(sorted_lats)
                    min_lat = np.min(sorted_lats)
                    max_lat = np.max(sorted_lats)
                    
                    # Estimate packet loss
                    # We assume duration is 30s by default (the runner default)
                    # Let's try to infer duration or use a baseline.
                    # We can estimate it from the timestamp difference in the CSV:
                    duration_s = 30.0
                    if len(df) > 1:
                        # Convert send_ts_ns difference to seconds
                        ts_diff = (df["send_ts_ns"].max() - df["send_ts_ns"].min()) / 1e9
                        if ts_diff > 1.0:
                            duration_s = ts_diff + (1.0 / params["rate"]) # round up to full interval
                    
                    # If the inferred duration collapses due to connection/discovery failure,
                    # fall back to the intended 30s run length.
                    if duration_s < 28.0:
                        duration_s = 30.0
                    
                    if e2e:
                        expected_packets = max(0, params["devices"] - 1) * params["rate"] * duration_s
                    else:
                        expected_packets = params["devices"] * params["rate"] * duration_s
                    lost_packets = max(0, expected_packets - n_rec)
                    loss_pct = (lost_packets / expected_packets) * 100 if expected_packets > 0 else 0.0
                    
                    # Throughput in Kbps
                    throughput_kbps = (n_rec * params["payload"] * 8) / (duration_s * 1000) if duration_s > 0 else 0.0
                    
                    entry = {
                        "protocol": protocol,
                        "profile": profile,
                        "devices": params["devices"],
                        "payload": params["payload"],
                        "rate": params["rate"],
                        "acks_received": n_rec,
                        "expected": expected_packets,
                        "loss_pct": loss_pct,
                        "throughput_kbps": throughput_kbps,
                        "p50": p50,
                        "p95": p95,
                        "p99": p99,
                        "mean": mean_lat,
                        "min": min_lat,
                        "max": max_lat,
                        "raw_data": sorted_lats
                    }
                    data_list.append(entry)
                    
                except Exception as e:
                    print(f"[WARNING] Failed to parse {file_path}: {e}")
                    
    return data_list

def generate_plots(data_list, output_dir):
    df = pd.DataFrame([{k: v for k, v in item.items() if k != "raw_data"} for item in data_list])
    if df.empty:
        return
    
    os.makedirs(output_dir, exist_ok=True)
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

    # Plot 1: Latency p95 vs Device Count N (for payload=100, rate=10, profile=good_5g)
    plt.figure(figsize=(8, 5))
    subset1 = df[(df["payload"] == 100) & (df["rate"] == 10) & (df["profile"] == "good_5g")]
    
    for protocol in subset1["protocol"].unique():
        proto_data = subset1[subset1["protocol"] == protocol].sort_values("devices")
        plt.plot(proto_data["devices"], proto_data["p95"], marker='o', linewidth=2, label=protocol.upper())
        
    plt.title("p95 Latency vs. Device Count (Normal 5G, 100B, 10Hz)", fontsize=12, fontweight='bold')
    plt.xlabel("Number of Targeted Devices (N)", fontsize=10)
    plt.ylabel("p95 Round-Trip Latency (ms)", fontsize=10)
    plt.xticks(subset1["devices"].unique())
    plt.legend(frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "latency_vs_N.png"), dpi=150)
    plt.close()

    # Plot 2: Latency CDF (for N=1 or 2, payload=100, rate=10, profile=good_5g)
    plt.figure(figsize=(8, 5))
    target_configs = [item for item in data_list if item["payload"] == 100 and item["rate"] == 10 and item["profile"] == "good_5g"]
    # We want a representative N, say N=2 or N=1 (what is available)
    if target_configs:
        available_Ns = set(item["devices"] for item in target_configs)
        chosen_N = min(available_Ns)
        
        for item in target_configs:
            if item["devices"] == chosen_N:
                raw_lats = item["raw_data"]
                # Cumulative probability
                y = np.arange(1, len(raw_lats) + 1) / len(raw_lats)
                plt.plot(raw_lats, y, label=item["protocol"].upper(), linewidth=2)
                
        plt.title(f"RTT Latency CDF (Normal 5G, N={chosen_N}, 100B, 10Hz)", fontsize=12, fontweight='bold')
        plt.xlabel("Round-Trip Latency (ms)", fontsize=10)
        plt.ylabel("Cumulative Probability", fontsize=10)
        plt.xlim(left=0)
        plt.legend(frameon=True)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "latency_cdf.png"), dpi=150)
        plt.close()

    # Plot 3: p95 Latency across Network Profiles (for N=2, payload=100, rate=10)
    plt.figure(figsize=(8, 5))
    subset3 = df[(df["devices"] == 2) & (df["payload"] == 100) & (df["rate"] == 10)]
    
    if not subset3.empty:
        protocols = subset3["protocol"].unique()
        profiles = ["clean", "good_5g", "degraded_5g"]
        
        x = np.arange(len(profiles))
        width = 0.25
        
        for i, proto in enumerate(protocols):
            proto_data = subset3[subset3["protocol"] == proto]
            # Map to profiles list to maintain order
            p95s = []
            for prof in profiles:
                val = proto_data[proto_data["profile"] == prof]["p95"].values
                p95s.append(val[0] if len(val) > 0 else 0)
                
            plt.bar(x + (i - len(protocols)/2 + 0.5) * width, p95s, width, label=proto.upper())
            
        plt.title("p95 Latency comparison across Network Profiles (N=2, 100B, 10Hz)", fontsize=12, fontweight='bold')
        plt.xlabel("Network Profile", fontsize=10)
        plt.ylabel("p95 Latency (ms)", fontsize=10)
        plt.xticks(x, [p.upper() for p in profiles])
        plt.legend(frameon=True)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "profile_comparison.png"), dpi=150)
        plt.close()

def write_summary_markdown(data_list, output_path):
    df = pd.DataFrame([{k: v for k, v in item.items() if k != "raw_data"} for item in data_list])
    if df.empty:
        return
        
    # Exclude 1Hz runs from the summary table to avoid volatile percentiles due to low sample sizes (15-150 samples)
    df = df[df["rate"].isin([5, 10])]
    
    df_sorted = df.sort_values(by=["protocol", "profile", "devices", "payload", "rate"])
    
    with open(output_path, "w") as f:
        f.write("# CAMPUS Experiment Benchmark Summary\n\n")
        f.write("This file summarizes RTT latency statistics and throughput parsed from the test matrix.\n\n")
        
        f.write("## Summary Table\n\n")
        f.write("| Protocol | Profile | N | Payload | Rate | Recv | Loss % | p50 (ms) | p95 (ms) | p99 (ms) | Mean (ms) |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        
        for _, row in df_sorted.iterrows():
            f.write(
                f"| {row['protocol'].upper()} | {row['profile'].upper()} | {row['devices']} | {row['payload']}B | {row['rate']}Hz | "
                f"{row['acks_received']} | {row['loss_pct']:.1f}% | {row['p50']:.2f} | {row['p95']:.2f} | {row['p99']:.2f} | {row['mean']:.2f} |\n"
            )
            
    print(f"[EDGE] Wrote benchmark markdown summary to: {output_path}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Analyze Benchmark Results")
    parser.add_argument("--output-base", default="results/unified", help="Base directory where results are stored")
    parser.add_argument("--e2e", action="store_true", help="Analyze results from E2E mode sweeps")
    args = parser.parse_args()

    # Automatically divert to separate directory when in E2E mode to avoid overwriting baseline results
    if args.e2e and not args.output_base.endswith("_e2e"):
        args.output_base = args.output_base.rstrip("/\\") + "_e2e"

    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"[ANALYZE] Processing CSV files from {args.output_base}... E2E Mode: {args.e2e}")
    data_list = process_results(root_dir, args.output_base, e2e=args.e2e)
    
    if not data_list:
        print("[ERROR] No data processed. Exiting.")
        return
        
    output_dir = os.path.join(root_dir, args.output_base)
    generate_plots(data_list, output_dir)
    write_summary_markdown(data_list, os.path.join(output_dir, "summary.md"))
    print(f"[ANALYZE] Analysis complete. Plots and summary.md saved successfully in {output_dir}.")

if __name__ == "__main__":
    main()
