#!/bin/bash

# NYC Taxi Streaming Pipeline - Shutdown Script

echo "============================================================"
echo "  Stopping NYC Taxi Analytics Pipeline"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

# Stop Spark
if [ -f .spark.pid ]; then
    SPARK_PID=$(cat .spark.pid)
    print_info "Stopping Spark job (PID: $SPARK_PID)..."
    kill $SPARK_PID 2>/dev/null || true
    rm .spark.pid
    print_info "Spark stopped ✓"
else
    print_info "No Spark PID file found, skipping..."
fi

# Stop Docker services
print_info "Stopping Docker services..."
docker compose down

print_info "Cleaning up..."
# Optionally clean checkpoints (uncomment if needed)
# rm -rf /tmp/spark_checkpoints/*

echo ""
print_info "Pipeline stopped successfully! ✓"
echo ""
