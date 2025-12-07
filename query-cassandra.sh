#!/bin/bash

# Quick Cassandra Query Helper Script

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ $# -eq 0 ]; then
    echo -e "${YELLOW}Usage:${NC}"
    echo "  $0 count          - Count total records"
    echo "  $0 recent         - Show recent 10 records"
    echo "  $0 zones          - Top zones by revenue"
    echo "  $0 peaks          - Peak hour analysis"
    echo "  $0 interactive    - Open cqlsh shell"
    echo "  $0 'YOUR QUERY'   - Run custom CQL query"
    exit 0
fi

case "$1" in
    count)
        echo -e "${GREEN}Counting total records...${NC}"
        docker exec cassandra cqlsh -e "USE taxi_streaming; SELECT COUNT(*) FROM taxi_analytics;"
        ;;
    recent)
        echo -e "${GREEN}Recent 10 aggregations...${NC}"
        docker exec cassandra cqlsh -e "USE taxi_streaming; SELECT window_start, pickup_zone, peak_category, total_trips, total_revenue FROM taxi_analytics LIMIT 10;"
        ;;
    zones)
        echo -e "${GREEN}Top zones by revenue...${NC}"
        docker exec cassandra cqlsh -e "USE taxi_streaming; SELECT pickup_zone, SUM(total_revenue) as revenue FROM taxi_analytics GROUP BY pickup_zone ALLOW FILTERING LIMIT 10;"
        ;;
    peaks)
        echo -e "${GREEN}Peak hour analysis...${NC}"
        docker exec cassandra cqlsh -e "USE taxi_streaming; SELECT peak_category, SUM(total_trips) as trips, AVG(avg_fare) as avg_fare FROM taxi_analytics GROUP BY peak_category ALLOW FILTERING;"
        ;;
    interactive)
        echo -e "${GREEN}Opening Cassandra shell...${NC}"
        echo -e "${YELLOW}Tip: Run 'USE taxi_streaming;' first${NC}"
        docker exec -it cassandra cqlsh
        ;;
    *)
        echo -e "${GREEN}Running custom query...${NC}"
        docker exec cassandra cqlsh -e "USE taxi_streaming; $1"
        ;;
esac
