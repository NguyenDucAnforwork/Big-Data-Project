# 🔍 Cassandra Query Limitations & Workarounds

## ❌ What DOESN'T Work

### 1. Partial Partition Key GROUP BY
```sql
-- ❌ FAILS: Can't GROUP BY only part of partition key
SELECT pickup_zone, SUM(total_trips) 
FROM taxi_analytics 
GROUP BY pickup_zone 
ALLOW FILTERING;

-- Error: "Group by is not supported on only a part of the partition key"
```

**Reason:** Partition key is `(pickup_zone, peak_category)` - must query both together.

### 2. Cross-Partition Aggregations
```sql
-- ❌ FAILS: SUM/AVG across all partitions
SELECT SUM(total_trips) FROM taxi_analytics ALLOW FILTERING;
```

**Reason:** Cassandra is designed for distributed reads, not analytical aggregations.

---

## ✅ What WORKS

### 1. WHERE IN with Specific Values
```sql
-- ✅ Query specific zones
SELECT pickup_zone, peak_category, total_trips, total_revenue 
FROM taxi_analytics 
WHERE pickup_zone IN ('JFK Airport', 'LaGuardia Airport') 
LIMIT 20 ALLOW FILTERING;
```

### 2. Complete Partition Key Query
```sql
-- ✅ Query with both partition key columns
SELECT * 
FROM taxi_analytics 
WHERE pickup_zone = 'JFK Airport' 
  AND peak_category = 'Off_Peak' 
LIMIT 10;
```

### 3. Table Scans (with LIMIT)
```sql
-- ✅ Simple table scan
SELECT window_start, pickup_zone, total_trips, total_revenue 
FROM taxi_analytics 
LIMIT 50 ALLOW FILTERING;
```

---

## 🎯 Grafana Best Practices

### Use Table Visualizations
**Cassandra plugin works best with tables**, not time series or stats.

### Good Queries for Grafana:

```sql
-- Main Dashboard Query
SELECT window_start, pickup_zone, peak_category, 
       total_trips, total_revenue, avg_speed, avg_tip_ratio 
FROM taxi_analytics 
WHERE pickup_zone IN ('JFK Airport', 'LaGuardia Airport', 'Times Sq/Theatre District') 
LIMIT 100 ALLOW FILTERING;
```

```sql
-- Zone-specific Query
SELECT window_start, peak_category, total_trips, total_revenue 
FROM taxi_analytics 
WHERE pickup_zone = 'JFK Airport' 
LIMIT 50 ALLOW FILTERING;
```

```sql
-- Peak Category Analysis
SELECT window_start, pickup_zone, total_trips, avg_speed 
FROM taxi_analytics 
WHERE peak_category = 'PM_Rush' 
LIMIT 50 ALLOW FILTERING;
```

---

## 🛠️ Workarounds for Aggregations

### Option 1: Application-Level Aggregation
Do SUM/AVG in Python/Spark BEFORE writing to Cassandra (already doing this!).

### Option 2: Materialized Views (Not recommended for streaming)
Create pre-aggregated views (adds complexity).

### Option 3: Spark SQL for Analytics
```bash
# Use Spark to query Cassandra for complex analytics
spark-submit --packages com.datastax.spark:spark-cassandra-connector_2.13:3.5.1 \
  analytics_query.py
```

---

## 📊 Current Schema Design

```sql
CREATE TABLE taxi_analytics (
    -- Partition key (determines data distribution)
    pickup_zone TEXT,
    peak_category TEXT,
    
    -- Clustering columns (determine sort order within partition)
    window_start TIMESTAMP,
    payment_type BIGINT,
    distance_category TEXT,
    
    -- Data columns
    total_trips BIGINT,
    total_revenue DOUBLE,
    avg_distance DOUBLE,
    -- ... other metrics
    
    PRIMARY KEY ((pickup_zone, peak_category), window_start, payment_type, distance_category)
) WITH CLUSTERING ORDER BY (window_start DESC);
```

**Why this design?**
- ✅ Efficient queries by zone + peak category
- ✅ Time-ordered data (DESC for recent first)
- ✅ Distributed across cluster by pickup_zone
- ❌ Can't aggregate across all zones easily

---

## 🎓 Key Takeaways

1. **Cassandra is NOT a data warehouse** - it's optimized for fast reads by partition key
2. **Do aggregations in Spark** - that's why we use Spark Streaming!
3. **Use TABLE visualization in Grafana** - better support than time series
4. **Always use LIMIT** - prevents overwhelming queries
5. **ALLOW FILTERING is slow** - but necessary for demo queries

---

## 📝 For Demo

**Explain to audience:**
- "Cassandra stores pre-aggregated data from Spark"
- "Each window creates one record per zone/peak combination"
- "We query specific zones for visualization"
- "For full analytics, we'd use Spark SQL or export to warehouse"

**Show these queries:**
1. ✅ Specific zone data
2. ✅ Recent windows (LIMIT 20)
3. ✅ Multiple zones comparison
4. ❌ Don't attempt SUM across all data

---

**Bottom line:** Current design is correct for streaming use case. Cassandra handles write-heavy workload and fast lookups. For complex analytics, use Spark!
