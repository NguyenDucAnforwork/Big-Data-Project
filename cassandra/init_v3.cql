CREATE KEYSPACE IF NOT EXISTS analytics
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE analytics;

-- Zones Revenue by Time Window (30-minute or 15-minute windows)
CREATE TABLE IF NOT EXISTS zones_revenue_by_window (
    zone TEXT,
    time_bucket TIMESTAMP,
    total_revenue DOUBLE,
    trip_count BIGINT,
    last_updated TIMESTAMP,
    PRIMARY KEY (zone, time_bucket)
) WITH CLUSTERING ORDER BY (time_bucket DESC)
AND default_time_to_live = 7776000;  -- 90 days retention