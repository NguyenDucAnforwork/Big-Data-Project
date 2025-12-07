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

# Kafka producer configuration (simple JSON producer, no Schema Registry)
producer_config = {
    'bootstrap.servers': 'localhost:9092',
    'enable.idempotence': False
}

producer = Producer(producer_config)

print(f"Reading Parquet file from {DATA_PATH}...")
try:
    trips = pl.read_parquet(DATA_PATH)
except FileNotFoundError:
    print(f"ERROR: Data file not found at {DATA_PATH}")
    exit(1)

# Use all columns for complete schema (Spark expects full taxi trip schema)
print(f"Schema: {trips.columns}")
print("File read successfully. Starting to stream JSON data...")

# Iterate and produce records with proper JSON encoding
sent_count = 0
for row in trips.to_dicts():
    try:
        # Serialize dict to JSON bytes (default=str handles datetime objects)
        value_bytes = json.dumps(row, default=str).encode('utf-8')
        key_bytes = str(row.get('VendorID', '')).encode('utf-8')
        
        producer.produce(
            topic=TOPIC_NAME,
            value=value_bytes,
            key=key_bytes
        )
        producer.poll(0)
        time.sleep(1.0)
        sent_count += 1
        if sent_count % 100 == 0:
            print(f"Sent {sent_count} messages...")
            
    except BufferError:
        print("Buffer full, flushing...")
        producer.flush()
    except Exception as e:
        print(f"An error occurred: {e}")
        producer.flush()

print(f"Finished streaming {sent_count} records. Flushing final messages...")
producer.flush()
print("Producer completed successfully!")
