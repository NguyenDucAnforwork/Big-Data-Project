# 🚀 NYC Taxi Analytics Pipeline - Demo Guide

**Real-time streaming analytics pipeline** for NYC taxi trip data using Kafka, Spark Structured Streaming, Cassandra, and Grafana.

---

## 📋 Architecture Overview

```
NYC Taxi Data (Parquet)
        ↓
   Kafka Producer
        ↓
   Kafka Topic (taxi-trips)
        ↓
   Spark Structured Streaming
   • Data Cleaning
   • Feature Engineering
   • 5-minute Window Aggregations
        ↓
   Cassandra (taxi_analytics table)
        ↓
   Grafana Dashboard
```

---

## ✅ Prerequisites

### Already Installed (Per Your Setup)
- ✅ Docker Desktop with Kubernetes enabled
- ✅ Ubuntu (WSL2)
- ✅ Java 17
- ✅ Apache Spark 3.5.7
- ✅ Python with `uv` package manager

### Quick Verification

```bash
# Verify all tools
docker --version
java -version
spark-submit --version
uv --version
```

---

## 🎯 Quick Start (Automated)

### Option 1: One-Command Launch (Recommended)

```bash
# Start everything automatically
./start-pipeline.sh
```

This script will:
1. ✓ Clean previous state
2. ✓ Start Docker services (Kafka, Cassandra, Grafana)
3. ✓ Initialize Cassandra schema
4. ✓ Start Spark Streaming job
5. ✓ Display status dashboard

**Wait until you see:** `Pipeline is ready for demo! 🚀`

### Option 2: Manual Step-by-Step

If you prefer manual control or troubleshooting:

#### Step 1: Clean Previous State
```bash
docker compose down
sudo rm -rf kafka/kafka_data/*
rm -rf /tmp/spark_checkpoints/*
mkdir -p kafka/kafka_data /tmp/spark_checkpoints
```

#### Step 2: Start Docker Services
```bash
docker compose up -d

# Wait for services (30-60 seconds)
sleep 30

# Verify all containers are running
docker ps
```

#### Step 3: Initialize Cassandra
```bash
# Wait for Cassandra to be ready
docker exec -it cassandra cqlsh -e "DESCRIBE KEYSPACES" 

# Initialize schema
docker exec -i cassandra cqlsh < cassandra/init.cql

# Verify table creation
docker exec -it cassandra cqlsh -e "DESCRIBE TABLE taxi_streaming.taxi_analytics;"
```

#### Step 4: Start Spark Streaming
```bash
spark-submit \
  --driver-memory 1g \
  --executor-memory 1g \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.13:3.5.1,com.datastax.spark:spark-cassandra-connector_2.13:3.5.1 \
  --conf spark.driver.bindAddress=127.0.0.1 \
  --conf spark.driver.host=127.0.0.1 \
  --conf spark.cassandra.connection.timeoutMS=60000 \
  --conf spark.cassandra.read.timeoutMS=60000 \
  --conf spark.sql.shuffle.partitions=2 \
  spark/streaming.py
```

**Wait for:** `✓ Streaming query started successfully!`

---

## 📊 Run the Demo

### Start Producer (New Terminal)

```bash
# Open a new terminal
cd ~/Big-Data-Project

# Start streaming data
uv run python kafka/producer.py
```

**Expected Output:**
```
✓ Sent 10/1000 messages (20.0 msg/sec)
✓ Sent 20/1000 messages (20.0 msg/sec)
...
✓ Producer completed successfully!
✓ Sent 1000 records in 50.00 seconds
```

---

## 🔍 Verify Data Flow

### 1. Check Kafka Messages

```bash
docker exec -it broker kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic taxi-trips \
  --from-beginning \
  --max-messages 5
```

### 2. Monitor Spark Processing

```bash
# If using automated script
tail -f spark_streaming.log

# Look for these log entries:
# INFO: Writing batch X to taxi_analytics
# Batch X: Successfully written to Cassandra
```

### 3. Query Cassandra Data

