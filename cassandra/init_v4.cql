CREATE KEYSPACE IF NOT EXISTS analytics
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE analytics;

-- Average Fare Per Mile by Borough (Dashboard #4)
-- Stores aggregated revenue and distance by borough to calculate fare/mile in Grafana
CREATE TABLE IF NOT EXISTS borough_fare_distance (
    borough TEXT,
    time_bucket TIMESTAMP,
    total_revenue DOUBLE,
    total_distance DOUBLE,
    trip_count BIGINT,
    last_updated TIMESTAMP,
    PRIMARY KEY (borough, time_bucket)
) WITH CLUSTERING ORDER BY (time_bucket DESC)
AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'HOURS',
    'compaction_window_size': '1'
}
AND default_time_to_live = 7776000;  -- 90 days retention