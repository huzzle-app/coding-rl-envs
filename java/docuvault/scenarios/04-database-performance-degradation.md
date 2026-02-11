# Grafana Alert: Database Performance Critical

## Alert Details

**Alert Name**: PostgreSQL Query Performance Degraded
**Severity**: High
**Firing Since**: 2024-01-17 14:32 UTC
**Dashboard**: DocuVault Infrastructure > Database

---

## Alert Configuration

```yaml
alert: PostgresSlowQueries
expr: pg_stat_statements_mean_time_seconds{query=~".*documents.*"} > 5
for: 5m
labels:
  severity: high
annotations:
  summary: "Document queries taking >5s on average"
  description: "Query time {{ $value }}s exceeds threshold"
```

## Current Metrics

| Metric | Value | Threshold |
|--------|-------|-----------|
| Avg Query Time (documents) | 8.7s | <1s |
| Active Connections | 45 | 50 (max) |
| Queries per Second | 127 | - |
| Lock Wait Time | 2.3s avg | <100ms |
| Connection Timeouts | 234 | 0 |

---

## Error Logs from Application

### N+1 Query Pattern Detected

```
2024-01-17T14:32:15.123Z DEBUG  Hibernate: select d1_0.id,d1_0.name,d1_0.user_id from documents d1_0 where d1_0.user_id=?
2024-01-17T14:32:15.234Z DEBUG  Hibernate: select v1_0.id,v1_0.document_id,v1_0.version from versions v1_0 where v1_0.document_id=?
2024-01-17T14:32:15.345Z DEBUG  Hibernate: select v1_0.id,v1_0.document_id,v1_0.version from versions v1_0 where v1_0.document_id=?
2024-01-17T14:32:15.456Z DEBUG  Hibernate: select v1_0.id,v1_0.document_id,v1_0.version from versions v1_0 where v1_0.document_id=?
... [repeated 247 times for 247 documents]
```

### LazyInitializationException

```
2024-01-17T14:35:22.789Z ERROR  Failed to access document permissions
org.hibernate.LazyInitializationException: failed to lazily initialize a collection of role:
com.docuvault.model.Document.permissions: could not initialize proxy - no Session

    at org.hibernate.collection.spi.AbstractPersistentCollection.throwLazyInitializationException(AbstractPersistentCollection.java:635)
    at org.hibernate.collection.spi.AbstractPersistentCollection.withTemporarySessionIfNeeded(AbstractPersistentCollection.java:218)
    at org.hibernate.collection.spi.AbstractPersistentCollection.initialize(AbstractPersistentCollection.java:615)
    at com.docuvault.service.DocumentService.getDocumentPermissions(DocumentService.java:287)
```

### Connection Pool Exhaustion

```
2024-01-17T14:40:45.012Z  WARN  HikariPool-1 - Connection is not available, request timed out after 30000ms
2024-01-17T14:40:45.234Z ERROR  Unable to acquire JDBC Connection
org.springframework.jdbc.CannotGetJdbcConnectionException: Failed to obtain JDBC Connection

Caused by: java.sql.SQLTransientConnectionException: HikariPool-1 - Connection is not available, request timed out after 30000ms.
    at com.zaxxer.hikari.pool.HikariPool.createTimeoutException(HikariPool.java:696)
    at com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:197)
```

### EntityManager Not Closed

```
2024-01-17T14:42:18.567Z  WARN  EntityManager leak detected
2024-01-17T14:42:18.568Z DEBUG  Leaked EntityManager created at:
    at com.docuvault.service.DocumentService.searchDocumentsNative(DocumentService.java:312)
    at com.docuvault.controller.DocumentController.search(DocumentController.java:156)
```

### OptimisticLockException (Unhandled)

