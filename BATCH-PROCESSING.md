# Batch Processing Layer - NYC Taxi Data

## Tóm Tắt

Batch Processing Layer xử lý dữ liệu lịch sử taxi NYC để tạo các aggregation theo ngày, bổ sung cho Speed Layer (real-time streaming) trong kiến trúc Lambda Architecture.

### Những Gì Đã Làm

#### 1. **Thiết Lập HDFS (Ban Đầu)**
- **Vấn đề gặp phải**: Docker image `apache/hadoop:3.2.1` không tồn tại
- **Giải pháp**: Chuyển sang sử dụng `bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8`
- **Kết quả**: HDFS services (namenode, datanode) chạy thành công trên Docker

#### 2. **Upload Dữ Liệu Lên HDFS**
- **File**: `hdfs/upload_to_hdfs.py`
- **Chức năng**: Upload file parquet, convert sang CSV và lưu vào HDFS
- **Kết quả**: 
  - ✅ Upload thành công 3,574,091 records (403.6 MB CSV)
  - ✅ Lưu tại: `/raw/taxi_trips/2025-08.csv` trong HDFS
  - ⏱️ Thời gian: ~10 giây

#### 3. **Gặp Vấn Đề Với HDFS**
- **Lỗi**: `BlockMissingException` - "No live nodes contain block"
- **Nguyên nhân**: 
  - File CSV quá lớn (403 MB)
  - HDFS block replication thất bại
  - Datanode connection không ổn định
- **Quyết định**: Chuyển sang đọc trực tiếp từ parquet file thay vì HDFS

#### 4. **Refactor Batch Processing**
- **File**: `spark/batch_processing.py`
- **Thay đổi**:
  - ❌ Loại bỏ: Đọc CSV từ HDFS qua `hdfs://namenode:9000`
  - ✅ Thay bằng: Đọc trực tiếp từ parquet file (60 MB, nén tốt hơn)
  - ✅ Removed HDFS_URL config khỏi SparkSession
  - ✅ Giữ nguyên logic xử lý và aggregation

#### 5. **Kết Quả Batch Processing**
```
✅ Total records processed: 3,574,091
✅ Records after cleaning: 2,558,256
✅ Daily aggregations created: 7,105
✅ Written to: taxi_streaming.daily_analytics
```

### Kiến Trúc Lambda Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Lambda Architecture                      │
└─────────────────────────────────────────────────────────────┘

[Historical Data]                    [Real-time Data]
      │                                      │
      ▼                                      ▼
┌─────────────┐                    ┌─────────────┐
│ Batch Layer │                    │ Speed Layer │
│             │                    │             │
│ Spark Batch │                    │  Kafka +    │
│ Processing  │                    │  Spark      │
│             │                    │  Streaming  │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │  Daily Aggregations             │  5-min Windows
       │  (trip_date, zone)              │  (window_start, zone)
       │                                  │
       ▼                                  ▼
┌──────────────────────────────────────────────────┐
│              Cassandra Database                  │
│  ┌─────────────────┐    ┌──────────────────┐   │
│  │ daily_analytics │    │ taxi_analytics   │   │
│  │ (Batch View)    │    │ (Real-time View) │   │
│  └─────────────────┘    └──────────────────┘   │
└──────────────────────────────────────────────────┘
                    │
                    ▼
            ┌───────────────┐
            │    Grafana    │
            │   Dashboard   │
            └───────────────┘
```

---

## Hướng Dẫn Sử Dụng

### Prerequisites

- Docker & Docker Compose đang chạy
- Cassandra container đã khởi động
- Python 3.9+ với các thư viện: `pyspark`, `polars`, `pyarrow`
- Apache Spark 3.5.7 đã cài đặt

### 1. Chuẩn Bị Dữ Liệu

Đảm bảo file dữ liệu tồn tại:
```bash
ls -lh data/yellow_tripdata_2025-08.parquet
# Expected: ~60MB parquet file
```

Nếu chưa có, download từ NYC TLC:
```bash
cd data
wget https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2025-08.parquet
```

### 2. Kiểm Tra Cassandra

Đảm bảo bảng `daily_analytics` đã được tạo:
```bash
docker exec cassandra cqlsh -e "DESCRIBE TABLE taxi_streaming.daily_analytics;"
```

Nếu chưa tồn tại, tạo bảng:
```bash
docker exec cassandra cqlsh -f cassandra/init.cql
```

### 3. Chạy Batch Processing

#### Cách 1: Sử dụng Script (Khuyến nghị)
```bash
./run-batch-pipeline.sh
```

#### Cách 2: Chạy Trực Tiếp với Spark-Submit
```bash
cd spark

