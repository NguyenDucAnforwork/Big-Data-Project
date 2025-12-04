# 🧩 Mini Survey: Apache Cassandra

## 1. **Architecture of Cassandra**
Cassandra is a decentralized multi-node database that physically spans separate locations and uses **replication** and **partitioning** to infinitely scale reads and writes:
- **Decentralized**: No single point central controller, easily scalable and failure-resistant.
- Data is replicated across multiple nodes. For requests, the coordinator node (which can be any node receives the request), if necessary, always knows which node stores data through **consistent hashing algorithm**.

For an overview of Cassandra architecture, a Cassandra database called a cluster. A cluster consists of multiple nodes(physical servers). Keyspace is a logical grouping of tables, similar to a database in RDBMS. a cluster contains one or more keyspaces, and each keyspace contains one or more tables. One node can host multiple keyspaces and tables. One keyspace can locate on multiple nodes. In a table, data is distributed across multiple partitions, and each partition is stored on a single node. 


### 1.2. Data Partitioning
> **Partitioning** is a method of splitting and storing a single logical dataset in multiple databases. By distributing the data among multiple machines, a **cluster** of database systems can store larger datasets and handle additional requests.

— *How Sharding Works* by Jeeyoung Kim

In Cassandra, **Primary key** not only uniquely identifies a row, but also determines how data is distributed across the cluster. It consists of:
- **Partition Key**: Determines the node where the data is stored. It mapped to node using consistent hashing algorithm.
- **Clustering Columns**: Define the order of data within a partition.

Given a table :
```text
country (p) | user_email (c)  | first_name | last_name | age
----------------------------------------------------------------
US          | john@email.com  | John       | Wick      | 55  
UK          | peter@email.com | Peter      | Clark     | 65  
UK          | bob@email.com   | Bob        | Sandler   | 23 
UK          | alice@email.com | Alice      | Brown     | 26
```

To create this table in Cassandra, you would use:
```sql
CREATE TABLE learn_cassandra.users_by_country (
    country text,
    user_email text,
    first_name text,
    last_name text,
    age smallint,
    PRIMARY KEY ((country), user_email)
),
```
The first group of the primary key (country) defines the **partition key**. All other elements of the primary key (user_email) are **clustering columns**.

From point of view of SQL, this choice of primary key is strange. But the use of primary key in Cassandra is different. In this case, all rows from the same country are stored in the same partition. Different partitions will be distributed to different nodes, which enables **horizontal scalability**. 
- **Horizontal Scalability**: It means you can scale out by adding more nodes to the cluster to handle more data and more requests, instead of scaling up by adding more resources (CPU, RAM) to a single node.

The partition key plays a crucial role in efficient data storage and retrieval in Cassandra. A good partition key should:
- Distribute data evenly across the cluster to avoid hotspots.
- Support efficient queries by minimizing the number of partitions that need to be accessed.

### 1.3. Replication 
By duplicating data across multiple nodes(replicas), you can improve throughput, fault tolerance, and availability.
The replication factor (RF) determines how many copies of the data are stored in the cluster. For example, if RF=3, there will be three copies of each piece of data on different nodes.
 
### 1.4. Consistency Levels
There are 3 main consistency levels in Cassandra:
- **ONE**: means only single replica node must respond to a read or write request.
- **QUORUM**: means a majority of replica nodes must respond to a read or write request. For example, if RF=3, at least 2 nodes must respond.
- **ALL**: means all replica nodes must respond to a read or write request.
You can define the consistency level of your read and write queries. This choice is a trade-off between consistency, availability, and latency.

CAP theorem: 
- Consistency: Every read receives the most recent write or an error.
- Availability: Every request receives a (non-error) response, without guarantee that it contains the most recent write.
- Partition Tolerance: The system continues to operate despite an arbitrary number of messages
When a network partition occurs, a distributed system must choose between consistency and availability. Cassandra is designed to be AP (Available and Partition-tolerant) by default, but you can configure it to be CP (Consistent and Partition-tolerant) by using higher consistency levels like QUORUM or ALL.

To ensure strong consistency, you need to satisfy the condition:
[read-consistency-level] + [write-consistency-level] > [replication-factor]

### 1.5. Other Concepts
- **Optimize storage for reading or writing**: Cassandra is optimized for high write throughput. It uses a log-structured storage engine that writes data sequentially to disk, which is faster than random writes. Reads can be slower, especially if the data is not in memory.
- **Compaction**: For every write operation, data is written to disk to provide durability. This means that if something goes wrong, like a power outage, data is not lost. SSTables are immutable data files Cassandra uses to store data on disk. Over time, multiple SSTables can accumulate, which can lead to inefficient reads. Compaction is the process of merging these SSTables into fewer, larger ones, which helps improve read performance and reclaim disk space.
- **Presort data on Cassandra nodes**: Data within a partition is sorted by clustering columns. This allows for efficient range queries and ordered retrieval of data.
For above table, to presort users by age within each country, you can define the table as:
```sql
CREATE TABLE learn_cassandra.users_by_country_sorted_by_age_asc (
    country text,
    user_email text,
    first_name text,
    last_name text,
    age smallint,
    PRIMARY KEY ((country), age, user_email)
) WITH CLUSTERING ORDER BY (age ASC);
```

## 2. **Data Model of Cassandra**
--- On going ---

## 3. **Deployment of Cassandra on Kubernetes**
--- On going ---

# Temporary Conclusion: 
## 1. Cassandra is query-driven
When designing a data model in Cassandra, you should start with the queries you want to support. This is different from traditional relational databases, where you typically start with the data and its relationships. In Cassandra, you should denormalize your data and create tables that are optimized for your specific queries.
## 2. Cassandra expensive in join or query across multiple partitions
Cassandra does not support joins or complex queries across multiple partitions. As a trade-off for its scalability and performance, you should design your data model to avoid these operations: put all the data you need for a query in a single partition; choose partition keys that support your query patterns; use clustering columns to sort and filter data within a partition.