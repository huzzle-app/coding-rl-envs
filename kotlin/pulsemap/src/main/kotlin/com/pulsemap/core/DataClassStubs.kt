package com.pulsemap.core

// =============================================================================
// Data class stubs: Demonstrate Kotlin data class and sealed class pitfalls.
// Bugs: C1 (DoubleArray equality), C2 (shallow copy), C3 (missing when branch),
//        C4 (missing sealed serialization registration)
// =============================================================================

/**
 * Sensor reading with measurement values.
 *
 * BUG C1: Uses DoubleArray instead of List<Double>. In Kotlin data classes,
 * DoubleArray.equals() uses reference equality (identity), not structural equality.
 * This means two SensorReadingLocal instances with identical values will NOT be equal,
 * and deduplication via HashSet/HashMap will fail.
 */
data class SensorReadingLocal(
    val id: String,
    val sensorId: String,
    val values: DoubleArray,  // BUG C1: Arrays use reference equality in data classes
    val latitude: Double,
    val longitude: Double,
    val timestamp: Long
)

/**
 * Geographic point with mutable annotations.
 *
 * BUG C2: The annotations field is a MutableList. Kotlin's data class copy()
 * performs a shallow copy, meaning the original and copy share the same
 * MutableList reference. Modifying one mutates the other.
 */
data class GeoPointLocal(
    val lat: Double,
    val lng: Double,
    val annotations: MutableList<String> = mutableListOf()  // BUG C2: Shallow copied by data class
)

/**
 * Sealed class representing geometry types.
 *
 * BUG C3: The describeGeometry function uses a when expression that handles
 * most subtypes but is missing MultiPolygon. The else branch throws instead
 * of handling it properly.
 */
sealed class GeometryTypeLocal {
    object Point : GeometryTypeLocal()
    object LineString : GeometryTypeLocal()
    object Polygon : GeometryTypeLocal()
    object MultiPolygon : GeometryTypeLocal()
    object GeometryCollection : GeometryTypeLocal()
}

/**
 * Describe a geometry type. Missing MultiPolygon branch.
 * BUG C3: MultiPolygon falls through to else which throws.
 */
fun describeGeometryLocal(type: GeometryTypeLocal): String {
    return when (type) {
        is GeometryTypeLocal.Point -> "Point"
        is GeometryTypeLocal.LineString -> "LineString"
        is GeometryTypeLocal.Polygon -> "Polygon"
        // BUG C3: Missing MultiPolygon branch - falls to else and throws
        is GeometryTypeLocal.GeometryCollection -> "GeometryCollection"
        else -> throw IllegalArgumentException("Unknown geometry type")
    }
}

/**
 * Sealed class representing query filters.
 *
 * BUG C4: The serialization registry only includes BoundingBoxFilter and PolygonFilter.
 * RadiusFilter is defined but not registered, causing serialization/deserialization
 * to fail at runtime.
 */
sealed class QueryFilterLocal {
    data class BoundingBoxFilter(
        val minLat: Double, val minLng: Double,
        val maxLat: Double, val maxLng: Double
    ) : QueryFilterLocal()

    data class PolygonFilter(val points: List<GeoPointLocal>) : QueryFilterLocal()

    data class RadiusFilter(
        val centerLat: Double,
        val centerLng: Double,
        val radiusKm: Double
    ) : QueryFilterLocal()
}

// BUG C4: RadiusFilter is NOT in the registered types set
val registeredFilterTypes = setOf(
    QueryFilterLocal.BoundingBoxFilter::class,
    QueryFilterLocal.PolygonFilter::class
    // Missing: QueryFilterLocal.RadiusFilter::class
)

fun serializeFilterLocal(filter: QueryFilterLocal): String {
    if (filter::class !in registeredFilterTypes) {
        throw IllegalArgumentException("Unregistered filter type: ${filter::class.simpleName}")
    }
    return when (filter) {
        is QueryFilterLocal.BoundingBoxFilter -> """{"type":"bbox","minLat":${filter.minLat},"minLng":${filter.minLng},"maxLat":${filter.maxLat},"maxLng":${filter.maxLng}}"""
        is QueryFilterLocal.PolygonFilter -> """{"type":"polygon","points":${filter.points.size}}"""
        is QueryFilterLocal.RadiusFilter -> """{"type":"radius","centerLat":${filter.centerLat},"centerLng":${filter.centerLng},"radiusKm":${filter.radiusKm}}"""
    }
}

fun deserializeFilterLocal(json: String): QueryFilterLocal {
    return when {
        json.contains("\"type\":\"bbox\"") -> QueryFilterLocal.BoundingBoxFilter(0.0, 0.0, 1.0, 1.0)
        json.contains("\"type\":\"polygon\"") -> QueryFilterLocal.PolygonFilter(emptyList())
        json.contains("\"type\":\"radius\"") -> QueryFilterLocal.RadiusFilter(0.0, 0.0, 0.0)
        else -> throw IllegalArgumentException("Unknown filter type in JSON")
    }
}
