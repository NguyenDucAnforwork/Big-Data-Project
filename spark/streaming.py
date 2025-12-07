import os
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, window, avg, sum as spark_sum, count,
    current_timestamp, when, lit, hour, dayofweek, 
    unix_timestamp, broadcast, round as spark_round
)
from pyspark.sql.types import (
    StructType, StructField, IntegerType, LongType,
    DoubleType, TimestampType, StringType
)


# ---------- Logging Setup ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------- Config ----------
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "taxi-trips")
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "localhost")
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "taxi_streaming")

# Single checkpoint path for single query
CHECKPOINT_ROOT = os.getenv("CHECKPOINT_ROOT", "/tmp/spark_checkpoints")
CHECKPOINT_PATH = os.path.join(CHECKPOINT_ROOT, "taxi_analytics")

# Zone lookup CSV
ZONE_LOOKUP_PATH = os.getenv("ZONE_LOOKUP_PATH", "taxi_zone_lookup.csv")


# ---------- Schemas ----------
taxi_schema = StructType([
    StructField("VendorID", IntegerType(), True),
    StructField("tpep_pickup_datetime", TimestampType(), True),
    StructField("tpep_dropoff_datetime", TimestampType(), True),
    StructField("passenger_count", LongType(), True),
    StructField("trip_distance", DoubleType(), True),
    StructField("RatecodeID", LongType(), True),
    StructField("store_and_fwd_flag", StringType(), True),
    StructField("PULocationID", IntegerType(), True),
    StructField("DOLocationID", IntegerType(), True),
    StructField("payment_type", LongType(), True),
    StructField("fare_amount", DoubleType(), True),
    StructField("extra", DoubleType(), True),
    StructField("mta_tax", DoubleType(), True),
    StructField("tip_amount", DoubleType(), True),
    StructField("tolls_amount", DoubleType(), True),
    StructField("improvement_surcharge", DoubleType(), True),
    StructField("total_amount", DoubleType(), True),
    StructField("congestion_surcharge", DoubleType(), True),
    StructField("Airport_fee", DoubleType(), True),
    StructField("cbd_congestion_fee", DoubleType(), True)
])

zone_schema = StructType([
    StructField("LocationID", IntegerType(), True),
    StructField("Borough", StringType(), True),
    StructField("Zone", StringType(), True),
    StructField("service_zone", StringType(), True)
])


# ---------- Spark Session ----------
spark = (
    SparkSession.builder
    .appName("NYC Taxi Analytics Stream")
    .config("spark.cassandra.connection.host", CASSANDRA_HOST)
    .config("spark.cassandra.connection.port", "9042")
    .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_PATH)
    .config("spark.sql.shuffle.partitions", "2")
    # Memory optimizations
    .config("spark.driver.memory", "1g")
    .config("spark.executor.memory", "1g")
    .config("spark.memory.fraction", "0.8")
    .config("spark.memory.storageFraction", "0.3")
    # Streaming optimizations
    .config("spark.sql.streaming.stateStore.providerClass", 
            "org.apache.spark.sql.execution.streaming.state.HDFSBackedStateStoreProvider")
    .config("spark.sql.streaming.minBatchesToRetain", "2")
    .master("local[2]")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")


# ---------- Read from Kafka ----------
kafka_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
    .option("subscribe", KAFKA_TOPIC)
    .option("startingOffsets", "earliest")
    .option("maxOffsetsPerTrigger", "100")  # Rate limiting
    .option("failOnDataLoss", "false")
    .load()
)

# Parse JSON payload
parsed_df = kafka_df.select(
    from_json(col("value").cast("string"), taxi_schema).alias("data"),
    col("timestamp").alias("kafka_timestamp")
).select("data.*", "kafka_timestamp")


# ---------- Data Cleaning & Pre-processing ----------
df_with_duration = parsed_df.withColumn(
    "trip_duration_sec", 
    (unix_timestamp("tpep_dropoff_datetime") - unix_timestamp("tpep_pickup_datetime"))
)

cleaned_df = df_with_duration.filter(
    (col("trip_distance") > 0) &
    (col("trip_distance") < 100) &
    (col("fare_amount") >= 0) &
    (col("fare_amount") < 500) &
    (col("passenger_count") > 0) &
    (col("passenger_count") < 10) &
    (col("trip_duration_sec") > 60) &
    (col("trip_duration_sec") < 14400) &
    (col("PULocationID").isNotNull()) &
    (col("PULocationID") < 264) &
    (col("total_amount").isNotNull())
)


# ---------- Feature Engineering ----------
# 1. Event time
df_with_time = cleaned_df.withColumn(
    "event_time",
    when(col("tpep_pickup_datetime").isNotNull(), col("tpep_pickup_datetime"))
    .otherwise(col("kafka_timestamp"))
)

# Watermark
watermarked = df_with_time.withWatermark("event_time", "10 minutes")

