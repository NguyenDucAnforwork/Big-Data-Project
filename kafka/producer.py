# import polars as pl
# import json
# from confluent_kafka import Producer
# import time
# import os

# # --- Configuration ---
# SCRIPT_DIR = os.path.dirname(__file__)
# PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))

# DATA_PATH = os.path.join(PROJECT_ROOT, "data", "yellow_tripdata_2025-08.parquet")
# TOPIC_NAME = "taxi-trips"

# # Kafka producer configuration (simple JSON producer, no Schema Registry)
# producer_config = {
#     'bootstrap.servers': 'localhost:9092',
#     'enable.idempotence': True
# }

# producer = Producer(producer_config)

# print(f"Reading Parquet file from {DATA_PATH}...")
# try:
#     trips = pl.read_parquet(DATA_PATH)
# except FileNotFoundError:
#     print(f"ERROR: Data file not found at {DATA_PATH}")
#     exit(1)

# # Use all columns for complete schema (Spark expects full taxi trip schema)
# print(f"Schema: {trips.columns}")
# print("File read successfully. Starting to stream JSON data...")

# # Iterate and produce records with proper JSON encoding
# sent_count = 0
# for row in trips.to_dicts():
#     try:
#         # Serialize dict to JSON bytes (default=str handles datetime objects)
#         value_bytes = json.dumps(row, default=str).encode('utf-8')
#         key_bytes = str(row.get('VendorID', '')).encode('utf-8')
        
#         producer.produce(
#             topic=TOPIC_NAME,
#             value=value_bytes,
#             key=key_bytes
#         )
#         producer.poll(0)
#         time.sleep(0.1)
#         # time.sleep(30)  # My laptop struggles with 0.1s delay
#         sent_count += 1
#         if sent_count % 10000 == 0:
#             print(f"Sent {sent_count} messages...")
            
#     except BufferError:
#         print("Buffer full, flushing...")
#         producer.flush()
#     except Exception as e:
#         print(f"An error occurred: {e}")
#         producer.flush()

# print(f"Finished streaming {sent_count} records. Flushing final messages...")
# producer.flush()
# print("Producer completed successfully!")

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
BATCH_SIZE = 1000  # Process 1000 rows at a time
MAX_RECORDS = 10000  # Limit for testing (remove for production)

# Kafka producer configuration
producer_config = {
    'bootstrap.servers': 'localhost:9092',
    'enable.idempotence': True
}

producer = Producer(producer_config)

print(f"Streaming Parquet file from {DATA_PATH}...")
print(f"Batch size: {BATCH_SIZE}, Max records: {MAX_RECORDS}")

try:
    # Use scan_parquet for lazy loading (doesn't load into memory)
    lazy_df = pl.scan_parquet(DATA_PATH)
    
    # Get schema without loading data
    schema = lazy_df.collect_schema()
    print(f"Schema: {schema.names()}")
    print("Starting to stream JSON data in batches...")
    
    sent_count = 0
    
    # Process in batches using slice
    offset = 0
    while sent_count < MAX_RECORDS:
        # Read only BATCH_SIZE rows at a time
        batch = lazy_df.slice(offset, BATCH_SIZE).collect()
        
        # Break if no more data
        if batch.height == 0:
            break
        
        # Process each row in the batch
        for row in batch.to_dicts():
            if sent_count >= MAX_RECORDS:
                break
                
            try:
                value_bytes = json.dumps(row, default=str).encode('utf-8')
                key_bytes = str(row.get('VendorID', '')).encode('utf-8')
                
                producer.produce(
                    topic=TOPIC_NAME,
                    value=value_bytes,
                    key=key_bytes
                )
                producer.poll(0)
                time.sleep(0.1)  # Adjust delay as needed
                
                sent_count += 1
                if sent_count % 100 == 0:  # Log every 100 messages
                    print(f"Sent {sent_count}/{MAX_RECORDS} messages...")
                    
            except BufferError:
                print("Buffer full, flushing...")
                producer.flush()
            except Exception as e:
                print(f"Error at record {sent_count}: {e}")
                break
        
        offset += BATCH_SIZE
        
        # Optional: Clear batch from memory explicitly
        del batch
    
except FileNotFoundError:
    print(f"ERROR: Data file not found at {DATA_PATH}")
    exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)

print(f"Finished streaming {sent_count} records. Flushing final messages...")
producer.flush()
print("Producer completed successfully!")