-- Initialize Cassandra keyspace and tables for NYC Taxi Trip pipeline

CREATE KEYSPACE IF NOT EXISTS taxi_streaming
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE taxi_streaming;

-- Table for hourly aggregations (NEEDED FOR PANELS 1 & 2)
CREATE TABLE IF NOT EXISTS trip_aggregations_hourly (
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    total_trips BIGINT,
    total_revenue DOUBLE,
    avg_passengers DOUBLE,
    PRIMARY KEY (window_start)
) WITH CLUSTERING ORDER BY (window_start DESC);

-- 1. Demand & Revenue Table (UPDATED for panel queries)
CREATE TABLE IF NOT EXISTS demand_dynamics (
    pickup_zone TEXT,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    peak_category TEXT,
    total_trips BIGINT,
    total_revenue DOUBLE,
    avg_distance DOUBLE,
    avg_fare_per_mile DOUBLE,
    avg_tip_ratio DOUBLE,
    PRIMARY KEY ((pickup_zone), window_start, peak_category)
) WITH CLUSTERING ORDER BY (window_start DESC);

-- 2. Operational Efficiency Table
CREATE TABLE IF NOT EXISTS operational_efficiency (
    pickup_zone TEXT,
    window_start TIMESTAMP,
    avg_speed DOUBLE,
    avg_duration_sec DOUBLE,
    avg_occupancy DOUBLE,
    PRIMARY KEY ((pickup_zone), window_start)
) WITH CLUSTERING ORDER BY (window_start DESC);

-- 3. Rider Behavior Table
CREATE TABLE IF NOT EXISTS rider_behavior (
    payment_type BIGINT,
    window_start TIMESTAMP,
    distance_category TEXT,
    total_trips BIGINT,
    avg_tip_ratio DOUBLE,
    PRIMARY KEY ((payment_type), window_start, distance_category)
) WITH CLUSTERING ORDER BY (window_start DESC);

-- Table for 5-minute aggregations (for vendor_id variable)
CREATE TABLE IF NOT EXISTS trip_aggregations_5min (
    vendor_id INT,
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    trip_count BIGINT,
    avg_passenger_count DOUBLE,
    total_revenue DOUBLE,
    avg_fare DOUBLE,
    PRIMARY KEY ((vendor_id), window_start)
) WITH CLUSTERING ORDER BY (window_start DESC);