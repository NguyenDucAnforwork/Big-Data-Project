# 🏗️ Lambda Architecture Implementation

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    NYC Taxi Data Pipeline                    │
│                   (Lambda Architecture)                      │
└─────────────────────────────────────────────────────────────┘

                    Raw Data (Parquet)
                           │
                           ├────────────────────┐
                           │                    │
                    ┌──────▼──────┐      ┌─────▼─────┐
                    │   BATCH     │      │  STREAM   │
                    │   LAYER     │      │   LAYER   │
                    └──────┬──────┘      └─────┬─────┘
                           │                    │
                    ┌──────▼──────┐      ┌─────▼─────┐
                    │    HDFS     │      │   Kafka   │
                    │ Data Lake   │      │  Topics   │
                    └──────┬──────┘      └─────┬─────┘
                           │                    │
                    ┌──────▼──────┐      ┌─────▼─────┐
                    │Spark Batch  │      │   Spark   │
                    │  (Daily)    │      │ Streaming │
                    └──────┬──────┘      └─────┬─────┘
                           │                    │
                           └────────┬───────────┘
                                    │
                            ┌───────▼────────┐
                            │   Cassandra    │
                            │  (Serving DB)  │
                            └───────┬────────┘
                                    │
                            ┌───────▼────────┐
                            │    Grafana     │
                            │  Dashboards    │
                            └────────────────┘
```

---

## 🎯 Components

### **Batch Layer (Historical Analysis)**
- **Data Lake:** HDFS stores raw data
- **Processing:** Spark Batch runs daily aggregations
- **Storage:** Cassandra `daily_analytics` table
- **Purpose:** Long-term trends, historical reports

### **Speed Layer (Real-time Analytics)**
- **Ingestion:** Kafka for streaming data
- **Processing:** Spark Structured Streaming (5-min windows)
- **Storage:** Cassandra `taxi_analytics` table
- **Purpose:** Real-time dashboards, immediate insights

### **Serving Layer**
- **Database:** Cassandra (handles both batch and stream writes)
- **Visualization:** Grafana (unified view of real-time + historical)

---

## 🚀 Quick Start

### Step 1: Start Infrastructure
```bash
# Start all services (including HDFS)
docker compose up -d

# Wait for services
sleep 30
```

### Step 2: Run Batch Pipeline (One-time)
```bash
# Upload data to HDFS and run batch job
./run-batch-pipeline.sh
```

**Expected output:**
```
✓ HDFS is ready!
✓ Uploading data to HDFS...
✓ Successfully uploaded 2,964,624 records to HDFS
✓ Running Spark batch processing...
✓ Successfully wrote 145 daily aggregations to Cassandra
```

### Step 3: Run Streaming Pipeline
```bash
# Start real-time processing
./start-pipeline.sh

# In another terminal, start producer
uv run python kafka/producer.py
```

---

## 📊 Data Tables

### Batch Table: `daily_analytics`
```sql
CREATE TABLE daily_analytics (
    trip_date DATE,           -- Partition key
    pickup_zone TEXT,         -- Clustering key
    total_trips BIGINT,
    total_revenue DOUBLE,
    avg_fare DOUBLE,
    avg_distance DOUBLE,
    avg_speed DOUBLE,
    avg_passengers DOUBLE,
    PRIMARY KEY (trip_date, pickup_zone)
);
```

**Query example:**
```sql
-- Daily trends for JFK Airport
SELECT trip_date, total_trips, total_revenue 
FROM daily_analytics 
WHERE trip_date >= '2025-07-01' 
  AND pickup_zone = 'JFK Airport'
ALLOW FILTERING;
```

### Stream Table: `taxi_analytics`
```sql
CREATE TABLE taxi_analytics (
    window_start TIMESTAMP,   -- 5-minute windows
    pickup_zone TEXT,
    peak_category TEXT,
    total_trips BIGINT,
    total_revenue DOUBLE,
    avg_speed DOUBLE,
    -- ... other real-time metrics
    PRIMARY KEY ((pickup_zone, peak_category), window_start, ...)
);
```

---

## 🔍 Verification

### Check HDFS Data
```bash
# Access HDFS UI
http://localhost:9870

# CLI check
docker exec -it namenode hdfs dfs -ls /raw/taxi_trips/
docker exec -it namenode hdfs dfs -cat /raw/taxi_trips/2025-08.csv | head -10
```

### Check Cassandra Data
```bash
# Batch data
docker exec -it cassandra cqlsh -e "SELECT COUNT(*) FROM taxi_streaming.daily_analytics;"