spark-submit \
  --packages com.datastax.spark:spark-cassandra-connector_2.13:3.5.1 \
  --conf spark.driver.memory=2g \
  --conf spark.executor.memory=2g \
  --conf spark.sql.shuffle.partitions=4 \
  batch_processing.py
```

### 4. Theo Dõi Progress

Spark UI sẽ chạy tại: http://localhost:4041 (hoặc 4042 nếu 4041 đang dùng)

Log output sẽ hiển thị:
- Số lượng records đọc được
- Số records sau khi clean
- Sample aggregations (top 10 rows)
- Số daily aggregations được tạo
- Trạng thái ghi vào Cassandra

### 5. Xác Minh Kết Quả

#### Kiểm tra số lượng records:
```bash
docker exec cassandra cqlsh -e "SELECT COUNT(*) FROM taxi_streaming.daily_analytics;"
# Expected: 7,105 rows
```

#### Xem sample data:
```bash
docker exec cassandra cqlsh -e "SELECT * FROM taxi_streaming.daily_analytics LIMIT 10;"
```

#### Query theo ngày cụ thể:
```bash
docker exec cassandra cqlsh -e "
  SELECT trip_date, pickup_zone, total_trips, total_revenue 
  FROM taxi_streaming.daily_analytics 
  WHERE trip_date = '2025-08-01' 
  ALLOW FILTERING;
"
```

#### Query theo zone:
```bash
docker exec cassandra cqlsh -e "
  SELECT trip_date, total_trips, avg_fare, avg_distance 
  FROM taxi_streaming.daily_analytics 
  WHERE trip_date = '2025-08-15' 
  AND pickup_zone = 'Times Sq/Theatre District' 
  ALLOW FILTERING;
"
```

---

## Chi Tiết Kỹ Thuật

### Input Data
- **Source**: `data/yellow_tripdata_2025-08.parquet`
- **Size**: 60 MB (compressed)
- **Records**: 3,574,091 trips
- **Format**: Parquet with schema:
  - VendorID, tpep_pickup_datetime, tpep_dropoff_datetime
  - PULocationID, DOLocationID
  - passenger_count, trip_distance, fare_amount, total_amount

### Data Processing Pipeline

```python
# 1. Read Parquet
df = spark.read.parquet("../data/yellow_tripdata_2025-08.parquet")

# 2. Data Cleaning
cleaned_df = df.filter(
    (col("trip_distance") > 0) &
    (col("fare_amount") > 0) &
    (col("total_amount") > 0) &
    (col("passenger_count") > 0)
)

# 3. Zone Mapping
zone_df = spark.read.csv("taxi_zone_lookup.csv", header=True)
with_zones = cleaned_df.join(zone_df, 
    cleaned_df.PULocationID == zone_df.LocationID, "left")

# 4. Daily Aggregation
daily_agg = with_zones.groupBy("trip_date", "pickup_zone").agg(
    count("*").alias("total_trips"),
    sum("total_amount").alias("total_revenue"),
    avg("fare_amount").alias("avg_fare"),
    avg("trip_distance").alias("avg_distance"),
    avg("speed_mph").alias("avg_speed"),
    avg("passenger_count").alias("avg_passengers")
)

# 5. Write to Cassandra
daily_agg.write \
    .format("org.apache.spark.sql.cassandra") \
    .options(table="daily_analytics", keyspace="taxi_streaming") \
    .mode("append") \
    .save()
