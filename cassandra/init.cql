-- Initialize Cassandra keyspace and tables for NYC Taxi Trip pipeline

-- Create keyspace
CREATE KEYSPACE IF NOT EXISTS taxi_streaming
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

-- Use keyspace
USE taxi_streaming;

-- UNIFIED ANALYTICS TABLE
-- Single table storing all aggregated metrics for taxi trips
-- Optimized for time-series queries and multi-dimensional analysis
CREATE TABLE IF NOT EXISTS taxi_analytics (
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    pickup_zone TEXT,
    peak_category TEXT,
    payment_type BIGINT,
    distance_category TEXT,
    total_trips BIGINT,
    total_revenue DOUBLE,
    avg_distance DOUBLE,
    avg_fare DOUBLE,
    avg_fare_per_mile DOUBLE,
    avg_tip_ratio DOUBLE,
    avg_speed DOUBLE,
    avg_duration_sec DOUBLE,
    avg_occupancy DOUBLE,
    PRIMARY KEY ((pickup_zone, peak_category), window_start, payment_type, distance_category)
) WITH CLUSTERING ORDER BY (window_start DESC)
  AND compaction = {'class': 'TimeWindowCompactionStrategy'}
  AND default_time_to_live = 2592000;  -- 30 days retention
