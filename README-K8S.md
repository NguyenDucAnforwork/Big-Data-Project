# Big Data Kafka Project - Kubernetes Deployment Guide

## 📋 Tổng quan

Dự án này triển khai hệ thống Kafka với Schema Registry và các ứng dụng Python Producer/Consumer trên Kubernetes cluster.

## 🏗️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌───────────────────┐                │
│  │   Kafka Broker  │  │  Schema Registry  │                │
│  │   Port: 9092    │  │    Port: 8081     │                │
│  │   (NodePort:    │  │   (NodePort:      │                │
│  │    30092)       │  │    30081)         │                │
│  └─────────────────┘  └───────────────────┘                │
│           │                      │                          │
│           │                      │                          │
│  ┌─────────────────┐  ┌───────────────────┐                │
│  │    Producer     │  │     Consumer      │                │
│  │     (Job)       │  │   (Deployment)    │                │
│  └─────────────────┘  └───────────────────┘                │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┤
│  │            Persistent Volume (Kafka Data)              │
│  └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Yêu cầu hệ thống

- **Kubernetes cluster** (Docker Desktop Kubernetes, Minikube, hoặc cloud)
- **kubectl** CLI tool
- **Docker** (để build images)
- **kustomize** (tùy chọn, đã tích hợp sẵn trong kubectl)

## 📦 Cấu trúc project

```
k8s/
├── README-K8S.md                 # File này
├── namespace.yaml                # Namespace cho project
├── kustomization.yaml           # Kustomize configuration
├── storage/
│   └── persistent-volumes.yaml # PV và PVC cho Kafka
├── kafka/
│   ├── kafka-deployment.yaml   # Kafka broker deployment
│   └── kafka-service.yaml      # Kafka services
├── schema-registry/
│   ├── schema-registry-deployment.yaml
│   └── schema-registry-service.yaml
└── apps/
    ├── Dockerfile.producer      # Producer container
    ├── Dockerfile.consumer      # Consumer container
    ├── producer-k8s.py         # Producer app cho K8s
    ├── consumer-k8s.py         # Consumer app cho K8s
    ├── producer-job.yaml       # Producer job
    └── consumer-deployment.yaml # Consumer deployment
```

## 🚀 Hướng dẫn triển khai

### 1. Chuẩn bị môi trường

```powershell
# Đảm bảo kubectl đã kết nối với cluster
kubectl cluster-info

# Chuyển đến thư mục k8s
cd k8s
```

### 2. Build Docker Images

```powershell
# Chuyển về thư mục root của project
cd ..

# Build Producer image
docker build -f k8s/apps/Dockerfile.producer -t kafka-producer:latest .

# Build Consumer image
docker build -f k8s/apps/Dockerfile.consumer -t kafka-consumer:latest .

# Verify images
docker images | findstr kafka
```

### 3. Deploy lên Kubernetes

#### Option A: Sử dụng Kustomize (Khuyến nghị)

```powershell
# Deploy toàn bộ stack
kubectl apply -k k8s/

# Verify deployment
kubectl get all -n big-data-kafka
```

#### Option B: Deploy từng component

```powershell
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Create storage
kubectl apply -f k8s/storage/persistent-volumes.yaml

# 3. Deploy Kafka
kubectl apply -f k8s/kafka/

# 4. Deploy Schema Registry
kubectl apply -f k8s/schema-registry/

# 5. Deploy applications
kubectl apply -f k8s/apps/
```

### 4. Kiểm tra triển khai

```powershell
# Xem tất cả resources
kubectl get all -n big-data-kafka

# Xem trạng thái pods
kubectl get pods -n big-data-kafka -w

# Xem services và endpoints
kubectl get svc -n big-data-kafka

# Xem persistent volumes
kubectl get pv,pvc -n big-data-kafka
```

### 5. Tạo Kafka topic

```powershell
# Exec vào Kafka pod
kubectl exec -it -n big-data-kafka deployment/kafka-broker -- /bin/bash

# Trong container Kafka
cd /opt/kafka/bin
./kafka-topics.sh --create --topic taxi-trips --bootstrap-server localhost:29092 --partitions 3 --replication-factor 1

# Verify topic
./kafka-topics.sh --list --bootstrap-server localhost:29092

# Exit container
exit
```