```
2024-01-17T14:45:33.890Z ERROR  Failed to update document metadata
org.hibernate.StaleObjectStateException: Row was updated or deleted by another transaction
(or unsaved-value mapping was incorrect): [com.docuvault.model.Document#doc_12345]

    at org.hibernate.event.internal.DefaultMergeEventListener.entityIsDetached(DefaultMergeEventListener.java:303)
    at com.docuvault.util.FileUtils.updateMetadata(FileUtils.java:189)
```

---

## PostgreSQL Analysis

### pg_stat_statements Output

```sql
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
WHERE query LIKE '%documents%'
ORDER BY total_time DESC
LIMIT 10;
```

```
                         query                         | calls | mean_time |  total_time
-------------------------------------------------------+-------+-----------+-------------
 SELECT ... FROM documents WHERE user_id = $1          | 12847 |   0.234s  |    3006.2s
 SELECT ... FROM versions WHERE document_id = $1       | 89234 |   0.089s  |    7941.8s  <- N+1!
 SELECT ... FROM permissions WHERE document_id = $1    |  4521 |   0.156s  |     705.3s
```

### Active Connections Analysis

```sql
SELECT state, count(*), array_agg(query) as queries
FROM pg_stat_activity
WHERE datname = 'docuvault'
GROUP BY state;
```

```
   state   | count |                     queries
-----------+-------+------------------------------------------------
 active    |    12 | {"SELECT ... FROM documents...", ...}
 idle      |     8 | {...}
 idle in transaction | 25 | {"SELECT ... FROM documents...", ...}  <- PROBLEM!
```

25 connections stuck in "idle in transaction" state, indicating EntityManagers not being properly closed.

---

## Heap Dump Analysis

JVM heap dump shows high retention of:

```
com.docuvault.model.Document instances: 12,847 (retained: 890MB)
  └── Each Document retains:
      └── permissions: LazyCollection (not initialized, but holding proxy reference)
      └── versions: LazyCollection (not initialized)

org.hibernate.engine.internal.StatefulPersistenceContext instances: 25
  └── Each retains ~35MB of entity state
  └── Never cleared due to unclosed EntityManager
```

---

## Customer Impact

### User Reports

> "Loading the document list takes forever now. It used to be instant."
> - Sarah M., Legal Department

> "I keep getting 'Connection timed out' errors when trying to view document history."
> - James K., Compliance Team

> "My document changes aren't saving. I get an error about 'stale state' and have to refresh."
> - Maria L., Contracts Manager

### Metrics

- **Page Load Time**: P95 increased from 800ms to 12.4s
- **Error Rate**: Increased from 0.1% to 4.7%
- **User Complaints**: 47 tickets in past 24 hours

---

## Root Causes (Suspected)

1. **N+1 Query Problem**: `Document.versions` is lazily loaded, causing a separate query for each document when iterating
2. **LazyInitializationException**: Accessing lazy collections outside of transaction scope
3. **Connection Leak**: EntityManager created manually but not closed on all code paths
4. **OptimisticLockException**: Concurrent updates not handled with retry logic
5. **Missing Transaction Boundaries**: Some methods calling @Transactional methods via `this.` instead of through the proxy

---

## Recommended Investigation

1. Check `DocumentRepository.java` for `JOIN FETCH` usage
2. Review `DocumentService.java` for proper transaction boundaries
3. Look for manual EntityManager usage without try-with-resources
4. Verify `@Transactional` methods aren't being self-invoked

---

## Attempted Mitigations

1. Increased connection pool size from 20 to 50 - helped briefly, then exhausted again
2. Added query timeout of 30s - now queries fail instead of hanging
3. Enabled Hibernate statistics - revealed N+1 pattern

---

## Files to Investigate

- `src/main/java/com/docuvault/repository/DocumentRepository.java` - Missing JOIN FETCH
- `src/main/java/com/docuvault/service/DocumentService.java` - LazyInitializationException, EntityManager leak, @Transactional self-invocation
- `src/main/java/com/docuvault/util/FileUtils.java` - OptimisticLockException handling

---

**Status**: Active
**On-Call**: @sre.michael
**Escalation**: Database team notified
