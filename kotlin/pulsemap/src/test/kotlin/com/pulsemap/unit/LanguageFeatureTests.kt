package com.pulsemap.unit

import com.pulsemap.core.*
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertNotNull
import kotlin.test.assertIs

/**
 * Tests for Kotlin language features: extension functions, inline/reified generics.
 *
 * Bug-specific tests:
 *   E1 - Extension function shadowed by member function with same name
 *   E2 - Reified type info erased when not using inline+reified
 */
class LanguageFeatureTests {

    // =========================================================================
    // E1: Extension function shadowed by member function
    // =========================================================================

    @Test
    fun test_extension_not_shadowed() {
        val points = GeoPolygonLocal(
            points = listOf(
                PointLocal(1.0, 2.0),
                PointLocal(3.0, 4.0),
                PointLocal(5.0, 6.0)
            )
        )
        val bbox = points.boundingBox()
        assertEquals(1.0, bbox.minLat, "minLat should be 1.0")
        assertEquals(2.0, bbox.minLng, "minLng should be 2.0")
        assertEquals(5.0, bbox.maxLat, "maxLat should be 5.0")
        assertEquals(6.0, bbox.maxLng, "maxLng should be 6.0")
    }

    @Test
    fun test_bounding_box_correct() {
        val polygon = GeoPolygonLocal(
            points = listOf(
                PointLocal(-10.0, -20.0),
                PointLocal(10.0, 20.0),
                PointLocal(0.0, 0.0)
            )
        )
        val bbox = polygon.boundingBox()
        assertEquals(-10.0, bbox.minLat, "Should find minimum latitude")
        assertEquals(-20.0, bbox.minLng, "Should find minimum longitude")
        assertEquals(10.0, bbox.maxLat, "Should find maximum latitude")
        assertEquals(20.0, bbox.maxLng, "Should find maximum longitude")
    }

    // =========================================================================
    // E2: Reified type info not preserved
    // =========================================================================

    @Test
    fun test_reified_type_preserved() {
        val json = """{"value":42}"""
        val result = deserializeLocal<IntWrapper>(json)
        assertNotNull(result, "Deserialization should preserve type via reified")
        assertIs<IntWrapper>(result, "Result should be IntWrapper type")
    }

    @Test
    fun test_deserialize_generic() {
        val jsonInt = """{"value":100}"""
        val jsonStr = """{"text":"hello"}"""

        val intResult = deserializeLocal<IntWrapper>(jsonInt)
        val strResult = deserializeLocal<StringWrapper>(jsonStr)

        assertNotNull(intResult)
        assertNotNull(strResult)
        assertIs<IntWrapper>(intResult, "Should deserialize as IntWrapper")
        assertIs<StringWrapper>(strResult, "Should deserialize as StringWrapper")
    }

    // =========================================================================
    // Baseline: Kotlin language feature tests
    // =========================================================================

    @Test
    fun test_extension_function_on_string() {
        fun String.removeWhitespace(): String = this.replace("\\s".toRegex(), "")
        val result = "hello world".removeWhitespace()
        assertEquals("helloworld", result)
    }

    @Test
    fun test_extension_property() {
        val list = listOf(1, 2, 3, 4, 5)
        val secondElement = list.getOrNull(1)
        assertEquals(2, secondElement)
    }

    @Test
    fun test_inline_function_performance() {
        val result = inlineTransform(10) { it * 2 }
        assertEquals(20, result)
    }

    @Test
    fun test_lambda_with_receiver() {
        val result = buildString {
            append("Hello")
            append(", ")
            append("World")
        }
        assertEquals("Hello, World", result)
    }

    @Test
    fun test_scope_function_apply() {
        val point = PointLocal(0.0, 0.0).let { base ->
            PointLocal(base.lat + 1.0, base.lng + 2.0)
        }
        assertEquals(1.0, point.lat)
        assertEquals(2.0, point.lng)
    }

    @Test
    fun test_higher_order_function() {
        val numbers = listOf(1, 2, 3, 4, 5)
        val evens = numbers.filter { it % 2 == 0 }
        assertEquals(listOf(2, 4), evens)
    }

    // =========================================================================
    // Local helpers for baseline tests
    // =========================================================================

    private inline fun <T> inlineTransform(value: T, transform: (T) -> T): T = transform(value)
}