### 6. Chạy Producer và Consumer

```powershell
# Chạy Producer job
kubectl apply -f k8s/apps/producer-job.yaml

# Consumer đã tự động chạy như deployment
# Xem logs của consumer
kubectl logs -n big-data-kafka deployment/kafka-consumer -f

# Xem logs của producer job
kubectl logs -n big-data-kafka job/kafka-producer -f
```

## 📊 Monitoring và Debugging

### Xem logs

```powershell
# Kafka broker logs
kubectl logs -n big-data-kafka deployment/kafka-broker -f

# Schema Registry logs
kubectl logs -n big-data-kafka deployment/schema-registry -f

# Producer logs
kubectl logs -n big-data-kafka job/kafka-producer -f

# Consumer logs
kubectl logs -n big-data-kafka deployment/kafka-consumer -f
```

### Port forwarding để truy cập từ local

```powershell
# Kafka (port 9092)
kubectl port-forward -n big-data-kafka svc/kafka-external-service 9092:9092

# Schema Registry (port 8081)
kubectl port-forward -n big-data-kafka svc/schema-registry-external-service 8081:8081
```

### Kiểm tra kết nối

```powershell
# Test Schema Registry
curl http://localhost:30081/subjects

# Hoặc với port-forward
curl http://localhost:8081/subjects
```

## 🔧 Troubleshooting

### Các vấn đề thường gặp

1. **Pods không start được**
   ```powershell
   kubectl describe pod <pod-name> -n big-data-kafka
   kubectl logs <pod-name> -n big-data-kafka
   ```

2. **Services không kết nối được**
   ```powershell
   kubectl get endpoints -n big-data-kafka
   kubectl describe svc <service-name> -n big-data-kafka
   ```

3. **Storage issues**
   ```powershell
   kubectl get pv,pvc -n big-data-kafka
   kubectl describe pvc kafka-pvc -n big-data-kafka
   ```

4. **Images không tìm thấy**
   - Đảm bảo đã build images với tag đúng
   - Sử dụng `imagePullPolicy: Never` cho local images

### Lệnh hữu ích

```powershell
# Restart deployment
kubectl rollout restart deployment/<deployment-name> -n big-data-kafka

# Scale deployment
kubectl scale deployment kafka-consumer --replicas=2 -n big-data-kafka

# Delete và recreate job
kubectl delete job kafka-producer -n big-data-kafka
kubectl apply -f k8s/apps/producer-job.yaml
```

## 🧹 Cleanup

### Xóa toàn bộ deployment

```powershell
# Sử dụng kustomize
kubectl delete -k k8s/

# Hoặc xóa namespace (sẽ xóa tất cả)
kubectl delete namespace big-data-kafka
```

### Xóa từng component

```powershell
kubectl delete -f k8s/apps/
kubectl delete -f k8s/schema-registry/
kubectl delete -f k8s/kafka/
kubectl delete -f k8s/storage/
kubectl delete -f k8s/namespace.yaml
```

## 🔄 Scaling và Production

### Horizontal scaling

```powershell
# Scale consumer
kubectl scale deployment kafka-consumer --replicas=3 -n big-data-kafka

# Scale Kafka (cần cấu hình cluster mode)
kubectl scale deployment kafka-broker --replicas=3 -n big-data-kafka
```

### Resource limits

Các file deployment đã có resource requests và limits:
- **Kafka**: 512Mi-1Gi RAM, 250m-500m CPU
- **Schema Registry**: 256Mi-512Mi RAM, 100m-250m CPU  
- **Apps**: 256Mi-512Mi RAM, 100m-200m CPU

### Production considerations

1. **Persistent Storage**: Sử dụng storage class phù hợp cho production
2. **Security**: Implement RBAC, NetworkPolicies
3. **Monitoring**: Thêm Prometheus metrics, Grafana dashboards
4. **Backup**: Backup Kafka data và Schema Registry
5. **High Availability**: Multi-node Kafka cluster với replication

## 📞 Hỗ trợ

Nếu gặp vấn đề, hãy kiểm tra:
1. Logs của các pods
2. Network connectivity giữa services
3. Resource availability
4. Image pull policies

---

*Tài liệu này hướng dẫn deploy Big Data Kafka project lên Kubernetes cluster một cách hoàn chỉnh.*