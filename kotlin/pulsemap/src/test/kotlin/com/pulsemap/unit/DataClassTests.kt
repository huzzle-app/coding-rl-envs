package com.pulsemap.unit

import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNotSame
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith

/**
 * Tests for data classes, sealed hierarchies, equality, hashCode, and serialization registration.
 *
 * Bug-specific tests:
 *   C1 - SensorReading with DoubleArray equality (reference vs structural)
 *   C2 - GeoPoint copy() shallow-copies MutableList
 *   C3 - Sealed GeometryType missing when-branch for MultiPolygon
 *   C4 - QueryFilter sealed serialization missing RadiusFilter subclass
 */
class DataClassTests {

    // =========================================================================
    // C1: data class with DoubleArray - equals()/hashCode() use reference equality
    // =========================================================================

    @Test
    fun test_sensor_reading_equality() {
        
        // Two SensorReadings with identical content should be equal, but won't be
        // because DoubleArray.equals() checks reference, not structural equality.
        val reading1 = SensorReadingLocal(
            id = "r1",
            sensorId = "s1",
            values = doubleArrayOf(1.0, 2.0, 3.0),
            latitude = 40.7128,
            longitude = -74.0060,
            timestamp = 1700000000L
        )
        val reading2 = SensorReadingLocal(
            id = "r1",
            sensorId = "s1",
            values = doubleArrayOf(1.0, 2.0, 3.0),
            latitude = 40.7128,
            longitude = -74.0060,
            timestamp = 1700000000L
        )
        // This SHOULD pass (structurally equal), but FAILS because DoubleArray uses reference equality
        assertEquals(reading1, reading2, "SensorReadings with identical values should be equal")
    }

    @Test
    fun test_deduplication_works() {
        
        val reading1 = SensorReadingLocal(
            id = "r1", sensorId = "s1", values = doubleArrayOf(10.0, 20.0),
            latitude = 51.5074, longitude = -0.1278, timestamp = 1700000001L
        )
        val reading2 = SensorReadingLocal(
            id = "r1", sensorId = "s1", values = doubleArrayOf(10.0, 20.0),
            latitude = 51.5074, longitude = -0.1278, timestamp = 1700000001L
        )
        val set = setOf(reading1, reading2)
        // Should deduplicate to 1 entry, but fails because hashCode uses reference for DoubleArray
        assertEquals(1, set.size, "Identical sensor readings should deduplicate in a set")
    }

    // =========================================================================
    // C2: copy() shares MutableList (shallow copy)
    // =========================================================================

    @Test
    fun test_copy_deep_mutable_list() {
        
        val original = GeoPointLocal(lat = 40.0, lng = -74.0, annotations = mutableListOf("park"))
        val copied = original.copy()
        copied.annotations.add("building")

        // The copy and original should have INDEPENDENT annotation lists
        assertNotEquals(
            original.annotations.size,
            copied.annotations.size,
            "Copied GeoPoint should have independent annotation list"
        )
    }

    @Test
    fun test_original_not_mutated_after_copy() {
        
        val original = GeoPointLocal(lat = 35.6762, lng = 139.6503, annotations = mutableListOf("temple"))
        val copied = original.copy()
        copied.annotations.add("shrine")
        copied.annotations.add("garden")

        assertEquals(
            1,
            original.annotations.size,
            "Original GeoPoint annotations should not be mutated when copy is modified"
        )
    }

    // =========================================================================
    // C3: Sealed GeometryType missing when-branch
    // =========================================================================

    @Test
    fun test_sealed_when_all_branches() {
        
        val types = listOf(
            GeometryTypeLocal.Point,
            GeometryTypeLocal.LineString,
            GeometryTypeLocal.Polygon,
            GeometryTypeLocal.MultiPolygon,
            GeometryTypeLocal.GeometryCollection
        )
        for (type in types) {
            val name = describeGeometryLocal(type)
            assertTrue(name.isNotEmpty(), "describeGeometry should handle ${type::class.simpleName}")
        }
    }

    @Test
    fun test_multi_polygon_handled() {
        
        val result = describeGeometryLocal(GeometryTypeLocal.MultiPolygon)
        assertEquals("MultiPolygon", result, "MultiPolygon should be handled in when expression")
    }

    // =========================================================================
    // C4: Sealed serialization missing RadiusFilter
    // =========================================================================

