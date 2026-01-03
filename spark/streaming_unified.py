import os
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, sum as _sum, count, current_timestamp, window,
    when, lit, broadcast, unix_timestamp
)
from pyspark.sql.types import (
    StructType, StructField, IntegerType, LongType,
    DoubleType, TimestampType, StringType
)

# ---------- Config ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "broker:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "taxi-trips")
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "localhost")
CASSANDRA_KEYSPACE = "analytics"
CHECKPOINT_ROOT = os.getenv("CHECKPOINT_ROOT", "/tmp/spark_checkpoints")

SCRIPT_DIR = os.path.dirname(__file__)
ZONE_LOOKUP_PATH = os.path.join(SCRIPT_DIR, "taxi_zone_lookup.csv")

# ---------- Schema ----------
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

def get_spark_session():
    return SparkSession.builder \
        .appName("NYC Taxi Unified Pipeline") \
        .config("spark.driver.memory", "1g") \
        .config("spark.executor.memory", "1g") \
        .config("spark.sql.shuffle.partitions", "2") \
        .config("spark.default.parallelism", "2") \
        .config("spark.streaming.kafka.maxRatePerPartition", "100") \
        .config("spark.cassandra.connection.host", CASSANDRA_HOST) \
        .config("spark.cassandra.connection.port", "9042") \
        .master("local[2]").getOrCreate()

