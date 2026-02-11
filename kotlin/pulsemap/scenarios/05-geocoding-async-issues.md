# Slack Discussion: Geocoding and Data Processing Anomalies

## #eng-backend - February 21, 2024

---

**@dev.nina** (10:15):
> Hey team, I'm seeing some weird behavior in the geocoding service. Reverse geocode lookups are returning "Unknown Location" for coordinates that should definitely resolve. Anyone else seeing this?

**@dev.james** (10:18):
> Which coordinates? I can test on my side.

**@dev.nina** (10:20):
> Tried (40.7128, -74.0060) which should return something like "New York, NY" but getting "Unknown Location". The external geocoding API is definitely working - I tested it directly.

**@dev.james** (10:25):
> Let me add some debug logging...

**@dev.james** (10:32):
> OK this is interesting. Look at the logs:
```
10:30:15.123 DEBUG GeocodingService - Starting reverse geocode for: (40.7128, -74.0060)
10:30:15.124 DEBUG GeocodingService - Launching async geocode request
10:30:15.125 DEBUG GeocodingService - Returning result: "Unknown Location"
10:30:15.456 DEBUG GeocodingService - Async geocode completed: "350 5th Ave, New York, NY 10118"
```

**@dev.nina** (10:35):
> Wait, the async result comes AFTER we return? That's backwards.

**@dev.james** (10:38):
> Found it. Look at this code in `GeocodingService`:
```kotlin
suspend fun reverseGeocode(lat: Double, lon: Double): String {
    val addressDeferred = async {
        externalGeocodingApi.lookup(lat, lon)
    }
    // Some other setup work...
    return "Unknown Location"  // Returns immediately without awaiting!
}
```

**@dev.nina** (10:42):
> So we launch the async request but never call `await()` on it? The result is computed and then thrown away!

**@dev.james** (10:45):
> Exactly. It should be:
```kotlin
return addressDeferred.await()  // Actually wait for the result
```

---

**@dev.nina** (11:00):
> While we're on async issues, I've been debugging the spatial aggregation service. The Flow processing is running on the wrong dispatcher.

**@dev.james** (11:05):
> What do you mean?

**@dev.nina** (11:08):
> Check this out:
```kotlin
suspend fun aggregateSensorData(flow: Flow<SensorReading>) {
    flow
        .map { processReading(it) }  // CPU-intensive work
        .collect { results.add(it) }
        .flowOn(Dispatchers.IO)  // <-- This does nothing!
}
```

**@dev.james** (11:12):
> Oh no. `flowOn` needs to be applied BEFORE `collect`, not after. It only affects upstream operators.

**@dev.nina** (11:15):
> Right. So all our CPU-intensive map operations are running on `Dispatchers.Default` instead of `Dispatchers.IO`. That's why we're seeing thread pool contention during heavy aggregation jobs.

**@dev.james** (11:18):
> The correct pattern is:
```kotlin
flow
    .map { processReading(it) }
    .flowOn(Dispatchers.IO)  // Affects the map above
    .collect { results.add(it) }
```

---

**@sre.tom** (11:30):
> Related issue: I'm seeing memory growth in the ingestion pipeline. Channel buffer keeps growing under burst traffic.

**@dev.james** (11:35):
> Let me check... oh boy:
```kotlin
private val ingestChannel = Channel<SensorReading>(Channel.UNLIMITED)
```

**@sre.tom** (11:38):
> `Channel.UNLIMITED`? So there's no backpressure at all?

**@dev.james** (11:42):
> None. During burst traffic, producers can dump unlimited messages into the channel faster than consumers can process them. Memory grows until OOM.

**@sre.tom** (11:45):
> Metrics confirm:
```
Time         Channel Size    Memory Usage
11:00        1,247           2.1 GB
11:15        47,829          3.4 GB
11:30        182,456         5.8 GB
11:35        OOM Kill
```

**@dev.james** (11:48):
> Should use `Channel.BUFFERED` (64 by default) or an explicit capacity like `Channel(128)`. That way producers will suspend when the buffer is full, creating natural backpressure.

---

**@dev.nina** (12:00):
> One more thing - I noticed the tile cache lookup has a race condition:
```kotlin
fun getTile(key: String): Tile? {
    if (cache.containsKey(key)) {
        return cache[key]!!  // <-- Can NPE!
    }
    return null
}
```

**@dev.james** (12:05):
> TOCTOU (time-of-check-time-of-use). Between `containsKey` and `get`, another thread could evict the entry. The `!!` will then throw NPE.

**@dev.nina** (12:08):
> We hit this 3 times in prod last week. Always under high concurrency.

**@dev.james** (12:12):
> Fix is simple - just use `get` directly:
```kotlin
fun getTile(key: String): Tile? {
    return cache[key]  // Returns null if not present
}
```

**@dev.nina** (12:15):
> Or use `getOrElse` if we need a default.

---

**@dev.james** (12:30):
> Found another issue while investigating. In `TileRepository`, there's a coroutine launched inside an Exposed transaction:
```kotlin
transaction {
    // Insert tile data
    GlobalScope.launch {
        notifyTileSubscribers(tileId)  // Escapes transaction scope!
    }
}
```

**@dev.nina** (12:35):
> What's wrong with that?

**@dev.james** (12:38):
> The `GlobalScope.launch` runs independently of the transaction. By the time the coroutine executes, the transaction may have already committed or rolled back. If it tries to do any database work, `TransactionManager.current()` will be null.

**@dev.nina** (12:42):
> We've been getting sporadic `IllegalStateException: No transaction in context` errors. This could be why.

**@dev.james** (12:45):
> Should either move the notification outside the transaction block, or use Exposed's `afterCommit` hook:
```kotlin
transaction {
    // Insert tile data
    afterCommit {
        scope.launch { notifyTileSubscribers(tileId) }
    }
}
```

---

## Summary of Issues

1. **Async without await**: `GeocodingService.reverseGeocode()` launches async but never awaits result
2. **flowOn after collect**: `SpatialAggregationService` applies `flowOn` after `collect`, which has no effect
3. **Unbounded channel**: `IngestionService` uses `Channel.UNLIMITED` with no backpressure
4. **TOCTOU in cache**: `TileService` uses `containsKey` + `!!` pattern that races under concurrency
5. **Coroutine escaping transaction**: `TileRepository` launches `GlobalScope` coroutine inside transaction

## Files to Fix

- `src/main/kotlin/com/pulsemap/service/GeocodingService.kt`
- `src/main/kotlin/com/pulsemap/service/SpatialAggregationService.kt`
- `src/main/kotlin/com/pulsemap/service/IngestionService.kt`
- `src/main/kotlin/com/pulsemap/service/TileService.kt`
- `src/main/kotlin/com/pulsemap/repository/TileRepository.kt`

---

**Action Items**:
- [ ] Fix await() call in GeocodingService
- [ ] Move flowOn() before collect() in SpatialAggregationService
- [ ] Change Channel.UNLIMITED to Channel.BUFFERED in IngestionService
- [ ] Fix TOCTOU race in TileService cache lookup
- [ ] Move coroutine launch outside transaction in TileRepository

**Priority**: Medium - causes data quality issues and memory growth under load
**Assigned**: @dev.james, @dev.nina