# Sample batch results
docker exec -it cassandra cqlsh -e "SELECT * FROM taxi_streaming.daily_analytics LIMIT 10;"

# Stream data
docker exec -it cassandra cqlsh -e "SELECT COUNT(*) FROM taxi_streaming.taxi_analytics;"
```

### Check Spark Jobs
```bash
# Batch job logs
cat spark_batch.log

# Streaming job logs
tail -f spark_streaming.log
```

---

## 📈 Grafana Dashboards

### Dashboard 1: Real-time Analytics
- **Source:** `taxi_analytics` table
- **Metrics:** 5-minute windows, live updates
- **Queries:**
```sql
SELECT window_start, pickup_zone, total_trips, total_revenue
FROM taxi_analytics
WHERE pickup_zone IN ('JFK Airport', 'LaGuardia Airport')
LIMIT 100 ALLOW FILTERING
```

### Dashboard 2: Historical Trends
- **Source:** `daily_analytics` table
- **Metrics:** Daily aggregations, long-term patterns
- **Queries:**
```sql
SELECT trip_date, pickup_zone, total_trips, total_revenue
FROM daily_analytics
WHERE trip_date >= '2025-07-01'
LIMIT 100 ALLOW FILTERING
```

### Dashboard 3: Unified View (Lambda)
- **Source:** Both tables joined
- **Purpose:** Compare real-time vs historical
- **Use Grafana transformations** to merge datasets

---

## 🛠️ Maintenance

### Re-run Batch Processing
```bash
# Upload new data to HDFS
python3 hdfs/upload_to_hdfs.py

# Run batch job
spark-submit \
  --packages com.datastax.spark:spark-cassandra-connector_2.13:3.5.1 \
  --conf spark.hadoop.fs.defaultFS=hdfs://localhost:9000 \
  spark/batch_processing.py
```

### Schedule Daily Batch Jobs
```bash
# Add to crontab for daily runs at 2 AM
0 2 * * * cd /home/ducan/Big-Data-Project && ./run-batch-pipeline.sh >> /var/log/taxi-batch.log 2>&1
```

### Clean Up HDFS
```bash
# Remove old files
docker exec -it namenode hdfs dfs -rm -r /raw/taxi_trips/2025-07.csv

# Check disk usage
docker exec -it namenode hdfs dfs -du -h /raw/
```

---

## 🎓 Lambda Architecture Benefits

| Aspect | Batch Layer | Speed Layer |
|--------|-------------|-------------|
| **Latency** | Hours/Days | Seconds |
| **Accuracy** | High (full recompute) | Approximate (windows) |
| **Data Volume** | All historical data | Recent data only |
| **Complexity** | Simple aggregations | Stream processing |
| **Storage** | HDFS (cheap) | Cassandra (fast) |

**Combined:** Best of both worlds - accurate historical + fast real-time!

---

## 📝 Demo Script

### Show Lambda Architecture:

1. **Explain Architecture:**
   - "We use Lambda Architecture: Batch + Stream"
   - "HDFS stores all historical data"
   - "Kafka handles real-time events"
   - "Both write to Cassandra for unified serving"

2. **Show HDFS:**
   - Open http://localhost:9870
   - Browse `/raw/taxi_trips/`
   - Show file size and replication

3. **Run Batch Job:**
   - `./run-batch-pipeline.sh`
   - Explain daily aggregations
   - Query `daily_analytics` table

4. **Show Streaming:**
   - Start producer
   - Show Spark logs processing 5-min windows
   - Query `taxi_analytics` table

5. **Grafana Unified View:**
   - Dashboard 1: Real-time (last hour)
   - Dashboard 2: Historical (last month)
   - Dashboard 3: Combined view

---

## 🚨 Troubleshooting

### HDFS Issues
```bash
# Check namenode status
docker logs namenode

# Restart HDFS
docker compose restart namenode datanode
```

### Batch Job Fails
```bash
# Check Spark logs
cat spark_batch.log

# Verify HDFS connectivity
docker exec -it namenode hdfs dfs -ls /
```

### Data Not Appearing
```bash
# Verify Cassandra schema
docker exec -it cassandra cqlsh -e "DESCRIBE TABLE taxi_streaming.daily_analytics;"

# Check table data
docker exec -it cassandra cqlsh -e "SELECT * FROM taxi_streaming.daily_analytics LIMIT 1;"
```

---

**🎉 Lambda Architecture Implemented! Now you have both real-time AND historical analytics!**
