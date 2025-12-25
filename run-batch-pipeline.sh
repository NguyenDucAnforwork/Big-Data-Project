#!/bin/bash

# NYC Taxi Batch Pipeline - HDFS + Spark Batch Processing

set -e

echo "============================================================"
echo "  NYC Taxi Batch Pipeline - Lambda Architecture"
echo "============================================================"
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if HDFS is running
print_info "Checking HDFS status..."
if ! docker ps | grep -q namenode; then
    print_warn "HDFS not running. Starting HDFS services..."
    docker compose up -d namenode datanode
    sleep 15
fi

# Wait for HDFS
print_info "Waiting for HDFS to be ready..."
max_attempts=30
attempt=0
while ! curl -s http://localhost:9870 > /dev/null; do
    if [ $attempt -eq $max_attempts ]; then
        echo "ERROR: HDFS failed to start"
        exit 1
    fi
    echo -n "."
    sleep 2
    ((attempt++))
done
echo ""
print_info "HDFS is ready!"

# Install Python dependencies
print_info "Installing Python dependencies..."
pip install -q polars pyarrow 2>/dev/null || print_warn "Some packages may already be installed"

# Upload data to HDFS
print_info "Uploading data to HDFS..."
python3 hdfs/upload_to_hdfs.py

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to upload data to HDFS"
    exit 1
fi

# Run Spark batch job
print_info "Running Spark batch processing..."
spark-submit \
  --driver-memory 1g \
  --executor-memory 1g \
  --packages com.datastax.spark:spark-cassandra-connector_2.13:3.5.1 \
  --conf spark.cassandra.connection.host=localhost \
  --conf spark.cassandra.connection.port=9042 \
  --conf spark.hadoop.fs.defaultFS=hdfs://localhost:9000 \
  --conf spark.sql.shuffle.partitions=2 \
  spark/batch_processing.py

if [ $? -ne 0 ]; then
    echo "ERROR: Spark batch job failed"
    exit 1
fi

echo ""
print_info "Batch pipeline completed successfully!"
echo ""
echo "============================================================"
echo "  Summary"
echo "============================================================"
echo "✓ HDFS: http://localhost:9870"
echo "✓ Data uploaded to: /raw/taxi_trips/"
echo "✓ Daily aggregations written to Cassandra: daily_analytics"
echo ""
echo "Query results:"
echo "  docker exec -it cassandra cqlsh -e \"SELECT * FROM taxi_streaming.daily_analytics LIMIT 10;\""
echo "============================================================"