def main():
    spark = get_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # 1. Read from Kafka
    raw_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()

    # 2. Parse JSON
    parsed_df = raw_df.select(
        from_json(col("value").cast("string"), taxi_schema).alias("data"),
        col("timestamp").alias("kafka_timestamp")
    ).select("data.*", "kafka_timestamp")

    # 3. Use pickup time as event time
    df_with_time = parsed_df.withColumn(
        "event_time",
        when(col("tpep_pickup_datetime").isNotNull(), col("tpep_pickup_datetime"))
        .otherwise(col("kafka_timestamp"))
    )

    # 4. Load zone lookup
    try:
        zone_df = spark.read.option("header", "true").option("inferSchema", "true").csv(ZONE_LOOKUP_PATH)
        zone_lookup = zone_df.select(
            col("LocationID").cast("int").alias("lid"),
            col("Zone").alias("zone_name"),
            col("Borough").alias("borough")
        )
        
        df_enriched = df_with_time.join(
            broadcast(zone_lookup),
            df_with_time.PULocationID == zone_lookup.lid,
            "left"
        ).drop("lid")
    except Exception as e:
        logger.warning(f"Zone lookup failed: {e}")
        df_enriched = df_with_time.withColumn("zone_name", lit("Unknown")).withColumn("borough", lit("Unknown"))

    # ========== DASHBOARD #1: Top Zones by Revenue (streaming_v3.py) ==========
    df_v3 = df_enriched.withColumn(
        "zone",
        when(col("zone_name").isNotNull(), col("zone_name"))
        .otherwise(lit("Unknown"))
    )
    
    df_v3_windowed = df_v3 \
        .withWatermark("event_time", "10 minutes") \
        .groupBy(col("zone"), window(col("event_time"), "30 minutes")) \
        .agg(_sum("total_amount").alias("total_revenue"), count("*").alias("trip_count"))
    
    df_v3_output = df_v3_windowed.select(
        col("zone"),
        col("window.start").alias("time_bucket"),
        col("total_revenue"),
        col("trip_count"),
        current_timestamp().alias("last_updated")
    )

    # ========== DASHBOARD #2: Trip Demand by Zone (streaming_v2.py) ==========
    df_v2 = df_enriched.withColumn(
        "zone",
        when(col("zone_name").contains("Airport"), "Airport")
        .when(col("borough") == "Manhattan", "Manhattan")
        .when(col("borough") == "Queens", "Queens")
        .when(col("borough") == "Brooklyn", "Brooklyn")
        .when(col("borough") == "Bronx", "Bronx")
        .when(col("borough") == "Staten Island", "Staten Island")
        .otherwise("Unknown")
    )
    
    df_v2_windowed = df_v2 \
        .withWatermark("event_time", "10 minutes") \
        .groupBy(col("zone"), window(col("event_time"), "5 minutes")) \
        .agg(count("*").alias("trip_count"))
    
    df_v2_output = df_v2_windowed.select(
        col("zone"),
        col("window.start").alias("time_bucket"),
        col("trip_count")
    )

    # ========== DASHBOARD #4: Avg Fare Per Mile by Borough (streaming_v4.py) ==========
    df_v4 = df_enriched.filter(
        (col("total_amount") > 0) & 
        (col("trip_distance") > 0) &
        (col("total_amount") < 1000)
    ).withColumn(
        "borough",
        when(col("zone_name").contains("Airport"), "Airport")
        .when(col("borough") == "Manhattan", "Manhattan")
        .when(col("borough") == "Queens", "Queens")
        .when(col("borough") == "Brooklyn", "Brooklyn")
        .when(col("borough") == "Bronx", "Bronx")
        .when(col("borough") == "Staten Island", "Staten Island")
        .when(col("borough") == "EWR", "EWR")
        .otherwise("Unknown")
    )
    
    df_v4_windowed = df_v4 \
        .withWatermark("event_time", "10 minutes") \
        .groupBy(col("borough"), window(col("event_time"), "30 minutes")) \
        .agg(
            _sum("total_amount").alias("total_revenue"),
            _sum("trip_distance").alias("total_distance"),
            count("*").alias("trip_count")
        )
    
    df_v4_output = df_v4_windowed.select(
        col("borough"),
        col("window.start").alias("time_bucket"),
        col("total_revenue"),
        col("total_distance"),
        col("trip_count"),
        current_timestamp().alias("last_updated")
    )

    # ========== DASHBOARD #5: Avg Speed by Borough (streaming_v5.py) ==========
    df_v5 = df_enriched.withColumn(
        "duration_seconds", 
        unix_timestamp("tpep_dropoff_datetime") - unix_timestamp("tpep_pickup_datetime")
    ).filter(
        (col("trip_distance") > 0) & 
        (col("duration_seconds") > 0) & 
        (col("duration_seconds") < 7200)
    ).withColumn(
        "borough", 
        when(col("zone_name").contains("Airport"), "Airport")
        .otherwise(col("borough"))
    ).fillna({"borough": "Unknown"})
    
    df_v5_windowed = df_v5 \
        .withWatermark("event_time", "10 minutes") \
        .groupBy(col("borough"), window(col("event_time"), "15 minutes")) \
        .agg(
            _sum("trip_distance").alias("total_distance"),
            _sum("duration_seconds").alias("total_duration_seconds"),
            count("*").alias("trip_count")
        )
    
    df_v5_output = df_v5_windowed.select(
        col("borough"),
        col("window.start").alias("time_bucket"),
        col("total_distance"),
        col("total_duration_seconds"),
        col("trip_count"),
        current_timestamp().alias("last_updated")
    )

    # ========== WRITE FUNCTIONS ==========
    def write_v3(batch_df, batch_id):
        if not batch_df.rdd.isEmpty():
            logger.info(f"[V3] Batch {batch_id}: Writing {batch_df.count()} records")
            batch_df.write.format("org.apache.spark.sql.cassandra") \
                .mode("append").options(table="zones_revenue_by_window", keyspace=CASSANDRA_KEYSPACE).save()

    def write_v2(batch_df, batch_id):
        if not batch_df.rdd.isEmpty():
            logger.info(f"[V2] Batch {batch_id}: Writing {batch_df.count()} records")
            batch_df.write.format("org.apache.spark.sql.cassandra") \
                .mode("append").options(table="trip_demand_by_zone_5m", keyspace=CASSANDRA_KEYSPACE).save()

    def write_v4(batch_df, batch_id):
        if not batch_df.rdd.isEmpty():
            logger.info(f"[V4] Batch {batch_id}: Writing {batch_df.count()} records")
            batch_df.write.format("org.apache.spark.sql.cassandra") \
                .mode("append").options(table="borough_fare_distance", keyspace=CASSANDRA_KEYSPACE).save()

    def write_v5(batch_df, batch_id):
        if not batch_df.rdd.isEmpty():
            logger.info(f"[V5] Batch {batch_id}: Writing {batch_df.count()} records")
            batch_df.write.format("org.apache.spark.sql.cassandra") \
                .mode("append").options(table="borough_avg_speed", keyspace=CASSANDRA_KEYSPACE).save()

    # ========== START ALL STREAMS ==========
    query_v3 = df_v3_output.writeStream \
        .foreachBatch(write_v3) \
        .option("checkpointLocation", os.path.join(CHECKPOINT_ROOT, "zones_revenue_window")) \
        .trigger(processingTime="10 seconds") \
        .start()

    query_v2 = df_v2_output.writeStream \
        .foreachBatch(write_v2) \
        .option("checkpointLocation", os.path.join(CHECKPOINT_ROOT, "trip_demand_5m")) \
        .trigger(processingTime="10 seconds") \
        .start()

    query_v4 = df_v4_output.writeStream \
        .foreachBatch(write_v4) \
        .option("checkpointLocation", os.path.join(CHECKPOINT_ROOT, "borough_fare_distance")) \
        .trigger(processingTime="10 seconds") \
        .start()

    query_v5 = df_v5_output.writeStream \
        .foreachBatch(write_v5) \
        .option("checkpointLocation", os.path.join(CHECKPOINT_ROOT, "avg_speed")) \
        .trigger(processingTime="10 seconds") \
        .start()

    logger.info("All 4 streaming pipelines started...")
    query_v3.awaitTermination()

if __name__ == "__main__":
    main()