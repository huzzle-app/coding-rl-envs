# Slack Discussion: Data Corruption and Cache Inconsistencies

## #eng-backend - February 17, 2024

---

**@qa.jennifer** (09:15):
> Hey team, we're seeing some really strange behavior in our integration tests. Document comparisons are failing even when the documents should be identical. Also getting intermittent serialization errors that I can't reproduce consistently.

**@dev.marcus** (09:22):
> Can you share the test output? What kind of comparison failures?

**@qa.jennifer** (09:25):
> Here's a sample:
```
Test: DocumentEqualityTest.testDocumentComparison
Expected: Document(id=123, content=[1, 2, 3, 4, 5])
Actual:   Document(id=123, content=[1, 2, 3, 4, 5])
Result: FAILED - objects not equal

Assertion failed: doc1 == doc2 returned false
But doc1.content and doc2.content have identical byte values!
```

**@dev.alex** (09:30):
> Oh, that's the ByteArray equality trap. In Kotlin data classes, `equals()` uses reference equality for arrays, not `contentEquals()`. Two ByteArrays with the same content are not equal by `==`.

**@qa.jennifer** (09:32):
> That explains it. But there's more - we're also seeing this after document copies:
```
Test: DocumentMetadataTest.testDeepCopy
Original tags: [important, work]
Copied tags: [important, work, modified]
Original tags AFTER modifying copy: [important, work, modified]

Wait - modifying the copy changed the original?!
```

**@dev.alex** (09:35):
> Classic shallow copy issue. `data class` `copy()` doesn't deep-copy mutable collections. If `Metadata` has a `MutableList<String>` for tags, the copy shares the same list reference.

---

**@dev.sarah** (10:05):
> I'm hitting a different problem in the search service. The sealed class `QueryNode` is crashing at runtime:
```
kotlin.NoWhenBranchMatchedException:
    at com.mindvault.search.QueryParser.evaluate(QueryParser.kt:89)

Query was: PhraseQuery("machine learning")
```

**@dev.marcus** (10:08):
> Let me guess - there's a `when` expression on `QueryNode` that's missing the `PhraseQuery` branch?

**@dev.sarah** (10:10):
> Exactly. The compiler didn't catch it because there's an `else` branch, but the else throws an exception for "unknown query type". When `PhraseQuery` was added, nobody updated the when expression.

---

**@dev.jordan** (10:30):
> Getting serialization errors in the graph service:
```
kotlinx.serialization.SerializationException:
Serializer for class 'References' is not found.
Please ensure that class is marked as '@Serializable' and that
the serialization compiler plugin is applied.

at com.mindvault.graph.EdgeSerializer.deserialize(Edge.kt:45)
```

**@dev.sarah** (10:33):
> Is `References` a sealed subclass of `Edge`? Those need to be registered in the `SerializersModule` for polymorphic serialization.

**@dev.jordan** (10:35):
> Yes it is. I thought the `@Serializable` annotation was enough?

**@dev.sarah** (10:38):
> Nope, for sealed classes with `kotlinx.serialization`, each subclass needs to be explicitly registered:
```kotlin
serializersModule = SerializersModule {
    polymorphic(Edge::class) {
        subclass(References::class, References.serializer())
        // Missing this registration!
    }
}
```

---

**@dev.alex** (11:15):
> Found another fun one. The `@JvmInline value class NodeId` is causing issues when used as a HashMap key:
```
Test: GraphCacheTest.testNodeIdAsKey
cache.put(NodeId("abc"), data1)
cache.get(NodeId("abc")) returns null!

But cache.keys contains NodeId("abc")
```

**@dev.marcus** (11:18):
> Boxing/unboxing issue. When you use a value class as a generic type parameter (like `Map<NodeId, T>`), it gets boxed. If there's inconsistency in how it's boxed vs unboxed, key lookups fail.

---

**@qa.jennifer** (11:45):
> More weirdness - the graph service cache is returning stale data:
```
1. Update node via DSL: Nodes.update { it[name] = "new name" }
2. Query via DAO: Node.findById(id)
3. Result: Node(name = "old name")

The DSL update worked (checked database directly), but the DAO returns old cached value
```

**@dev.jordan** (11:48):
> Exposed's entity cache isn't invalidated by DSL operations. The DAO has its own cache that doesn't know about the DSL update. Need to either clear the entity cache or use `Entity.reload()`.

---

**@sre.kim** (13:00):
> Cache issues in the search service too. Same query is hitting the database every time:
```
Query: "machine learning papers 2024"
Cache key: "search_ml_papers_1708180234567"

Next query (same search):
Cache key: "search_ml_papers_1708180239123"

Keys are different! The timestamp is being included in the cache key.
```

**@dev.alex** (13:03):
> The cache key generator is including request timestamp or request ID. That makes every request unique, defeating the cache entirely.

**@sre.kim** (13:05):
> And during load testing, we're seeing this:
```
10 concurrent requests for same uncached query
All 10 hit the database simultaneously
Expected: 1 DB hit, 9 cache hits

This is the classic cache stampede problem.
```

---

**@dev.sarah** (14:30):
> Serialization chaos continues. Getting errors when reading from cache:
```
kotlinx.serialization.json.internal.JsonDecodingException:
Unexpected JSON token at offset 234: Expected '"', but had '}' instead
JSON input: {"id":"123","data":{"newField":"value"}}

at com.mindvault.graph.GraphCache.get(GraphCache.kt:67)
```

**@dev.marcus** (14:33):
> Schema evolution issue. The cached data has a field (`newField`) that didn't exist when the cache entry was written. If `ignoreUnknownKeys` is false (the default), deserialization fails.

**@dev.sarah** (14:35):
> So every time we add a new field to a cached type, we break all existing cache entries?

**@dev.marcus** (14:37):
> Yes, unless you set `ignoreUnknownKeys = true` or version your cache keys.

---

**@dev.alex** (15:00):
> One more - the in-memory cache is growing unbounded:
```
Memory usage over time:
  Start: 512MB
  +1h:   1.2GB
  +2h:   2.4GB
  +3h:   OOM crash

Cache entries: 2,847,291 and growing
```

**@sre.kim** (15:03):
> There's no eviction policy? No max size?

**@dev.alex** (15:05):
> Apparently not. It's using a plain `HashMap` with no bounds. Also, the TTL isn't working - entries never expire because there's a type mismatch between `java.time.Duration` and `kotlin.time.Duration` in the expiration check.

---

## Summary of Issues

1. **Document equality**: `data class` with `ByteArray` uses reference equality
2. **Shallow copy**: `copy()` shares mutable collection references
3. **Missing when branch**: Sealed class `QueryNode` missing `PhraseQuery` case
4. **Unregistered serializer**: Sealed subclass `References` not in `SerializersModule`
5. **Value class boxing**: `NodeId` behaves inconsistently as map key
6. **Stale DAO cache**: DSL updates don't invalidate entity cache
7. **Unstable cache key**: Timestamp included in cache key
8. **Cache stampede**: No coalescing of concurrent cache misses
9. **Schema evolution**: Cache deserialization fails on new fields
10. **Unbounded cache**: No eviction policy, TTL type mismatch

## Files to Investigate

- `documents/src/main/kotlin/com/mindvault/documents/Document.kt`
- `search/src/main/kotlin/com/mindvault/search/QueryNode.kt`
- `graph/src/main/kotlin/com/mindvault/graph/Edge.kt`
- `graph/src/main/kotlin/com/mindvault/graph/NodeId.kt`
- `shared/src/main/kotlin/com/mindvault/shared/cache/Cache.kt`
