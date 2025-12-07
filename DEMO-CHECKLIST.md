# 🎯 QUICK DEMO CHECKLIST

## ✅ Current Status
- Kafka: Running on port 9092
- Cassandra: Running on port 9042 (227 records inserted)
- Grafana: Running on port 3000
- Spark: Processing data (PID in .spark.pid)
- Producer: Completed (1000 records sent)

---

## 🔍 Verification Steps

### 1. Check Cassandra Data
```bash
docker exec -it cassandra cqlsh -e "USE taxi_streaming; SELECT COUNT(*) FROM taxi_analytics;"
```
**Expected:** Should show ~227 records

### 2. View Sample Data
```bash
docker exec -it cassandra cqlsh -e "USE taxi_streaming; SELECT window_start, pickup_zone, total_trips, total_revenue FROM taxi_analytics LIMIT 10;"
```

### 3. Top Zones Query
```bash
# Query specific zones
docker exec -it cassandra cqlsh -e "USE taxi_streaming; SELECT pickup_zone, peak_category, total_trips, total_revenue FROM taxi_analytics WHERE pickup_zone IN ('JFK Airport', 'LaGuardia Airport', 'Times Sq/Theatre District') LIMIT 20 ALLOW FILTERING;"
```

---

## 📊 Grafana Setup

### Access Grafana
1. Open browser: **http://localhost:3000**
2. Login: `admin` / `admin`
3. Skip password change (or set new one)

### Configure Cassandra Datasource

**If datasource not configured:**

1. Go to **☰ (menu)** → **Connections** → **Data sources**
2. Click **Add data source**
3. Search: **Cassandra**
4. Configure:
   - **Name**: Cassandra
   - **Host**: `cassandra:9042`
   - **Keyspace**: `taxi_streaming`
   - **Consistency**: ONE
5. Click **Save & Test**

### View Dashboard

1. Go to **☰ → Dashboards**
2. Look for **"NYC Taxi Real-time Analytics"**
3. If not found, import manually:
   - Click **New** → **Import**
   - Upload: `/grafana/provisioning/dashboards/taxi-dashboard.json`

---

## 🎨 Manual Query Examples in Grafana

If dashboard doesn't load, create panels manually:

### Panel 1: Total Trips
- Visualization: **Stat**
- Query:
```sql
SELECT total_trips as value 
FROM taxi_analytics 
LIMIT 100 ALLOW FILTERING
```
**Note:** Cassandra doesn't support SUM across partitions easily. Use Table view instead.

### Panel 2: Total Revenue
- Visualization: **Stat**
- Unit: **Currency USD**
- Query:
```sql
SELECT total_revenue as value 
FROM taxi_analytics 
LIMIT 100 ALLOW FILTERING
```
**Note:** Use Table visualization for better data display.

### Panel 3: Top Zones Table
- Visualization: **Table**
- Query:
```sql
SELECT pickup_zone, peak_category, window_start, total_trips, total_revenue 
FROM taxi_analytics 
WHERE pickup_zone IN ('JFK Airport', 'LaGuardia Airport', 'Times Sq/Theatre District', 'Upper East Side South', 'Midtown Center')
ALLOW FILTERING
```

### Panel 4: Trips Over Time
- Visualization: **Time series** or **Table**
- Query:
```sql
SELECT window_start, pickup_zone, peak_category, total_trips, total_revenue
FROM taxi_analytics 
WHERE pickup_zone IN ('JFK Airport', 'LaGuardia Airport', 'Times Sq/Theatre District') 
LIMIT 50 ALLOW FILTERING
```
**Note:** Cassandra Grafana plugin may have limitations with time series. Use Table view.

---

## 🚨 Troubleshooting

### Grafana Login Failed
```bash
# Reset Grafana
docker stop grafana
docker rm grafana
docker volume rm big-data-project_grafana_data
docker compose up -d grafana
```

### No Data in Grafana
1. Check Cassandra has data:
   ```bash
   docker exec -it cassandra cqlsh -e "SELECT COUNT(*) FROM taxi_streaming.taxi_analytics;"
   ```
2. Verify datasource connection in Grafana
3. Check query syntax (must include `ALLOW FILTERING`)

### Dashboard Not Loading
1. Go to Grafana → Dashboards → New → Import
2. Copy content from `grafana/provisioning/dashboards/taxi-dashboard.json`
3. Paste and click **Load**

---

## 📝 Demo Script

### What to Show:

1. **Real-time Data Ingestion**
   - Show producer logs: `tail -f producer.log`
   - Show Kafka topic: `docker exec -it broker kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic taxi-trips --from-beginning --max-messages 5`

2. **Stream Processing**
   - Show Spark logs: `tail -f spark_streaming.log`
   - Explain windowing (5 minutes)
   - Show checkpoint directory: `ls -la /tmp/spark_checkpoints/taxi_analytics/`

3. **Data Storage**
   - Query Cassandra live
   - Show schema: `docker exec -it cassandra cqlsh -e "DESCRIBE TABLE taxi_streaming.taxi_analytics;"`

4. **Visualization**
   - Open Grafana dashboard
   - Explain each metric
   - Show auto-refresh (10 seconds)

### Key Talking Points:

- ✅ **Kappa Architecture**: Stream-only processing
- ✅ **Window Aggregations**: 5-minute tumbling windows
- ✅ **Watermarking**: Handles late-arriving data (2-minute delay)
- ✅ **Multi-dimensional Analysis**: Zone, peak category, distance, payment type
- ✅ **Scalability**: Cassandra partitioning, Spark parallelism

---

## 🎬 Next Steps

### To Run More Data:
```bash
# Edit producer to send more records
# In kafka/producer.py line 29:
trips = pl.read_parquet(DATA_PATH).head(5000)  # Instead of 1000

# Or run full dataset:
trips = pl.read_parquet(DATA_PATH)  # All records
```

### To Stop Pipeline:
```bash
./stop-pipeline.sh
```

### To Restart:
```bash
./start-pipeline.sh
# Wait for "Pipeline is ready"
# Then run producer again
```

---

**🎉 Demo Ready!**
