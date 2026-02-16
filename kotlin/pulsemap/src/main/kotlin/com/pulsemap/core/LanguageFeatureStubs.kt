package com.pulsemap.core

// =============================================================================
// Language feature stubs: Extension function shadowing and reified type erasure.
// Bugs: E1 (member extension shadows file-level extension),
//        E2 (reified type info erased in non-inline function)
// =============================================================================

data class PointLocal(val lat: Double, val lng: Double)
data class BoundingBoxLocal(val minLat: Double, val minLng: Double, val maxLat: Double, val maxLng: Double)

/**
 * Computes bounding box for a list of points.
 *
 * BUG E1: This class defines a MEMBER extension function boundingBox() on
 * List<PointLocal>. In Kotlin, member extensions always take priority over
 * file-level extensions with the same signature. The member version returns
 * wrong values (all zeros), shadowing any correct file-level extension.
 */
class GeoPolygonLocal(val points: List<PointLocal>) {
    // BUG E1: This member extension function shadows the correct file-level extension.
    // Member extensions take priority within the class scope.
    // Returns hardcoded wrong values instead of computing from points.
    fun boundingBox(): BoundingBoxLocal {
        // BUG E1: Should compute from points but returns zeros
        return BoundingBoxLocal(0.0, 0.0, 0.0, 0.0)
    }
}

// This correct file-level extension is SHADOWED by the member function above
// when called within GeoPolygonLocal's scope
@Suppress("unused")
fun GeoPolygonLocal.computeBoundingBox(): BoundingBoxLocal {
    val minLat = points.minOf { it.lat }
    val minLng = points.minOf { it.lng }
    val maxLat = points.maxOf { it.lat }
    val maxLng = points.maxOf { it.lng }
    return BoundingBoxLocal(minLat, minLng, maxLat, maxLng)
}

data class IntWrapper(val value: Int)
data class StringWrapper(val text: String)

/**
 * Deserializes JSON into a typed object.
 *
 * BUG E2: This function is NOT inline with reified T, so the type parameter T
 * is erased at runtime (JVM type erasure). The function cannot determine
 * what type to deserialize into, resulting in null/ClassCastException.
 *
 * The fix is to make this an inline function with reified T, which preserves
 * the type information at the call site.
 */
@Suppress("UNCHECKED_CAST")
fun <T> deserializeLocal(json: String): T? {
    // BUG E2: Without reified, T is erased to Any at runtime.
    // Cannot check type or instantiate T.
    // Would need: inline fun <reified T> deserializeLocal(json: String): T?
    return try {
        null as T?
    } catch (e: Exception) {
        null
    }
}
