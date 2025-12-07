#!/bin/bash

# NYC Taxi Streaming Pipeline - Automated Startup Script
# This script handles the complete pipeline initialization

set -e  # Exit on error

echo "============================================================"
echo "  NYC Taxi Analytics Streaming Pipeline - Startup"
echo "============================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to wait for service
wait_for_service() {
    local service=$1
    local port=$2
    local max_attempts=30
    local attempt=1
    
    print_info "Waiting for $service on port $port..."
    while ! nc -z localhost $port 2>/dev/null; do
        if [ $attempt -eq $max_attempts ]; then
            print_error "$service failed to start after $max_attempts attempts"
            return 1
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    echo ""
    print_info "$service is ready!"
}

# Step 0: Check prerequisites
print_info "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    exit 1
fi

if ! command -v java &> /dev/null; then
    print_error "Java is not installed"
    exit 1
fi

if ! command -v spark-submit &> /dev/null; then
    print_error "Spark is not installed or not in PATH"
    exit 1
fi

if ! command -v nc &> /dev/null; then
    print_warn "netcat (nc) not found, installing..."
    sudo apt-get update && sudo apt-get install -y netcat
fi

print_info "All prerequisites satisfied ✓"
echo ""

# Step 1: Clean old state
print_info "Cleaning previous state..."
docker compose down 2>/dev/null || true
sudo rm -rf kafka/kafka_data/* 2>/dev/null || true
rm -rf /tmp/spark_checkpoints/* 2>/dev/null || true
mkdir -p kafka/kafka_data
mkdir -p /tmp/spark_checkpoints
print_info "Cleanup complete ✓"
echo ""

# Step 2: Start Docker services
print_info "Starting Docker services..."
docker compose up -d

echo ""
print_info "Waiting for services to initialize..."
sleep 5

# Wait for Kafka
wait_for_service "Kafka" 9092

# Create Kafka topic
print_info "Creating Kafka topic 'taxi-trips'..."
docker exec broker /opt/kafka/bin/kafka-topics.sh \
  --create \
  --topic taxi-trips \
  --bootstrap-server localhost:9092 \
  --replication-factor 1 \
  --partitions 3 2>/dev/null || print_warn "Topic may already exist"

print_info "Kafka topic created ✓"

# Wait for Cassandra (takes longer)
wait_for_service "Cassandra" 9042
sleep 10  # Extra time for Cassandra to be fully ready

# Wait for Grafana
wait_for_service "Grafana" 3000

echo ""
print_info "All Docker services are running ✓"
echo ""

# Step 3: Initialize Cassandra schema
print_info "Initializing Cassandra schema..."
max_retries=5
retry=0
while [ $retry -lt $max_retries ]; do
    if docker exec cassandra cqlsh -e "SOURCE '/tmp/init.cql'" 2>/dev/null; then
        print_info "Cassandra schema initialized ✓"
        break
    else
        # Try copying file and running
        docker cp cassandra/init.cql cassandra:/tmp/init.cql 2>/dev/null
        if docker exec cassandra cqlsh -f /tmp/init.cql 2>/dev/null; then
            print_info "Cassandra schema initialized ✓"
            break
        fi
        ((retry++))
        if [ $retry -eq $max_retries ]; then
            print_error "Failed to initialize Cassandra schema after $max_retries attempts"
            exit 1
        fi
        print_warn "Retry $retry/$max_retries - waiting 5 seconds..."
        sleep 5
    fi
done

echo ""

# Step 4: Verify schema
print_info "Verifying Cassandra schema..."
if docker exec cassandra cqlsh -e "DESCRIBE TABLE taxi_streaming.taxi_analytics;" > /dev/null 2>&1; then
    print_info "Schema verification complete ✓"
else
    print_warn "Could not verify schema, but continuing..."
fi
echo ""

# Step 5: Start Spark Streaming (in background)
print_info "Starting Spark Streaming job..."
nohup spark-submit \
  --driver-memory 1g \
  --executor-memory 1g \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.13:3.5.1,com.datastax.spark:spark-cassandra-connector_2.13:3.5.1 \
  --conf spark.driver.bindAddress=127.0.0.1 \
  --conf spark.driver.host=127.0.0.1 \
  --conf spark.cassandra.connection.timeoutMS=60000 \
  --conf spark.cassandra.read.timeoutMS=60000 \
  --conf spark.sql.shuffle.partitions=2 \
  spark/streaming.py > spark_streaming.log 2>&1 &

SPARK_PID=$!
echo $SPARK_PID > .spark.pid

print_info "Spark job started (PID: $SPARK_PID)"
print_info "Waiting for Spark to initialize..."
sleep 20

# Check if Spark is still running
if ! ps -p $SPARK_PID > /dev/null; then
    print_error "Spark job failed to start. Check spark_streaming.log"
    exit 1
fi

print_info "Spark is running ✓"
echo ""

# Step 6: Display status
echo "============================================================"
echo "  Pipeline Status"
echo "============================================================"
echo ""
echo "✓ Kafka:     Running on localhost:9092"
echo "✓ Cassandra: Running on localhost:9042"
echo "✓ Grafana:   Running on http://localhost:3000 (admin/admin)"
echo "✓ Spark:     Running (PID: $SPARK_PID)"
echo ""
echo "============================================================"
echo "  Next Steps"
echo "============================================================"
echo ""
echo "1. Start the producer (in a new terminal):"
echo "   $ uv run python kafka/producer.py"
echo ""
echo "2. Monitor Spark logs:"
echo "   $ tail -f spark_streaming.log"
echo ""
echo "3. Query Cassandra:"
echo "   $ docker exec cassandra cqlsh -e \"USE taxi_streaming; SELECT COUNT(*) FROM taxi_analytics;\""
echo ""
echo "4. View Grafana dashboard:"
echo "   Open http://localhost:3000"
echo ""
echo "5. Stop the pipeline:"
echo "   $ ./stop-pipeline.sh"
echo ""
echo "============================================================"
print_info "Pipeline is ready for demo! 🚀"
echo "============================================================"
