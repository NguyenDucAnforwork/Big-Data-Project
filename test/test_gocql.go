package main

import (
    "fmt"
    "log"

    "github.com/gocql/gocql"
)

func main() {
    cluster := gocql.NewCluster("cassandra")
    cluster.Port = 9042
    cluster.Keyspace = "taxi_streaming"
    cluster.Consistency = gocql.One

    session, err := cluster.CreateSession()
    if err != nil {
        log.Fatalf("Failed to connect to Cassandra: %v", err)
    }
    defer session.Close()

    fmt.Println("Connected to Cassandra successfully!")
}