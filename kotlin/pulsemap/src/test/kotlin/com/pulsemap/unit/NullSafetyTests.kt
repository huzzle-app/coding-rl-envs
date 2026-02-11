package com.pulsemap.unit

import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith

/**
 * Tests for Kotlin null safety: platform types, double-bang (!!), nullable columns,
 * and safe casts.
 *
 * Bug-specific tests:
 *   B1 - Platform type from Java/external source returns null without null-check
 *   B2 - Cache miss uses !! on map.get() instead of safe access
 *   B3 - Nullable database column inserts null into NOT NULL column
 *   B4 - Unsafe cast on deserialization input instead of safe cast (as?)
 */
class NullSafetyTests {

    // =========================================================================
    // B1: Platform type null check for empty geometry
    // =========================================================================

    @Test
    fun test_platform_type_null_check() {
        
        // When the geometry is empty, the Java lib returns null, but Kotlin treats it as non-null.
        val result = parseGeometryLocal("POINT EMPTY")
        // Should not crash with NPE; should return null or empty safely
        assertNull(result, "Empty geometry should return null, not crash with NPE")
    }

    @Test
    fun test_empty_geometry_handled() {
        
        val emptyWktStrings = listOf("POINT EMPTY", "LINESTRING EMPTY", "POLYGON EMPTY", "")
        for (wkt in emptyWktStrings) {
            val result = safeParseGeometryLocal(wkt)
            // Should not throw; should return null for empty/invalid
            assertNull(result, "Empty/invalid WKT '$wkt' should return null")
        }
    }

    // =========================================================================
    // B2: Cache miss and double-bang (!!)
    // =========================================================================

    @Test
    fun test_cache_miss_returns_404() {
        
        val cache = mutableMapOf("key1" to "value1")
        val result = cacheLookupLocal(cache, "nonexistent_key")
        assertNull(result, "Cache miss should return null, not throw via !!")
    }

    @Test
    fun test_no_double_bang_on_map_get() {
        
        val cache = mutableMapOf<String, String>()
        // This should NOT throw; should handle missing key gracefully
        val result = cacheLookupLocal(cache, "missing")
        assertNull(result, "Empty cache lookup should return null safely")
    }

    // =========================================================================
    // B3: Nullable column handling
    // =========================================================================

    @Test
    fun test_nullable_column_insert() {
        
        val record = SensorRecordLocal(id = "sr1", name = null, value = 42.0)
        val insertResult = insertRecordLocal(record)
        assertTrue(insertResult, "Inserting record with null name should succeed (use default or nullable column)")
    }

    @Test
    fun test_not_null_constraint_handled() {
        
        val record = SensorRecordLocal(id = "sr2", name = null, value = 99.0)
        // Should either use a default value or the column should be nullable
        val result = insertRecordLocal(record)
        assertTrue(result, "Null name should be handled without constraint violation")
    }

    // =========================================================================
    // B4: Safe cast on deserialization
    // =========================================================================

    @Test
    fun test_safe_cast_on_deserialize() {
        
        // When the input is the wrong type, it throws ClassCastException instead of returning null/400
        val wrongTypeInput: Any = "this is a string, not a SensorReading"
        val result = safeCastDeserializeLocal(wrongTypeInput)
        assertNull(result, "Wrong type input should return null via safe cast, not throw ClassCastException")
    }

    @Test
    fun test_wrong_type_returns_400() {
        
        val wrongInput: Any = 12345
        val response = handleDeserializeRequestLocal(wrongInput)
        assertEquals(400, response.statusCode, "Wrong type should return 400 Bad Request")
        assertTrue(response.body.contains("Invalid"), "Response body should indicate invalid input")
    }

    // =========================================================================
    // Baseline: null safety fundamentals
    // =========================================================================

    @Test
    fun test_nullable_string_safe_call() {
        val name: String? = null
        val length = name?.length
        assertNull(length, "Safe call on null should return null")
    }

    @Test
    fun test_elvis_operator_default() {
        val name: String? = null
        val result = name ?: "default"
        assertEquals("default", result)
    }

    @Test
    fun test_non_null_assertion_throws_on_null() {
        val value: String? = null
        assertFailsWith<NullPointerException> {
            @Suppress("ALWAYS_NULL")
            value!!
        }
    }

    @Test
    fun test_let_block_on_non_null() {
        val name: String? = "hello"
        var called = false
        name?.let {
            called = true
            assertEquals("hello", it)
        }
        assertTrue(called, "let block should be invoked on non-null")
    }

    @Test
    fun test_let_block_skipped_on_null() {
        val name: String? = null
        var called = false
        name?.let { called = true }
        assertFalse(called, "let block should not be invoked on null")
    }

    @Test
    fun test_safe_cast_returns_null_for_wrong_type() {
        val obj: Any = 42
        val str = obj as? String
        assertNull(str, "Safe cast to wrong type should return null")
    }

    @Test
    fun test_safe_cast_succeeds_for_correct_type() {
        val obj: Any = "hello"
        val str = obj as? String
        assertNotNull(str)
        assertEquals("hello", str)
    }

    @Test
    fun test_nullable_collection_filter_not_null() {
        val items: List<String?> = listOf("a", null, "b", null, "c")
        val nonNull = items.filterNotNull()
        assertEquals(3, nonNull.size)
        assertFalse(nonNull.any { it == null })
    }

    @Test
    fun test_require_not_null_throws() {
        assertFailsWith<IllegalArgumentException> {
            requireNotNull(null) { "Value must not be null" }
        }
    }

    @Test
    fun test_check_not_null_succeeds() {
        val value: String? = "present"
        val result = checkNotNull(value)
        assertEquals("present", result)
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    
    private fun parseGeometryLocal(wkt: String): String? {
        // Simulates a Java library that returns null for EMPTY geometries
        
        val javaResult: String? = if (wkt.contains("EMPTY") || wkt.isEmpty()) null else wkt
        
        return javaResult ?: throw NullPointerException("Null geometry from platform type")
    }

    private fun safeParseGeometryLocal(wkt: String): String? {
        
        if (wkt.isEmpty() || wkt.contains("EMPTY")) {
            
            throw NullPointerException("Cannot parse empty WKT")
        }
        return wkt
    }

    
    private fun cacheLookupLocal(cache: Map<String, String>, key: String): String? {
        
        return cache[key]!!
    }

    
    data class SensorRecordLocal(val id: String, val name: String?, val value: Double)

    private fun insertRecordLocal(record: SensorRecordLocal): Boolean {
        
        val nameForDb: String = record.name ?: throw IllegalStateException("name is null but column is NOT NULL")
        // Simulates constraint violation
        return nameForDb.isNotEmpty()
    }

    
    data class SimpleReading(val id: String, val value: Double)

    private fun safeCastDeserializeLocal(input: Any): SimpleReading? {
        
        return input as SimpleReading
    }

    data class HttpResponseLocal(val statusCode: Int, val body: String)

    private fun handleDeserializeRequestLocal(input: Any): HttpResponseLocal {
        
        val reading = input as SimpleReading
        return HttpResponseLocal(200, "OK: ${reading.id}")
    }
}
