from confluent_kafka import DeserializingConsumer
from confluent_kafka.avro.serializer import SerializerError
from confluent_kafka.serialization import StringDeserializer
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.schema_registry import SchemaRegistryClient
import os
import time

# --- Configuration for Kubernetes ---
SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
SCHEMA_PATH = os.path.join(PROJECT_ROOT, "schemas", "taxi_trip.avsc")

# Use environment variables for Kubernetes service discovery
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry-service:8081")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-broker-service:29092")

print(f"Using Schema Registry: {SCHEMA_REGISTRY_URL}")
print(f"Using Kafka Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}")

# Wait for services to be ready
print("Waiting for services to be ready...")
time.sleep(30)

# 1. Load the Avro schema to be used by the deserializer
with open(SCHEMA_PATH, "r") as f:
    schema_str = f.read()

schema_registry_conf = {'url': SCHEMA_REGISTRY_URL}
schema_registry_client = SchemaRegistryClient(schema_registry_conf)

# 2. Define deserializers for key and value
key_deserializer = StringDeserializer('utf_8')
avro_deserializer = AvroDeserializer(schema_registry_client, schema_str)

# 3. Update the consumer configuration
consumer_config = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'key.deserializer': key_deserializer,
    'value.deserializer': avro_deserializer,
    'group.id': 'taxi-avro-consumer-group-k8s',
    'auto.offset.reset': 'earliest',
}

# 4. Use DeserializingConsumer
consumer = DeserializingConsumer(consumer_config)
consumer.subscribe(['taxi-trips'])

print("Kubernetes AVRO Consumer started. Waiting for messages...")

try:
    message_count = 0
    while True:
        try:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue
            
            value = msg.value()
            message_count += 1
            print(f"Message #{message_count}: key='{msg.key()}', value={value}")

        except SerializerError as e:
            print(f"Message deserialization failed: {e}")
except KeyboardInterrupt:
    print("Stopping consumer.")
finally:
    consumer.close()