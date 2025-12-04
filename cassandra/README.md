# CASSANDRA NOTEBOOK

## Main Update Notes

### 1. Producer Optimization
- Modified Kafka producer to use **Polars** with lazy execution for better performance when reading large CSV files.
- Implemented batch sending to reduce network overhead.

### 2. Spark Streaming Configuration
- Adjusted Spark session settings to be runnable on **low-resource devices** (e.g., local development machines).
- Reduced executor memory and cores to prevent OOM errors.
- Enabled checkpointing for fault tolerance.

### 3. Grafana Dashboard Fixes
- **Datasource Configuration:** Explicitly set `uid: cassandra` in `cassandra.yaml` to fix provisioning errors.
- **JSON Dashboard:**
  - Added `"rawQuery": true` to all panels to bypass the plugin's query builder.
  - Added `"queryType": "query"` and `"alias"` fields to fix "missing field" errors.
  - Simplified CQL queries to remove unsupported macros like `$__timeFrom()`.

## Error Notes
- **"failed to resolve hostname":** Fixed by using the Docker service name `cassandra` instead of `localhost` in Grafana datasource settings.
- **"skip query execution...":** Caused by missing `rawQuery: true` in the dashboard JSON.
- **"Datasource not found":** Caused by missing `uid` in the datasource YAML provisioning file.

## Suggest Further Improvements

### 1. Dashboard Design
- **Real-time Visualization:** The current dashboard uses static queries with `LIMIT`. It should be updated to use time-window based queries (e.g., `WHERE window_start > now() - 5m`) to show true real-time changes.
- **Auto-refresh:** Ensure panel refresh rates are synchronized with Spark streaming batch intervals.

### 2. Table Design
- **Key Selection:** Re-evaluate partition keys. Currently, some queries might cause hotspots.
- **Data Expiry:** Implement TTL (Time To Live) for raw data tables to prevent unlimited disk growth.

### 3. Spark Streaming Performance
- **Latency:** The current processing is slow and doesn't simulate "Big Data" pressure effectively.
- **Throughput:** Increase Kafka partition count and Spark parallelism to handle higher throughput.
- **Resource Tuning:** Tune `spark.sql.shuffle.partitions` based on the actual data volume.

### 4. Evaluation for Final Report
- **Stress Testing:** Use tools like `cassandra-stress` or custom scripts to flood the pipeline with high-velocity data and measure latency.
- **Scalability Test:** Measure how the system behaves when adding more Spark workers or Cassandra nodes.
- **Data Integrity:** Verify that the aggregated data in Cassandra matches the raw data in Kafka (no data loss).


## Design Principles for Cassandra
- **Query-First Design:** Tables must be modeled based on the specific queries required by the dashboard.
- **Partition Keys:** Choose partition keys (e.g., `pickup_zone`, `window_start`) carefully to distribute data evenly while allowing efficient reads.
- **Clustering Columns:** Use clustering columns (e.g., `window_start DESC`) to support range queries and ordering.