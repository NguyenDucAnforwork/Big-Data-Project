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

taxi_schema = StructType([
    StructField("tpep_pickup_datetime", TimestampType(), True),
    StructField("tpep_dropoff_datetime", TimestampType(), True),
    StructField("trip_distance", DoubleType(), True),
    StructField("PULocationID", IntegerType(), True)
])

def get_spark_session():
    return SparkSession.builder \
        .appName("Average Speed by Borough") \
        .config("spark.driver.memory", "1g") \
        .config("spark.executor.memory", "1g") \
        .config("spark.cassandra.connection.host", CASSANDRA_HOST) \
        .master("local[2]").getOrCreate()

def main():
    spark = get_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    raw_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPIC) \
        .load()

    parsed_df = raw_df.select(
        from_json(col("value").cast("string"), taxi_schema).alias("data")
    ).select("data.*")

    # Calculate duration and filter invalid trips
    df_processed = parsed_df.withColumn(
        "duration_seconds", 
        unix_timestamp("tpep_dropoff_datetime") - unix_timestamp("tpep_pickup_datetime")
    ).filter(
        (col("trip_distance") > 0) & 
        (col("duration_seconds") > 0) & 
        (col("duration_seconds") < 7200) # Filter trips > 2 hours
    )

    # Load zone lookup
    zone_df = spark.read.option("header", "true").option("inferSchema", "true").csv(ZONE_LOOKUP_PATH)
    zone_lookup = zone_df.select(col("LocationID").alias("lid"), col("Borough").alias("borough"), col("Zone").alias("zn"))
    
    df_enriched = df_processed.join(broadcast(zone_lookup), df_processed.PULocationID == zone_lookup.lid, "left")
    
    df_final = df_enriched.withColumn("borough", 
        when(col("zn").contains("Airport"), "Airport")
        .otherwise(col("borough"))
    ).fillna({"borough": "Unknown"})

    # 15-minute window aggregation
    df_windowed = df_final \
        .withWatermark("tpep_pickup_datetime", "10 minutes") \
        .groupBy(col("borough"), window(col("tpep_pickup_datetime"), "15 minutes")) \
        .agg(
            _sum("trip_distance").alias("total_distance"),
            _sum("duration_seconds").alias("total_duration_seconds"),
            count("*").alias("trip_count")
        )

    df_output = df_windowed.select(
        col("borough"),
        col("window.start").alias("time_bucket"),
        "total_distance",
        "total_duration_seconds",
        "trip_count",
        current_timestamp().alias("last_updated")
    )

    def write_to_cassandra(batch_df, batch_id):
        batch_df.write \
            .format("org.apache.spark.sql.cassandra") \
            .mode("append") \
            .options(table="borough_avg_speed", keyspace=CASSANDRA_KEYSPACE) \
            .save()

    query = df_output.writeStream \
        .foreachBatch(write_to_cassandra) \
        .option("checkpointLocation", os.path.join(CHECKPOINT_ROOT, "avg_speed")) \
        .start()

    query.awaitTermination()

if __name__ == "__main__":
    main()