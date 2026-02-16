package com.pulsemap.core

// =============================================================================
// Null safety stubs: Kotlin null safety pitfalls.
// Bugs: B1 (platform type NPE), B2 (!! on map get), B3 (nullable column),
//        B4 (unsafe cast)
// =============================================================================

/**
 * Parse WKT geometry string. Simulates a Java library that returns null for
 * empty/invalid geometries.
 *
 * BUG B1: When the geometry is empty/invalid, the underlying parser returns null.
 * But the caller uses !! or treats the result as non-null (platform type behavior),
 * causing NullPointerException at runtime.
 */
fun parseGeometryLocal(wkt: String): String? {
    // Simulates Java interop: returns null for EMPTY geometries
    val javaResult: String? = if (wkt.contains("EMPTY") || wkt.isEmpty()) null else wkt
    // BUG B1: Should return null safely, but throws NPE via ?: throw pattern
    return javaResult ?: throw NullPointerException("Null geometry from platform type")
}

/**
 * Safely parse WKT geometry string.
 *
 * BUG B1: Also throws NPE on empty/invalid WKT instead of returning null.
 */
fun safeParseGeometryLocal(wkt: String): String? {
    // BUG B1: Throws instead of returning null for empty/invalid WKT
    if (wkt.isEmpty() || wkt.contains("EMPTY")) {
        throw NullPointerException("Cannot parse empty WKT")
    }
    return wkt
}

/**
 * Look up a value in a cache map.
 *
 * BUG B2: Uses the !! (double-bang) operator on map.get(), which throws
 * NullPointerException if the key is not in the map. Should use safe access
 * (map[key] without !!) or map.getOrDefault().
 */
fun cacheLookupLocal(cache: Map<String, String>, key: String): String? {
    // BUG B2: !! throws NPE when key doesn't exist in the map
    return cache[key]!!
}

data class SensorRecordLocal(val id: String, val name: String?, val value: Double)

/**
 * Insert a sensor record into the database.
 *
 * BUG B3: When name is null, throws IllegalStateException instead of handling
 * it gracefully (e.g., using a default value or allowing the nullable column).
 * In the production code, the ?.let pattern skips setting the column entirely.
 */
fun insertRecordLocal(record: SensorRecordLocal): Boolean {
    // BUG B3: Throws on null name instead of using a default or nullable column
    val nameForDb: String = record.name ?: throw IllegalStateException("name is null but column is NOT NULL")
    return nameForDb.isNotEmpty()
}

data class SimpleReading(val id: String, val value: Double)

/**
 * Safely cast deserialized input to SimpleReading.
 *
 * BUG B4: Uses unsafe cast (as) instead of safe cast (as?). When the input
 * is the wrong type, throws ClassCastException instead of returning null.
 */
fun safeCastDeserializeLocal(input: Any): SimpleReading? {
    // BUG B4: Unsafe cast throws ClassCastException for wrong types
    return input as SimpleReading
}

data class HttpResponseLocal(val statusCode: Int, val body: String)

/**
 * Handle deserialization of request input.
 *
 * BUG B4: Uses unsafe cast, throwing ClassCastException for wrong input types
 * instead of returning 400 Bad Request.
 */
fun handleDeserializeRequestLocal(input: Any): HttpResponseLocal {
    // BUG B4: Unsafe cast instead of safe cast with error handling
    val reading = input as SimpleReading
    return HttpResponseLocal(200, "OK: ${reading.id}")
}