    @Test
    fun test_sealed_serialization_registered() {
        
        val filters = listOf(
            QueryFilterLocal.BoundingBoxFilter(minLat = 0.0, minLng = 0.0, maxLat = 1.0, maxLng = 1.0),
            QueryFilterLocal.PolygonFilter(points = listOf(GeoPointLocal(0.0, 0.0))),
            QueryFilterLocal.RadiusFilter(centerLat = 40.0, centerLng = -74.0, radiusKm = 5.0)
        )
        for (filter in filters) {
            val serialized = serializeFilterLocal(filter)
            assertTrue(serialized.isNotEmpty(), "Filter ${filter::class.simpleName} should serialize")
            val deserialized = deserializeFilterLocal(serialized)
            assertEquals(
                filter::class,
                deserialized::class,
                "Deserialized filter should match original type"
            )
        }
    }

    @Test
    fun test_radius_filter_deserializes() {
        
        val filter = QueryFilterLocal.RadiusFilter(centerLat = 34.0522, centerLng = -118.2437, radiusKm = 10.0)
        val json = serializeFilterLocal(filter)
        val restored = deserializeFilterLocal(json)
        assertTrue(restored is QueryFilterLocal.RadiusFilter, "Should deserialize as RadiusFilter")
        assertEquals(10.0, (restored as QueryFilterLocal.RadiusFilter).radiusKm)
    }

    // =========================================================================
    // Baseline: data class basics
    // =========================================================================

    @Test
    fun test_data_class_toString_contains_fields() {
        val reading = SensorReadingLocal(
            id = "r1", sensorId = "s1", values = doubleArrayOf(1.0),
            latitude = 0.0, longitude = 0.0, timestamp = 0L
        )
        val str = reading.toString()
        assertTrue(str.contains("r1"), "toString should contain the id field")
        assertTrue(str.contains("s1"), "toString should contain the sensorId field")
    }

    @Test
    fun test_data_class_component_functions() {
        val reading = SensorReadingLocal(
            id = "abc", sensorId = "xyz", values = doubleArrayOf(),
            latitude = 1.0, longitude = 2.0, timestamp = 999L
        )
        assertEquals("abc", reading.component1())
        assertEquals("xyz", reading.component2())
        assertEquals(1.0, reading.component4())
        assertEquals(999L, reading.component6())
    }

    @Test
    fun test_data_class_copy_basic_fields() {
        val original = SensorReadingLocal(
            id = "r1", sensorId = "s1", values = doubleArrayOf(5.0),
            latitude = 10.0, longitude = 20.0, timestamp = 100L
        )
        val modified = original.copy(id = "r2", latitude = 99.0)
        assertEquals("r2", modified.id)
        assertEquals(99.0, modified.latitude)
        assertEquals("s1", modified.sensorId)
    }

    @Test
    fun test_geopoint_equality() {
        val a = GeoPointLocal(lat = 1.0, lng = 2.0)
        val b = GeoPointLocal(lat = 1.0, lng = 2.0)
        assertEquals(a, b, "GeoPoints with same coordinates should be equal")
    }

    @Test
    fun test_geopoint_hashcode_consistency() {
        val a = GeoPointLocal(lat = 48.8566, lng = 2.3522)
        val b = GeoPointLocal(lat = 48.8566, lng = 2.3522)
        assertEquals(a.hashCode(), b.hashCode(), "Equal GeoPoints should have same hashCode")
    }

    @Test
    fun test_geopoint_not_equal_different_coords() {
        val a = GeoPointLocal(lat = 1.0, lng = 2.0)
        val b = GeoPointLocal(lat = 3.0, lng = 4.0)
        assertNotEquals(a, b)
    }

    @Test
    fun test_sealed_class_is_subtype() {
        val filter: QueryFilterLocal = QueryFilterLocal.BoundingBoxFilter(0.0, 0.0, 1.0, 1.0)
        assertTrue(filter is QueryFilterLocal, "BoundingBoxFilter should be a QueryFilter")
    }

    @Test
    fun test_sealed_class_exhaustive_when() {
        val filter: QueryFilterLocal = QueryFilterLocal.PolygonFilter(listOf(GeoPointLocal(0.0, 0.0)))
        val typeName = when (filter) {
            is QueryFilterLocal.BoundingBoxFilter -> "bbox"
            is QueryFilterLocal.PolygonFilter -> "polygon"
            is QueryFilterLocal.RadiusFilter -> "radius"
        }
        assertEquals("polygon", typeName)
    }