```bash
# Quick queries using helper script
./query-cassandra.sh count          # Count total records
./query-cassandra.sh recent         # View recent aggregations
./query-cassandra.sh zones          # Top revenue zones
./query-cassandra.sh peaks          # Peak hour analysis

# Or manually
docker exec cassandra cqlsh -e "USE taxi_streaming; SELECT COUNT(*) FROM taxi_analytics;"

# Interactive shell (if needed)
./query-cassandra.sh interactive
# Then run:
USE taxi_streaming;
SELECT * FROM taxi_analytics LIMIT 10;
exit;
```

### 4. View Grafana Dashboard

```bash
# Open browser
http://localhost:3000
```

**Login:** `admin` / `admin`

**Setup Datasource:**
1. Go to **Connections** → **Data Sources**
2. Click **Add data source**
3. Search and select **Cassandra**
4. Configure:
   - Host: `cassandra:9042`
   - Keyspace: `taxi_streaming`
   - Consistency: `ONE`
5. Click **Save & Test**

**Create Dashboard:**
1. Create → Dashboard → Add visualization
2. Select Cassandra datasource
3. Query: `SELECT * FROM taxi_analytics WHERE pickup_zone = 'Manhattan' ALLOW FILTERING;`
4. Visualization: Time series or Table

---

## 📈 Demo Scenarios

### Scenario 1: Real-time Revenue Tracking

```sql
-- In Cassandra (cqlsh)
SELECT window_start, SUM(total_revenue) as total_revenue
FROM taxi_analytics
WHERE window_start >= '2025-08-01 00:00:00'
GROUP BY window_start
ALLOW FILTERING;
```

### Scenario 2: Peak Hour Analysis

```sql
SELECT peak_category, SUM(total_trips) as trips, AVG(avg_fare) as avg_fare
FROM taxi_analytics
GROUP BY peak_category
ALLOW FILTERING;
```

### Scenario 3: Distance-based Behavior

```sql
SELECT distance_category, AVG(avg_tip_ratio) as avg_tip
FROM taxi_analytics
GROUP BY distance_category
ALLOW FILTERING;
```

---

## 🛑 Stop the Pipeline

### Using Script
```bash
./stop-pipeline.sh
```

### Manual Shutdown
```bash
# Stop Spark (Ctrl+C in Spark terminal)

# Stop Docker services
docker compose down

# Optional: Clean data
sudo rm -rf kafka/kafka_data/*
rm -rf /tmp/spark_checkpoints/*
```

---

## 🔧 Troubleshooting

### Problem: Spark fails to start

**Solution:**
```bash
# Check logs
tail -f spark_streaming.log

# Verify Kafka is accessible
nc -zv localhost 9092

# Verify Cassandra is accessible
nc -zv localhost 9042
```

### Problem: Cassandra connection timeout

**Solution:**
```bash
# Check if Cassandra is fully ready
docker exec cassandra nodetool status

# Wait longer for initialization
sleep 30

# Copy schema file into container
docker cp cassandra/init.cql cassandra:/tmp/init.cql

# Re-initialize schema
docker exec cassandra cqlsh -f /tmp/init.cql

# Test connection
./query-cassandra.sh count
```

### Problem: Grafana login fails (admin/admin)

**Solution:**
```bash
# Reset Grafana volume
docker compose down
docker volume rm big-data-project_grafana_data

# Restart services
./start-pipeline.sh

# Now login should work with admin/admin
```

### Problem: Producer fails

**Solution:**
```bash
# Check data file exists
ls -lh data/yellow_tripdata_2025-08.parquet

# Verify Kafka topic exists
docker exec -it broker kafka-topics.sh \
  --list --bootstrap-server localhost:9092
```

### Problem: Out of memory

**Solution:**
```bash
# Increase Docker Desktop memory (Settings → Resources)
# Recommended: 6GB RAM minimum

# Reduce producer data size (already set to 1000 records)
# Edit kafka/producer.py line 29 if needed
```

### Problem: No data in Cassandra

**Check processing:**
```bash
# Verify Spark is receiving data
grep "Writing batch" spark_streaming.log

# Check Kafka consumer group
docker exec -it broker kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group spark-streaming --describe
```

---

## 📊 System Resources

### Current Configuration (Optimized for 8GB RAM)

