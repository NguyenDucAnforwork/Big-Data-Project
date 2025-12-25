#!/usr/bin/env python3
"""
Upload NYC Taxi data to HDFS for batch processing
"""

import os
import sys
import polars as pl
import logging
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "yellow_tripdata_2025-08.parquet")
HDFS_PATH = "/raw/taxi_trips/2025-08.csv"
TEMP_CSV_PATH = "/tmp/taxi_trips_upload.csv"

def upload_to_hdfs():
    """Upload parquet data to HDFS as CSV using docker exec"""
    try:
        # Read parquet file and convert to CSV
        logger.info(f"Reading data from {DATA_PATH}")
        df = pl.read_parquet(DATA_PATH)
        logger.info(f"Loaded {len(df):,} records")
        
        # Write to temporary CSV file
        logger.info(f"Converting to CSV: {TEMP_CSV_PATH}")
        df.write_csv(TEMP_CSV_PATH)
        csv_size = os.path.getsize(TEMP_CSV_PATH) / 1024 / 1024
        logger.info(f"CSV file created: {csv_size:.2f} MB")
        
        # Copy CSV to namenode container
        logger.info("Copying CSV to namenode container...")
        result = subprocess.run(
            ["docker", "cp", TEMP_CSV_PATH, "namenode:/tmp/taxi_trips.csv"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logger.error(f"Failed to copy to container: {result.stderr}")
            return False
        
        # Upload to HDFS using docker exec
        logger.info(f"Uploading to HDFS: {HDFS_PATH}")
        result = subprocess.run(
            ["docker", "exec", "namenode", "hdfs", "dfs", "-put", "-f", 
             "/tmp/taxi_trips.csv", HDFS_PATH],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logger.error(f"Failed to upload to HDFS: {result.stderr}")
            return False
        
        logger.info(f"✓ Successfully uploaded {len(df):,} records to HDFS")
        
        # Verify upload
        result = subprocess.run(
            ["docker", "exec", "namenode", "hdfs", "dfs", "-du", "-h", HDFS_PATH],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info(f"✓ HDFS file size: {result.stdout.strip()}")
        
        # Cleanup temp files
        os.remove(TEMP_CSV_PATH)
        subprocess.run(["docker", "exec", "namenode", "rm", "/tmp/taxi_trips.csv"], 
                      capture_output=True)
        
        return True
        
    except FileNotFoundError:
        logger.error(f"Data file not found: {DATA_PATH}")
        return False
    except Exception as e:
        logger.error(f"Error uploading to HDFS: {e}")
        return False
    finally:
        # Cleanup temp CSV if it exists
        if os.path.exists(TEMP_CSV_PATH):
            try:
                os.remove(TEMP_CSV_PATH)
            except:
                pass

if __name__ == "__main__":
    success = upload_to_hdfs()
    sys.exit(0 if success else 1)
