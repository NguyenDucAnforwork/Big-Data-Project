import os
import time
import json
import random
import argparse
import sys
import requests
import re
import polars as pl
import heapq
from datetime import datetime, timedelta
from multiprocessing import Process, Value, Lock
import math

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
# Define the sequence of months to process
MONTHS_TO_PROCESS = [
    "2025-08",
    # "2025-09"
]

# --- Defaults ---
DEFAULT_SPEEDUP = 3600.0
DEFAULT_GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
DEFAULT_PRODUCERS = 4
DEFAULT_LATENCY_MS = 20 # Average latency in milliseconds

def get_args():
    parser = argparse.ArgumentParser(description="Traffic Generator")
    parser.add_argument("--gateway", type=str, default=DEFAULT_GATEWAY_URL, help="Ingestion Gateway URL")
    parser.add_argument("--speedup", type=float, default=DEFAULT_SPEEDUP, help="Speedup factor")
    parser.add_argument("--max_records", type=int, default=0, help="Stop after X records (per producer)")
    parser.add_argument("--producers", type=int, default=DEFAULT_PRODUCERS, help="Number of concurrent producers to simulate")
    parser.add_argument("--latency", type=int, default=DEFAULT_LATENCY_MS, help="Average network latency in milliseconds")
    return parser.parse_args()

