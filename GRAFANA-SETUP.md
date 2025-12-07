## 🚀 GRAFANA SETUP GUIDE

### Step 1: Access Grafana
- URL: http://localhost:3000
- Login: `admin` / `admin`
- Skip password change or set new password

### Step 2: Add Cassandra Datasource

1. Click **☰** → **Connections** → **Data sources**
2. Click **Add data source**
3. Search: **Cassandra** (hadesarchitect-cassandra-datasource)
4. Configure:
   ```
   Name: Cassandra
   Host: cassandra:9042
   Keyspace: taxi_streaming
   Consistency: ONE
   ```
5. Click **Save & Test** (should show green checkmark)

### Step 3: Create Simple Dashboard

1. Click **☰** → **Dashboards** → **New** → **New Dashboard**
2. Click **Add visualization**
3. Select **Cassandra** datasource
4. Switch to **Code** mode
5. Use this query:

```sql
SELECT window_start, total_trips, total_revenue 
FROM taxi_analytics 
LIMIT 50 ALLOW FILTERING
```

6. Change visualization to **Table**
7. Click **Apply**
8. Click **Save dashboard** → Name it "NYC Taxi Analytics"

### Step 4: Alternative - Import Dashboard JSON

If auto-provisioning doesn't work:

1. **☰** → **Dashboards** → **New** → **Import**
2. Click **Upload JSON file**
3. Select: `/grafana/provisioning/dashboards/taxi-dashboard.json`
4. Click **Import**

---

## ✅ Working Queries for Manual Panels

### Query 1: All Data (Table)
```sql
SELECT window_start, pickup_zone, peak_category, 
       total_trips, total_revenue, avg_speed, avg_tip_ratio
FROM taxi_analytics 
LIMIT 100 ALLOW FILTERING
```

### Query 2: Specific Zone
```sql
SELECT window_start, peak_category, total_trips, total_revenue
FROM taxi_analytics 
WHERE pickup_zone = 'JFK Airport' 
LIMIT 50 ALLOW FILTERING
```

### Query 3: Peak Analysis
```sql
SELECT pickup_zone, peak_category, total_trips, total_revenue
FROM taxi_analytics 
WHERE peak_category = 'PM_Rush' 
LIMIT 30 ALLOW FILTERING
```

---

## ⚠️ Important Notes

1. **Use TABLE visualization** - Time series doesn't work well with Cassandra plugin
2. **Don't use GROUP BY** - Not supported by plugin
3. **Always use LIMIT** - Prevents overwhelming queries
4. **ALLOW FILTERING is required** - For non-partition key queries

---

## 🎯 Expected Result

You should see a table with columns:
- window_start (timestamp)
- pickup_zone (text)
- peak_category (text)
- total_trips (number)
- total_revenue (number)
- avg_speed (number)
- avg_tip_ratio (number)

**Data count:** ~227 records from the producer run

---

Access now: **http://localhost:3000** (admin/admin)
