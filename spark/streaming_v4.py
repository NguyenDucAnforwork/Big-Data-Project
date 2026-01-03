import os
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, sum as _sum, count, current_timestamp, window,
    when, lit, broadcast, coalesce
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
        .appName("Average Fare Per Mile by Zone") \
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

    # 3. Use pickup time as event time, handle nulls
    df_with_time = parsed_df.withColumn(
        "event_time",
        when(col("tpep_pickup_datetime").isNotNull(), col("tpep_pickup_datetime"))
        .otherwise(col("kafka_timestamp"))
    )
    
    # 4. Filter invalid data (negative amounts, zero distance, etc.)
    df_filtered = df_with_time.filter(
        (col("total_amount") > 0) & 
        (col("trip_distance") > 0) &
        (col("total_amount") < 1000)  # Remove outliers
    )

    # 5. Load zone lookup and categorize by borough
    try:
        zone_df = spark.read.option("header", "true").option("inferSchema", "true").csv(ZONE_LOOKUP_PATH)
        zone_lookup = zone_df.select(
            col("LocationID").cast("int").alias("lid"),
            col("Zone").alias("zone_name"),
            col("Borough").alias("borough")
        )
        
        df_enriched = df_filtered.join(
            broadcast(zone_lookup),
            df_filtered.PULocationID == zone_lookup.lid,
            "left"
        ).drop("lid")
        
        # Categorize by borough (aggregate to ~7 categories instead of 260+ zones)
        df_enriched = df_enriched.withColumn(
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
    except Exception as e:
        logger.warning(f"Zone lookup failed: {e}")
        df_enriched = df_filtered.withColumn("borough", lit("Unknown"))

    # 6. Apply watermark and 30-minute window aggregation by borough
    df_windowed = df_enriched \
        .withWatermark("event_time", "10 minutes") \
        .groupBy(
            col("borough"),
            window(col("event_time"), "30 minutes")
        ) \
        .agg(
            _sum("total_amount").alias("total_revenue"),
            _sum("trip_distance").alias("total_distance"),
            count("*").alias("trip_count")
        )

    # 7. Prepare for Cassandra write
    df_output = df_windowed.select(
        col("borough"),
        col("window.start").alias("time_bucket"),
        col("total_revenue"),
        col("total_distance"),
        col("trip_count"),
        current_timestamp().alias("last_updated")
    )

    # 8. Write to Cassandra
    def write_to_cassandra(batch_df, batch_id):
        if batch_df.rdd.isEmpty():
            logger.info(f"Batch {batch_id}: Empty, skipping")
            return
        
        count = batch_df.count()
        logger.info(f"Batch {batch_id}: Writing {count} borough-window records to Cassandra")
        batch_df.show(10, truncate=False)
        
        try:
            batch_df.write \
                .format("org.apache.spark.sql.cassandra") \
                .mode("append") \
                .options(table="borough_fare_distance", keyspace=CASSANDRA_KEYSPACE) \
                .save()
            logger.info(f"Batch {batch_id}: Successfully wrote to Cassandra")
        except Exception as e:
            logger.error(f"Batch {batch_id}: Failed - {e}")

    query = df_output.writeStream \
        .foreachBatch(write_to_cassandra) \
        .option("checkpointLocation", os.path.join(CHECKPOINT_ROOT, "borough_fare_distance")) \
        .trigger(processingTime="10 seconds") \
        .start()

    logger.info("Average Fare Per Mile by Borough streaming started...")
    query.awaitTermination()

if __name__ == "__main__":
    main()