def ensure_data_ready(filename):
    """Checks for, downloads, and sorts a single data file."""
    original_path = os.path.join(DATA_DIR, f"{filename}.parquet")
    sorted_path = os.path.join(DATA_DIR, f"{filename}_sorted.parquet")
    download_url = f"https://d37ci6vzurychx.cloudfront.net/trip-data/{filename}.parquet"
    
    docker_data_path = os.path.join("/data", f"{filename}_sorted.parquet")
    if os.path.exists(docker_data_path):
        return docker_data_path
    
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
    if os.path.exists(sorted_path): return sorted_path

    print(f"\nDownloading {download_url}...")
    try:
        r = requests.get(download_url, stream=True)
        r.raise_for_status()
        with open(original_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
    except Exception as e:
        print(f"Download Error: {e}")
        exit(1)

    print(f"Sorting {filename}...")
    try:
        df = pl.read_parquet(original_path)
        year, month = map(int, filename.split('_')[-1].split('-'))
        
        start_date = datetime(year, month, 1)
        end_date = (start_date + timedelta(days=32)).replace(day=1)
        
        df = df.filter((pl.col("tpep_dropoff_datetime") >= start_date) & (pl.col("tpep_dropoff_datetime") < end_date))
        df = df.sort("tpep_dropoff_datetime")
        df.write_parquet(sorted_path)
        os.remove(original_path) # Clean up original file
        return sorted_path
    except Exception as e:
        print(f"Processing Error: {e}")
        exit(1)

def print_total_status(start_time, total_sent, total_late, num_producers, current_file=""):
    elapsed = time.time() - start_time
    rate = total_sent / elapsed if elapsed > 0 else 0
    file_str = f"| File: {current_file}" if current_file else ""
    sys.stdout.write(f"\r\x1b[2K📈 Total Rate: \033[1m{rate:,.0f} req/s\033[0m | Sent: {total_sent:,} | Producers: {num_producers} {file_str}")
    sys.stdout.flush()

def send_batch(session, url, records, latency_ms=0):
    if not records: return True
    
    # Simulate network latency with controlled random noise
    if latency_ms > 0:
        # Add ±30% random variation to the base latency
        noise_factor = random.uniform(0.7, 1.3)
        actual_latency = (latency_ms * noise_factor) / 1000.0  # Convert ms to seconds
        time.sleep(actual_latency)
    
    try:
        payload = [
            {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in r.items()}
            for r in records
        ]
        session.post(url, json=payload, timeout=5)
        return True
    except Exception:
        return False

def simulate_volume(producer_id, args, data_path, sent_counter, late_counter, lock):
    session = requests.Session()
    
    df = pl.scan_parquet(data_path).collect()
    total_rows = len(df)
    chunk_size = math.ceil(total_rows / args.producers)
    start_index = producer_id * chunk_size
    end_index = min(start_index + chunk_size, total_rows)
    
    if start_index >= end_index:
        return

    producer_df = df[start_index:end_index]
    iterator = producer_df.iter_rows(named=True)
    
    try:
        first_record = next(iterator)
    except StopIteration:
        return

    current_sim_time = first_record['tpep_dropoff_datetime']
    late_buffer = [] 
    sent_count = 0
    late_count = 0
    pending_batch = [first_record]
    sleep_debt = 0.0
    tie_breaker = 0
    last_flush_time = time.time()

    try:
        for row in iterator:
            if args.max_records > 0 and sent_count >= args.max_records:
                break
            
            row_time = row['tpep_dropoff_datetime']
            
            while late_buffer and late_buffer[0][0] <= row_time:
                _, _, late_row = heapq.heappop(late_buffer)
                pending_batch.append(late_row)
                late_count += 1
            
            time_delta = (row_time - current_sim_time).total_seconds()
            
            if time_delta > 0:
                real_sleep = time_delta / args.speedup
                sleep_debt += real_sleep
                
                if sleep_debt > 0.01:
                    if pending_batch:
                        if send_batch(session, f"{args.gateway}/trips", pending_batch, args.latency):
                            sent_count += len(pending_batch)
                        pending_batch = []
                        last_flush_time = time.time()
                    
                    time.sleep(sleep_debt)
                    sleep_debt = 0.0
                
                current_sim_time = row_time

            flag = str(row.get('store_and_fwd_flag', 'N')).upper()
            if flag == 'Y':
                due = row_time + timedelta(seconds=random.randint(120, 1200))
                heapq.heappush(late_buffer, (due, tie_breaker, row))
                tie_breaker += 1
            else:
                pending_batch.append(row)

            if time.time() - last_flush_time > 1.0 and len(pending_batch) > 0:
                if send_batch(session, f"{args.gateway}/trips", pending_batch, args.latency):
                    sent_count += len(pending_batch)
                pending_batch = []
                last_flush_time = time.time()

    except KeyboardInterrupt:
        pass

    if pending_batch:
        if send_batch(session, f"{args.gateway}/trips", pending_batch, args.latency):
            sent_count += len(pending_batch)
    
    with lock:
        sent_counter.value += sent_count
        late_counter.value += late_count

def main():
    args = get_args()
    
    print(f"\n--- Starting Generator ---")
    print(f"Target: {args.gateway}/trips | Speed: {args.speedup}x | Producers: {args.producers}")

    overall_start_time = time.time()
    cumulative_sent = 0
    cumulative_late = 0

    # Sort files to process them chronologically
    sorted_months = sorted(MONTHS_TO_PROCESS)

    for month_str in sorted_months:
        filename = f"yellow_tripdata_{month_str}"
        print(f"\n--- Processing file: {filename}.parquet ---")
        
        data_path = ensure_data_ready(filename)

        processes = []
        monthly_sent = Value('i', 0)
        monthly_late = Value('i', 0)
        lock = Lock()
        month_start_time = time.time()

        for i in range(args.producers):
            p = Process(target=simulate_volume, args=(i, args, data_path, monthly_sent, monthly_late, lock))
            processes.append(p)
            p.start()

        try:
            while any(p.is_alive() for p in processes):
                with lock:
                    print_total_status(month_start_time, monthly_sent.value, monthly_late.value, args.producers, f"{filename}.parquet")
                time.sleep(0.2)
            
            for p in processes:
                p.join()

        except KeyboardInterrupt:
            print("\n\nStopping all producers...")
            for p in processes:
                p.terminate()
                p.join()
            break # Exit the main file loop on interrupt

        # Final status update for the month
        print_total_status(month_start_time, monthly_sent.value, monthly_late.value, args.producers, f"{filename}.parquet")
        cumulative_sent += monthly_sent.value
        cumulative_late += monthly_late.value

    duration = time.time() - overall_start_time
    rate = cumulative_sent / duration if duration > 0 else 0
    
    print("\n\n--- Overall Summary ---")
    print(f"Total Sent: {cumulative_sent:,}")
    print(f"Total Late (Store & Fwd): {cumulative_late:,}")
    print(f"Total Duration: {duration:.2f}s")
    print(f"Average Rate: {rate:.2f} records/sec")

if __name__ == "__main__":
    main()