    @Test
    fun test_geometry_type_sealed_object_identity() {
        val a: GeometryTypeLocal = GeometryTypeLocal.Point
        val b: GeometryTypeLocal = GeometryTypeLocal.Point
        assertTrue(a === b, "Sealed object singletons should have identity equality")
    }

    @Test
    fun test_data_class_destructuring() {
        val (lat, lng) = GeoPointLocal(lat = 55.0, lng = 37.0)
        assertEquals(55.0, lat)
        assertEquals(37.0, lng)
    }

    @Test
    fun test_sensor_reading_hashcode_differs_for_different_data() {
        val a = SensorReadingLocal("a", "s1", doubleArrayOf(1.0), 0.0, 0.0, 0L)
        val b = SensorReadingLocal("b", "s2", doubleArrayOf(2.0), 0.0, 0.0, 0L)
        assertNotEquals(a.hashCode(), b.hashCode(), "Different readings should have different hashCodes (usually)")
    }

    @Test
    fun test_mutable_list_default_is_empty() {
        val point = GeoPointLocal(lat = 0.0, lng = 0.0)
        assertTrue(point.annotations.isEmpty(), "Default annotations should be empty")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    // C1: data class with DoubleArray (buggy - uses reference equality)
    data class SensorReadingLocal(
        val id: String,
        val sensorId: String,
        val values: DoubleArray, 
        val latitude: Double,
        val longitude: Double,
        val timestamp: Long
    )

    // C2: GeoPoint with MutableList (buggy - shallow copy)
    data class GeoPointLocal(
        val lat: Double,
        val lng: Double,
        val annotations: MutableList<String> = mutableListOf()
    )

    // C3: Sealed class with missing when branch
    sealed class GeometryTypeLocal {
        object Point : GeometryTypeLocal()
        object LineString : GeometryTypeLocal()
        object Polygon : GeometryTypeLocal()
        object MultiPolygon : GeometryTypeLocal()
        object GeometryCollection : GeometryTypeLocal()
    }

    
    private fun describeGeometryLocal(type: GeometryTypeLocal): String {
        return when (type) {
            is GeometryTypeLocal.Point -> "Point"
            is GeometryTypeLocal.LineString -> "LineString"
            is GeometryTypeLocal.Polygon -> "Polygon"
            
            is GeometryTypeLocal.GeometryCollection -> "GeometryCollection"
            else -> throw IllegalArgumentException("Unknown geometry type")
        }
    }

    // C4: Sealed serialization
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

    
    private val registeredTypes = setOf(
        QueryFilterLocal.BoundingBoxFilter::class,
        QueryFilterLocal.PolygonFilter::class
        // Missing: QueryFilterLocal.RadiusFilter::class
    )

    private fun serializeFilterLocal(filter: QueryFilterLocal): String {
        if (filter::class !in registeredTypes) {
            throw IllegalArgumentException("Unregistered filter type: ${filter::class.simpleName}")
        }
        return when (filter) {
            is QueryFilterLocal.BoundingBoxFilter -> """{"type":"bbox","minLat":${filter.minLat},"minLng":${filter.minLng},"maxLat":${filter.maxLat},"maxLng":${filter.maxLng}}"""
            is QueryFilterLocal.PolygonFilter -> """{"type":"polygon","points":${filter.points.size}}"""
            is QueryFilterLocal.RadiusFilter -> """{"type":"radius","centerLat":${filter.centerLat},"centerLng":${filter.centerLng},"radiusKm":${filter.radiusKm}}"""
        }
    }

    private fun deserializeFilterLocal(json: String): QueryFilterLocal {
        return when {
            json.contains("\"type\":\"bbox\"") -> QueryFilterLocal.BoundingBoxFilter(0.0, 0.0, 1.0, 1.0)
            json.contains("\"type\":\"polygon\"") -> QueryFilterLocal.PolygonFilter(emptyList())
            json.contains("\"type\":\"radius\"") -> QueryFilterLocal.RadiusFilter(0.0, 0.0, 0.0)
            else -> throw IllegalArgumentException("Unknown filter type in JSON")
        }
    }
}