| Service   | CPU Limit | Memory Limit | Purpose                    |
|-----------|-----------|--------------|----------------------------|
| Kafka     | 1.0 core  | 1 GB         | Message broker             |
| Cassandra | 2.0 cores | 2 GB         | Time-series storage        |
| Grafana   | 0.5 core  | 512 MB       | Visualization              |
| Spark     | 2.0 cores | 2 GB         | Stream processing          |

**Total:** ~5.5 GB (leaves 2.5 GB for OS)

---

## 🎓 Key Features Demonstrated

### 1. **Streaming Ingestion**
- Kafka producer reads Parquet → streams JSON
- Batch sending with compression (Snappy)
- Rate limiting: ~20 messages/sec

### 2. **Real-time Processing**
- Spark Structured Streaming
- 5-minute tumbling windows
- Watermarking for late data (2 minutes)

### 3. **Data Enrichment**
- Zone lookup via broadcast join
- Feature engineering (speed, tip_ratio, etc.)
- Peak hour categorization

### 4. **Aggregations**
- Multi-dimensional grouping
- 9 metrics per window:
  - total_trips, total_revenue
  - avg_distance, avg_fare, avg_fare_per_mile
  - avg_tip_ratio, avg_speed
  - avg_duration_sec, avg_occupancy

### 5. **Storage Strategy**
- Cassandra time-series table
- Composite partition key for distributed reads
- 30-day TTL for automatic cleanup

---

## 📝 Project Structure

```
Big-Data-Project/
├── kafka/
│   ├── producer.py          # Streams Parquet → Kafka
│   └── kafka_data/          # Kafka persistent storage
├── spark/
│   ├── streaming.py         # Spark Structured Streaming
│   └── taxi_zone_lookup.csv # Zone reference data
├── cassandra/
│   └── init.cql             # Schema initialization
├── grafana/
│   └── provisioning/        # Dashboard configs
├── data/
│   └── yellow_tripdata_2025-08.parquet
├── compose.yaml             # Docker services
├── start-pipeline.sh        # Automated startup
├── stop-pipeline.sh         # Shutdown script
└── DEMO-GUIDE.md           # This file
```

---

## 🚀 Performance Tips

1. **For Faster Demo:**
   - Producer already limited to 1000 records
   - Batch size set to 10 messages
   - Window size: 5 minutes

2. **For Production Simulation:**
   - Edit `kafka/producer.py` line 29: `trips = pl.read_parquet(DATA_PATH)`
   - Reduce `time.sleep(0.5)` to `0.1` for higher throughput
   - Increase window size in `spark/streaming.py`

3. **For Low-Resource Machines:**
   - Reduce Cassandra memory in `compose.yaml`
   - Use `--driver-memory 512m` for Spark
   - Increase processing interval to 30 seconds

---

## 🎯 Success Criteria

Your demo is successful when you can show:

1. ✅ Producer sending messages to Kafka
2. ✅ Spark logs showing batch processing
3. ✅ Cassandra query returning aggregated data
4. ✅ Grafana displaying live metrics
5. ✅ End-to-end latency < 30 seconds

---

## 📞 Quick Reference

| Service      | URL/Command                        |
|--------------|------------------------------------|
| Grafana      | http://localhost:3000 (admin/admin)|
| Cassandra    | `./query-cassandra.sh interactive` |
| Quick Queries| `./query-cassandra.sh count`       |
| Kafka Topics | `docker exec broker kafka-topics.sh --list --bootstrap-server localhost:9092` |
| Spark Logs   | `tail -f spark_streaming.log`      |
| Stop All     | `./stop-pipeline.sh`               |

---

## 🎉 Conclusion

This pipeline demonstrates **real-time data engineering** using industry-standard tools:
- **Kafka**: Scalable message broker
- **Spark**: Distributed stream processing
- **Cassandra**: High-performance NoSQL for time-series
- **Grafana**: Enterprise visualization

**Perfect for showcasing:**
- Event-driven architecture
- Lambda/Kappa architecture patterns
- Window-based aggregations
- Real-time analytics dashboards

**Good luck with your demo! 🚀**
