CREATE KEYSPACE IF NOT EXISTS analytics
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE analytics;

-- Operational Efficiency: Average Speed by Borough (Dashboard #5)
CREATE TABLE IF NOT EXISTS borough_avg_speed (
    borough TEXT,
    time_bucket TIMESTAMP,
    total_distance DOUBLE,
    total_duration_seconds DOUBLE,
    trip_count BIGINT,
    last_updated TIMESTAMP,
    PRIMARY KEY (borough, time_bucket)
) WITH CLUSTERING ORDER BY (time_bucket DESC)
AND default_time_to_live = 7776000;  -- 90 days retention