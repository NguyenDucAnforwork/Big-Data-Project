# 🚀 NYC Taxi Analytics - Quick Start

## Khởi động Pipeline (1 lệnh)

```bash
./start-pipeline.sh
```

**Đợi 2-3 phút** cho đến khi thấy: `Pipeline is ready for demo! 🚀`

---

## Chạy Demo

### 1. Start Producer (Terminal mới)

```bash
uv run python kafka/producer.py
```

Sẽ stream 1000 records (~50 giây)

### 2. Kiểm tra dữ liệu

```bash
# Đếm số records trong Cassandra
./query-cassandra.sh count

# Xem dữ liệu gần đây
./query-cassandra.sh recent

# Top zones theo revenue
./query-cassandra.sh zones
```

### 3. Xem Dashboard

Mở trình duyệt: http://localhost:3000

- **User:** admin
- **Pass:** admin

---

## Dừng Pipeline

```bash
./stop-pipeline.sh
```

---

## Nếu có lỗi

### Cassandra không connect được

```bash
docker exec cassandra nodetool status
docker cp cassandra/init.cql cassandra:/tmp/init.cql
docker exec cassandra cqlsh -f /tmp/init.cql
```

### Grafana không login được

```bash
docker compose down
docker volume rm big-data-project_grafana_data
./start-pipeline.sh
```

### Spark bị crash

```bash
# Xóa checkpoints
rm -rf /tmp/spark_checkpoints/*

# Restart Spark
pkill -f spark-submit
./start-pipeline.sh
```

---

## Monitoring

```bash
# Spark logs
tail -f spark_streaming.log

# Kafka messages
docker exec broker kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic taxi-trips --max-messages 5

# Docker resource usage
docker stats --no-stream
```

---

## Kiến trúc

```
Parquet Data → Producer → Kafka → Spark Streaming → Cassandra → Grafana
```

- **Window:** 5 phút
- **Metrics:** 9 aggregations
- **Latency:** < 30 giây

📖 **Chi tiết:** Xem `DEMO-GUIDE.md`
