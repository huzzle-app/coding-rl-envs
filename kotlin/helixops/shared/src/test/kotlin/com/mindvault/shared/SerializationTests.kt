package com.helixops.shared

import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull

/**
 * Tests for serialization utilities.
 *
 * Bug-specific tests:
 *   F7 - parseDynamic returns Map<String, Any> which is not serializable back to JSON;
 *        should return JsonObject/JsonElement instead
 */
class SerializationTests {

    // =========================================================================
    // F7: Map<String, Any> instead of JsonElement
    // =========================================================================

    @Test
    fun test_json_element_used() {
        
        // back to JSON by kotlinx.serialization (no serializer for Any)
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"name": "doc1", "count": 5}"""
        val result = utils.parseDynamic(jsonStr)
        assertTrue(
            result.usesJsonElement,
            "parseDynamic should return JsonElement/JsonObject, not Map<String, Any>"
        )
    }

    @Test
    fun test_no_map_string_any() {
        
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"key": "value", "nested": {"inner": 42}}"""
        val result = utils.parseDynamic(jsonStr)
        assertFalse(
            result.returnsMapStringAny,
            "parseDynamic should NOT return Map<String, Any>; use JsonElement for type safety"
        )
        assertTrue(
            result.canRoundTrip,
            "Parsed result should be serializable back to JSON string"
        )
    }

    // =========================================================================
    // Baseline: Serialization fundamentals
    // =========================================================================

    @Test
    fun test_parse_simple_json() {
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"name": "test"}"""
        val result = utils.parseDynamic(jsonStr)
        assertNotNull(result.data, "Parsed JSON should produce a non-null result")
    }

    @Test
    fun test_parse_nested_json() {
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"outer": {"inner": "value"}}"""
        val result = utils.parseDynamic(jsonStr)
        assertNotNull(result.data, "Nested JSON should be parsed")
    }

    @Test
    fun test_parse_array_json() {
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"items": [1, 2, 3]}"""
        val result = utils.parseDynamic(jsonStr)
        assertNotNull(result.data, "JSON with arrays should be parsed")
    }

    @Test
    fun test_parse_empty_object() {
        val utils = SerializationUtilsFixture()
        val result = utils.parseDynamic("{}")
        assertNotNull(result.data, "Empty JSON object should be parsed")
    }

    @Test
    fun test_parse_preserves_string_values() {
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"name": "hello world"}"""
        val result = utils.parseDynamic(jsonStr)
        assertTrue(result.data.toString().contains("hello world"), "String values should be preserved")
    }

    @Test
    fun test_parse_preserves_numeric_values() {
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"count": 42, "price": 9.99}"""
        val result = utils.parseDynamic(jsonStr)
        assertTrue(result.data.toString().contains("42"), "Numeric values should be preserved")
    }

    @Test
    fun test_parse_boolean_values() {
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"active": true, "deleted": false}"""
        val result = utils.parseDynamic(jsonStr)
        assertNotNull(result.data, "JSON with booleans should be parsed")
    }

    @Test
    fun test_parse_null_values() {
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"name": null}"""
        val result = utils.parseDynamic(jsonStr)
        assertNotNull(result.data, "JSON with null values should be parsed")
    }

    @Test
    fun test_parse_deeply_nested_json() {
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"level1": {"level2": {"level3": "deep"}}}"""
        val result = utils.parseDynamic(jsonStr)
        assertNotNull(result.data, "Deeply nested JSON should be parsed without error")
    }

    @Test
    fun test_parse_json_with_special_characters() {
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"text": "hello \"world\" & <foo>"}"""
        val result = utils.parseDynamic(jsonStr)
        assertNotNull(result.data, "JSON with special characters should be parsed")
    }

    @Test
    fun test_parse_json_with_unicode() {
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"greeting": "こんにちは"}"""
        val result = utils.parseDynamic(jsonStr)
        assertNotNull(result.data, "JSON with unicode characters should be parsed")
    }

    @Test
    fun test_parse_json_with_mixed_types() {
        val utils = SerializationUtilsFixture()
        val jsonStr = """{"name": "test", "count": 10, "active": true, "data": null, "tags": ["a","b"]}"""
        val result = utils.parseDynamic(jsonStr)
        assertNotNull(result.data, "JSON with mixed value types should be parsed")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    data class DynamicParseResult(
        val data: Any,
        val usesJsonElement: Boolean,
        val returnsMapStringAny: Boolean,
        val canRoundTrip: Boolean
    )

    class SerializationUtilsFixture {
        fun parseDynamic(jsonStr: String): DynamicParseResult {
            
            val data = mapOf("raw" to jsonStr) // Simulating Map<String, Any> return type
            return DynamicParseResult(
                data = data,
                usesJsonElement = false, 
                returnsMapStringAny = true, 
                canRoundTrip = false 
            )
        }
    }
}
