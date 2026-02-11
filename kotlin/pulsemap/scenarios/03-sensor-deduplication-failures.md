# Customer Escalation: Duplicate Sensor Readings

## Zendesk Ticket #58234

**Priority**: Urgent
**Customer**: WeatherNet Global (Enterprise Tier)
**Account Value**: $480,000 ARR
**CSM**: David Park
**Created**: 2024-02-20 09:15 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> Our IoT sensor network pushes thousands of readings per minute to PulseMap. We're seeing massive data duplication in our dashboards - the same sensor reading appears multiple times with identical timestamps. This is completely breaking our analytics and our weather prediction models are producing garbage results.

### Reported Symptoms

1. **Duplicate Readings**: Identical sensor readings stored multiple times despite deduplication being enabled

2. **HashSet Not Deduplicating**: Customer implemented their own dedup check using HashSet, but readings that should be equal are not matching

3. **Memory Growth**: The deduplication cache is growing unbounded and never evicting entries

4. **Shallow Copy Corruption**: When creating sensor reading batches, modifications to one batch affect others

---

## Technical Details from Customer Logs

### Dashboard Query Results

```sql
-- Customer's debug query
SELECT sensor_id, timestamp, temperature, COUNT(*) as occurrences
FROM sensor_readings
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY sensor_id, timestamp, temperature
HAVING COUNT(*) > 1
LIMIT 10;

sensor_id       | timestamp                  | temperature | occurrences
----------------+----------------------------+-------------+------------
sensor_wx_001   | 2024-02-20 08:15:00.000   | 23.5        | 4
sensor_wx_001   | 2024-02-20 08:15:30.000   | 23.7        | 3
sensor_wx_002   | 2024-02-20 08:16:00.000   | 18.2        | 5
sensor_wx_003   | 2024-02-20 08:16:30.000   | 31.1        | 2
```

### Client SDK Logs

```
2024-02-20T08:15:00.123Z [SDK] Submitting reading: SensorReading(id=wx_001, values=[23.5, 67.2, 1013.25])
2024-02-20T08:15:00.124Z [SDK] Dedup check: hash=1847293847
2024-02-20T08:15:00.456Z [SDK] Submitting reading: SensorReading(id=wx_001, values=[23.5, 67.2, 1013.25])
2024-02-20T08:15:00.457Z [SDK] Dedup check: hash=1938472651  # Different hash for identical data!
2024-02-20T08:15:00.458Z [SDK] Warning: Identical readings have different hash codes
```

---

## Internal Investigation

### Slack Thread: #eng-data-pipeline

**@dev.sarah** (09:30):
> Looking at the duplicate issue. The customer is right - their readings should be deduplicated but they're not. Let me check the `DeduplicationService`.

**@dev.sarah** (09:42):
> Found the issue. Look at our `SensorReading` data class:
```kotlin
data class SensorReading(
    val sensorId: String,
    val timestamp: Instant,
    val values: DoubleArray  // <-- This is the problem
)
```

**@dev.marcus** (09:45):
> What's wrong with DoubleArray?

**@dev.sarah** (09:48):
> Arrays in Kotlin use reference equality for `equals()` and `hashCode()`, not structural equality. So two `SensorReading` objects with identical values but different array instances will have different hashes and won't be considered equal.

**@dev.sarah** (09:50):
> Proof:
```kotlin
val a = SensorReading("s1", now, doubleArrayOf(1.0, 2.0))
val b = SensorReading("s1", now, doubleArrayOf(1.0, 2.0))
println(a == b)  // false!
println(a.hashCode() == b.hashCode())  // false!
```

**@dev.marcus** (09:55):
> That completely breaks our HashSet-based deduplication. Every reading is "unique" even if the data is identical.

---

### Additional Issue: Shallow Copy Corruption

**@dev.sarah** (10:10):
> Found another data class issue in `GeoPoint`:
```kotlin
data class GeoPoint(
    val latitude: Double,
    val longitude: Double,
    val annotations: MutableList<String> = mutableListOf()
)
```

**@dev.marcus** (10:15):
> What's the problem there?

**@dev.sarah** (10:18):
> When you call `copy()` on a data class, it does a shallow copy. The `annotations` list is shared between the original and the copy:
```kotlin
val original = GeoPoint(40.7, -74.0)
val copy = original.copy()
copy.annotations.add("test")
println(original.annotations)  // ["test"] - original was modified!
```

**@dev.marcus** (10:22):
> That explains the batch corruption reports. We use `copy()` to create reading batches and then modify them independently - or so we thought.

---

### Memory Growth Analysis

**@sre.jenny** (10:30):
> The dedup cache is at 8GB and growing. Looking at heap dump...

**@sre.jenny** (10:45):
> The cache stores `SensorReading` objects as keys in a HashMap for deduplication. But because `equals()` is broken, nothing ever matches existing entries - every lookup is a miss, every reading gets added as a new entry.

**@sre.jenny** (10:48):
> Cache stats:
```
Entries: 2,847,293
Expected entries (with working dedup): ~50,000
Cache hit rate: 0.0%
Memory usage: 8.2GB
```

---

## Test Output

```
com.pulsemap.unit.SensorReadingTest > test data class equals with DoubleArray FAILED
    AssertionError: Expected readings to be equal
    at org.junit.jupiter.api.AssertionUtils.fail(AssertionUtils.java:55)

com.pulsemap.unit.GeoPointTest > test copy creates independent instance FAILED
    AssertionError: Expected original annotations to be empty after modifying copy
    Expected: []
    Actual: ["modified"]

com.pulsemap.integration.DeduplicationTest > test duplicate readings are filtered FAILED
    AssertionError: Expected 1 unique reading, but got 5
```

---

## Customer Impact

- **Data quality**: All analytics contaminated with duplicates
- **Storage costs**: 400% increase in data storage
- **ML models**: Weather prediction accuracy dropped from 94% to 67%
- **Customer confidence**: Considering alternative platform

---

## Files to Investigate

Based on analysis:
- `src/main/kotlin/com/pulsemap/model/SensorReading.kt` - DoubleArray in data class
- `src/main/kotlin/com/pulsemap/model/GeoPoint.kt` - MutableList shallow copy
- `src/main/kotlin/com/pulsemap/service/DeduplicationService.kt` - HashSet-based dedup relying on broken equals

---

## Kotlin Data Class Pitfalls Reference

From Kotlin documentation:
> Note that the compiler only uses the properties defined in the primary constructor for automatically generated functions... Properties declared in the class body are excluded.

For arrays specifically:
> Arrays in Kotlin are represented by the Array class... Arrays are NOT compared structurally - two arrays are equal only if they are the same instance.

---

**Status**: INVESTIGATING
**Assigned**: @dev.sarah, @dev.marcus
**Customer Follow-up**: Scheduled for 2024-02-21 10:00 UTC
**Workaround**: Customer implementing client-side deduplication (temporary)
