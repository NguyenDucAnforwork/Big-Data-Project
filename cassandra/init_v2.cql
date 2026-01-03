CREATE KEYSPACE IF NOT EXISTS analytics
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE analytics;

-- Trip Demand by Zone (Dashboard #2)
-- Query pattern: SELECT time_bucket, trip_count FROM trip_demand_by_zone WHERE zone = ? AND time_bucket >= ? AND time_bucket <= ?
CREATE TABLE IF NOT EXISTS trip_demand_by_zone_5m (
    zone TEXT,
    time_bucket TIMESTAMP,
    trip_count BIGINT,
    PRIMARY KEY ((zone), time_bucket)
) WITH CLUSTERING ORDER BY (time_bucket ASC)
AND compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_unit': 'MINUTES',
    'compaction_window_size': '60'
}
AND default_time_to_live = 7776000;  -- 90 days retention