import polars as pl
import json
from confluent_kafka import Producer
import time
import os

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))

DATA_PATH = os.path.join(PROJECT_ROOT, "data", "yellow_tripdata_2025-08.parquet")
TOPIC_NAME = "taxi-trips"

# Kafka producer configuration with optimizations
producer_config = {
    'bootstrap.servers': 'localhost:9092',
    'enable.idempotence': False,
    'linger.ms': 100,           # Batch messages for 100ms
    'batch.size': 32768,        # 32KB batch size
    'compression.type': 'snappy',  # Compress messages
    'acks': 1                   # Wait for leader acknowledgment only
}

producer = Producer(producer_config)

print(f"Reading Parquet file from {DATA_PATH}...")
try:
    # Read only first 1000 rows for demo
    trips = pl.read_parquet(DATA_PATH).head(1000)
except FileNotFoundError:
    print(f"ERROR: Data file not found at {DATA_PATH}")
    exit(1)

print(f"Schema: {trips.columns}")
print(f"Loaded {len(trips)} records for streaming")
print("Starting to stream JSON data to Kafka...")

# Batch sending with progress tracking
sent_count = 0
batch_size = 10  # Send 10 messages then flush
start_time = time.time()

for idx, row in enumerate(trips.to_dicts()):
    try:
        # Serialize dict to JSON bytes
        value_bytes = json.dumps(row, default=str).encode('utf-8')
        key_bytes = str(row.get('VendorID', '')).encode('utf-8')
        
        producer.produce(
            topic=TOPIC_NAME,
            value=value_bytes,
            key=key_bytes
        )
        
        sent_count += 1
        
        # Flush every batch_size messages
        if sent_count % batch_size == 0:
            producer.poll(0)
            producer.flush()
            elapsed = time.time() - start_time
            rate = sent_count / elapsed if elapsed > 0 else 0
            print(f"✓ Sent {sent_count}/{len(trips)} messages ({rate:.1f} msg/sec)")
            time.sleep(0.5)  # Small delay between batches
            
    except BufferError:
        print("Buffer full, flushing...")
        producer.flush()
        time.sleep(1)
    except Exception as e:
        print(f"Error sending message {idx}: {e}")
        continue

# Final flush
print(f"\nFlushing remaining messages...")
producer.flush()
elapsed = time.time() - start_time
print(f"\n{'='*60}")
print(f"✓ Producer completed successfully!")
print(f"✓ Sent {sent_count} records in {elapsed:.2f} seconds")
print(f"✓ Average rate: {sent_count/elapsed:.1f} messages/sec")
print(f"{'='*60}")