```

### Output Schema

**Table**: `taxi_streaming.daily_analytics`

| Column | Type | Description |
|--------|------|-------------|
| trip_date | date | Ngày của chuyến đi (PRIMARY KEY) |
| pickup_zone | text | Tên khu vực đón khách (PRIMARY KEY) |
| total_trips | bigint | Tổng số chuyến trong ngày |
| total_revenue | double | Tổng doanh thu ($) |
| avg_fare | double | Giá trung bình ($) |
| avg_distance | double | Quãng đường TB (miles) |
| avg_speed | double | Tốc độ TB (mph) |
| avg_passengers | double | Số hành khách TB |

**Partition Key**: `(trip_date, pickup_zone)`
- Cho phép query hiệu quả theo ngày và zone
- Phân phối đều data across Cassandra nodes

---

## Troubleshooting

### Lỗi: "NameError: name 'HDFS_URL' is not defined"
- **Nguyên nhân**: Code cũ còn tham chiếu đến HDFS
- **Giải pháp**: Đã fix trong phiên bản hiện tại, pull latest code

### Lỗi: "Cassandra connection refused"
- **Kiểm tra**: `docker ps | grep cassandra`
- **Khởi động**: `docker-compose up -d cassandra`
- **Đợi**: Cassandra cần ~30s để ready

### Lỗi: "File not found: yellow_tripdata_2025-08.parquet"
- **Kiểm tra path**: File phải ở `data/yellow_tripdata_2025-08.parquet`
- **Relative path**: Script chạy từ `spark/` directory, dùng `../data/`

### Performance Issues
- **Tăng memory**: Sửa `spark.driver.memory` và `spark.executor.memory` trong spark-submit
- **Tăng parallelism**: Sửa `spark.sql.shuffle.partitions` (default: 4)
- **Local mode**: Đang dùng `local[2]` (2 cores), có thể tăng lên `local[*]`

---

## So Sánh: HDFS vs Local Parquet

### HDFS Approach (Đã Thử - Thất Bại)
❌ **Pros**:
- Scalable cho Big Data (PB scale)
- Distributed storage
- Fault tolerance

❌ **Cons**:
- Setup phức tạp với Docker
- Block replication issues với large files
- Datanode connectivity unstable
- Overhead cho dataset nhỏ (<1GB)

### Local Parquet Approach (Đang Dùng)
✅ **Pros**:
- Simple, reliable
- Parquet format: compressed (60MB vs 403MB CSV)
- Columnar storage: fast reading
- No network overhead

✅ **Cons**:
- Không scale cho dataset rất lớn (>100GB)
- Single point of failure (local disk)

**Kết luận**: Với dataset 3.5M records (~60MB), local parquet là lựa chọn tối ưu.

---

## Scheduled Batch Jobs (Tương Lai)

Để chạy batch processing tự động hàng ngày:

### Option 1: Cron Job
```bash
# Add to crontab
0 2 * * * cd /home/ducan/Big-Data-Project && ./run-batch-pipeline.sh >> logs/batch.log 2>&1
```

### Option 2: Apache Airflow
```python
from airflow import DAG
from airflow.operators.bash import BashOperator

dag = DAG('taxi_batch_processing', schedule_interval='@daily')

batch_task = BashOperator(
    task_id='run_batch',
    bash_command='cd /path/to/project && ./run-batch-pipeline.sh',
    dag=dag
)
```

### Option 3: Kubernetes CronJob
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: taxi-batch-processing
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: spark-batch
            image: apache/spark:3.5.7
            command: ["spark-submit", "batch_processing.py"]
```

---

## Monitoring & Metrics

### Spark Metrics
- **Records processed**: 3,574,091
- **Processing time**: ~30-60 seconds
- **Memory usage**: ~2GB driver + 2GB executor
- **Shuffle partitions**: 4

### Cassandra Metrics
```bash
# Check table size
docker exec cassandra nodetool tablestats taxi_streaming.daily_analytics

# Check write throughput
docker exec cassandra nodetool tpstats
```

---

## Next Steps

1. **Incremental Processing**: 
   - Chỉ xử lý dữ liệu mới thay vì toàn bộ dataset
   - Sử dụng watermark/checkpoint

2. **Partitioning**:
   - Partition data theo tháng/năm
   - Giảm thời gian scan cho queries

3. **Grafana Integration**:
   - Tạo dashboard cho batch layer metrics
   - So sánh batch vs real-time aggregations

4. **Data Quality**:
   - Thêm validation rules
   - Logging anomalies
   - Data profiling reports

---

## References

- [Apache Spark Documentation](https://spark.apache.org/docs/latest/)
- [Cassandra Data Modeling](https://cassandra.apache.org/doc/latest/data_modeling/)
- [Lambda Architecture](http://lambda-architecture.net/)
- [NYC TLC Trip Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