# 2. Derived Features
enriched_df = watermarked.withColumn(
    "pickup_hour", hour("event_time")
).withColumn(
    "pickup_weekday", dayofweek("event_time") 
).withColumn(
    "is_weekend", 
    col("pickup_weekday").isin([1, 2]) # 1=Sunday, 7=Saturday (Spark default). 
    # NOTE: Spark dayofweek: 1=Sunday, 2=Monday... 7=Saturday. 
    # If you want Sat/Sun as weekend, check logic: isin([1, 7]). 
    # Assuming standard business logic (Sat=7, Sun=1).
).withColumn(
    "speed_mph",
    when(col("trip_duration_sec") > 0, 
         (col("trip_distance") / (col("trip_duration_sec") / 3600)))
    .otherwise(lit(0.0))
).withColumn(
    "tip_ratio",
    when(col("total_amount") > 0, 
         (col("tip_amount") / col("total_amount")))
    .otherwise(lit(0.0))
).withColumn(
    "fare_per_mile",
    when(col("trip_distance") > 0,
         (col("fare_amount") / col("trip_distance")))
    .otherwise(lit(0.0))
)

enriched_df = enriched_df.withColumn(
    "distance_category",
    when(col("trip_distance") < 2.0, lit("Short"))
    .when(col("trip_distance") < 10.0, lit("Medium"))
    .otherwise(lit("Long"))
).withColumn(
    "peak_category",
    when((~col("is_weekend")) & (col("pickup_hour").between(16, 20)), lit("PM_Rush"))
    .when((~col("is_weekend")) & (col("pickup_hour").between(7, 10)), lit("AM_Rush"))
    .otherwise(lit("Off_Peak"))
)


# ---------- Load Static Data (Broadcast Join) ----------
try:
    # Use the defined schema
    zone_df = spark.read.schema(zone_schema).option("header", "true").csv(ZONE_LOOKUP_PATH)
    zone_lookup = zone_df.select(
        col("LocationID").alias("lookup_PULocationID"),
        col("Zone").alias("pickup_zone")
    )
except Exception as e:
    logger.warning(f"Could not load zone lookup file: {e}. Zone enrichment will be skipped.")
    zone_lookup = None

if zone_lookup:
    final_stream = enriched_df.join(
        broadcast(zone_lookup),
        enriched_df.PULocationID == zone_lookup.lookup_PULocationID,
        "left"
    ).drop("lookup_PULocationID")
else:
    # Fallback if CSV missing
    final_stream = enriched_df.withColumn("pickup_zone", lit("Unknown"))


# ---------- SINGLE Unified Aggregation ----------
# Combine all metrics into ONE query to avoid state management conflicts

unified_agg = final_stream \
    .groupBy(
        window(col("event_time"), "5 minutes"),
        col("pickup_zone"),
        col("peak_category"),
        col("payment_type"),
        col("distance_category")
    ) \
    .agg(
        count("*").alias("total_trips"),
        spark_sum("total_amount").alias("total_revenue"),
        avg("trip_distance").alias("avg_distance"),
        avg("fare_amount").alias("avg_fare"),
        avg("fare_per_mile").alias("avg_fare_per_mile"),
        avg("tip_ratio").alias("avg_tip_ratio"),
        avg("speed_mph").alias("avg_speed"),
        avg("trip_duration_sec").alias("avg_duration_sec"),
        avg("passenger_count").alias("avg_occupancy")
    ) \
    .select(
        col("window.start").alias("window_start"),
        col("window.end").alias("window_end"),
        "pickup_zone",
        "peak_category",
        "payment_type",
        "distance_category",
        "total_trips",
        "total_revenue",
        "avg_distance",
        "avg_fare",
        "avg_fare_per_mile",
        "avg_tip_ratio",
        "avg_speed",
        "avg_duration_sec",
        "avg_occupancy"
    )


# ---------- Sink to Cassandra ----------
def write_to_cassandra(batch_df, batch_id):
    """Write aggregated metrics to Cassandra unified table"""
    if batch_df.rdd.isEmpty():
        logger.info(f"Batch {batch_id}: No data to write")
        return
    
    try:
        logger.info(f"Batch {batch_id}: Writing {batch_df.count()} records to taxi_analytics")
        
        batch_df.write \
            .format("org.apache.spark.sql.cassandra") \
            .mode("append") \
            .options(table="taxi_analytics", keyspace=CASSANDRA_KEYSPACE) \
            .save()
        
        logger.info(f"Batch {batch_id}: Successfully written to Cassandra")
    except Exception as e:
        logger.error(f"Batch {batch_id}: Error writing to Cassandra: {e}")

# ---------- Start Single Streaming Query ----------
print("=" * 60)
print("Starting NYC Taxi Analytics Streaming Pipeline")
print("=" * 60)
print(f"Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
print(f"Cassandra: {CASSANDRA_HOST}")
print(f"Checkpoint: {CHECKPOINT_PATH}")
print("=" * 60)

query = (
    unified_agg.writeStream
    .trigger(processingTime='10 seconds')
    .outputMode("update")
    .foreachBatch(write_to_cassandra)
    .option("checkpointLocation", CHECKPOINT_PATH)
    .start()
)

print("\n✓ Streaming query started successfully!")
print("✓ Processing taxi trips every 10 seconds")
print("✓ Press Ctrl+C to stop\n")

# ---------- Execution ----------
try:
    query.awaitTermination()
except KeyboardInterrupt:
    print("\n\nStopping streaming pipeline...")
    query.stop()
    spark.stop()
    print("Pipeline stopped successfully!")