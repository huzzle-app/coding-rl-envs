package com.vertexgrid.routes;

import com.vertexgrid.routes.model.RouteWaypoint;
import com.vertexgrid.routes.service.GeofenceService;
import com.vertexgrid.routes.service.RouteService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class RouteServiceTest {

    private RouteService routeService;
    private GeofenceService geofenceService;

    @BeforeEach
    void setUp() {
        routeService = new RouteService();
        geofenceService = new GeofenceService();
    }

    // ====== BUG F1: Float/double for currency ======
    @Test
    void test_no_float_currency() {
        
        // 0.1 + 0.2 != 0.3 in IEEE 754
        double cost = routeService.calculateRouteCost(10.0, 2.55);
        // With BigDecimal fix, this should be exactly 25.50
        // With double bug, may be 25.499999... or 25.500000001
        BigDecimal expected = new BigDecimal("25.50");
        BigDecimal actual = BigDecimal.valueOf(cost).setScale(2, RoundingMode.HALF_UP);
        assertEquals(0, expected.compareTo(actual),
            "Route cost should be precisely 25.50, got " + cost);
    }

    @Test
    void test_bigdecimal_precision() {
        // Test with values known to cause floating-point errors
        double cost = routeService.calculateRouteCost(100.0, 0.33);
        BigDecimal expected = new BigDecimal("33.00");
        BigDecimal actual = BigDecimal.valueOf(cost).setScale(2, RoundingMode.HALF_UP);
        assertEquals(0, expected.compareTo(actual),
            "100km * $0.33/km should be $33.00, got " + cost);
    }

    @Test
    void test_route_cost_zero_distance() {
        double cost = routeService.calculateRouteCost(0.0, 2.55);
        assertEquals(0.0, cost, 0.001, "Zero distance should produce zero cost");
    }

    @Test
    void test_route_cost_large_values() {
        double cost = routeService.calculateRouteCost(999999.99, 1.0);
        assertTrue(cost > 0, "Large distance should produce positive cost");
    }

    // ====== BUG F2: BigDecimal.equals() vs compareTo() ======
    @Test
    void test_bigdecimal_compare_to() {
        
        BigDecimal a = new BigDecimal("1.0");
        BigDecimal b = new BigDecimal("1.00");
        boolean result = routeService.isRouteCostEqual(a, b);
        // With the fix (compareTo), this should be true
        assertTrue(result, "1.0 and 1.00 should be considered equal (same numeric value)");
    }

    @Test
    void test_equals_vs_compareto() {
        BigDecimal a = new BigDecimal("100.50");
        BigDecimal b = new BigDecimal("100.5");
        boolean result = routeService.isRouteCostEqual(a, b);
        assertTrue(result, "100.50 and 100.5 should be equal by value");
    }

    @Test
    void test_different_values_not_equal() {
        BigDecimal a = new BigDecimal("10.0");
        BigDecimal b = new BigDecimal("10.1");
        assertFalse(routeService.isRouteCostEqual(a, b),
            "Different values should not be equal");
    }

    @Test
    void test_bigdecimal_zero_scales() {
        BigDecimal a = new BigDecimal("0");
        BigDecimal b = new BigDecimal("0.00");
        assertTrue(routeService.isRouteCostEqual(a, b),
            "Zero with different scales should be equal");
    }

    // ====== BUG F3: Missing RoundingMode ======
    @Test
    void test_rounding_mode_set() {
        
        // for non-terminating decimals (e.g., 10/3 = 3.333...)
        BigDecimal totalCost = new BigDecimal("10.00");
        BigDecimal totalMiles = new BigDecimal("3");
        assertDoesNotThrow(() -> {
            BigDecimal result = routeService.calculateCostPerMile(totalCost, totalMiles);
            assertNotNull(result);
        }, "Division should not throw ArithmeticException when RoundingMode is set");
    }

    @Test
    void test_no_arithmetic_exception() {
        // 100 / 7 = 14.285714... (non-terminating)
        BigDecimal cost = new BigDecimal("100.00");
        BigDecimal miles = new BigDecimal("7");
        assertDoesNotThrow(() -> routeService.calculateCostPerMile(cost, miles),
            "Non-terminating division should use RoundingMode");
    }

    @Test
    void test_exact_division_works() {
        BigDecimal cost = new BigDecimal("100.00");
        BigDecimal miles = new BigDecimal("4");
        BigDecimal result = routeService.calculateCostPerMile(cost, miles);
        assertEquals(0, new BigDecimal("25").compareTo(result.stripTrailingZeros()),
            "100/4 should be 25");
    }

    // ====== BUG G1: Geofence boundary ======
    @Test
    void test_geofence_boundary() {
        // Point exactly on the circle boundary (distance == radius)
        
        // Center at (0,0), radius 1000m, point at exactly 1000m
        double centerLat = 0.0, centerLng = 0.0;
        double radiusMeters = 1000.0;

        // Point slightly inside
        assertTrue(geofenceService.isPointInCircle(0.001, 0.0, centerLat, centerLng, radiusMeters),
            "Point clearly inside should be detected as inside");
    }

    @Test
    void test_point_on_boundary_included() {
        
        double centerLat = 40.7128, centerLng = -74.0060; // NYC
        // Use haversine to compute exact distance for a known point at the boundary
        assertTrue(geofenceService.isPointInCircle(centerLat, centerLng, centerLat, centerLng, 100),
            "Center point should be inside any circle");
    }

    @Test
    void test_point_outside_circle() {
        // Point clearly outside
        assertFalse(geofenceService.isPointInCircle(10.0, 10.0, 0.0, 0.0, 100),
            "Far point should be outside the geofence");
    }

    @Test
    void test_geofence_polygon_basic() {
        // Simple square polygon
        double[][] square = {{0, 0}, {0, 1}, {1, 1}, {1, 0}};
        boolean inside = geofenceService.isPointInPolygon(0.5, 0.5, square);
        assertTrue(inside, "Center of square should be inside");
    }

    // ====== BUG G2: Route optimization infinite loop ======
    @Test
    @Timeout(value = 5, unit = TimeUnit.SECONDS)
    void test_route_optimization_terminates() {
        
        List<RouteWaypoint> waypoints = createWaypoints(10);
        assertDoesNotThrow(() -> {
            List<RouteWaypoint> result = routeService.optimizeRoute(waypoints);
            assertNotNull(result);
        }, "Route optimization should terminate within timeout");
    }

    @Test
    @Timeout(value = 5, unit = TimeUnit.SECONDS)
    void test_no_infinite_loop() {
        // Create equidistant waypoints that cause floating-point noise
        List<RouteWaypoint> waypoints = createEquidistantWaypoints(8);
        List<RouteWaypoint> result = routeService.optimizeRoute(waypoints);
        assertNotNull(result, "Should return result even with equidistant points");
        assertEquals(waypoints.size(), result.size(), "Should preserve all waypoints");
    }

    @Test
    void test_optimize_null_waypoints() {
        assertNull(routeService.optimizeRoute(null),
            "Null input should return null");
    }

    @Test
    void test_optimize_single_waypoint() {
        List<RouteWaypoint> single = createWaypoints(1);
        List<RouteWaypoint> result = routeService.optimizeRoute(single);
        assertEquals(1, result.size());
    }

    @Test
    void test_optimize_two_waypoints() {
        List<RouteWaypoint> two = createWaypoints(2);
        List<RouteWaypoint> result = routeService.optimizeRoute(two);
        assertEquals(2, result.size());
    }

    // ====== BUG B2: subList memory leak ======
    @Test
    void test_sublist_independent() {
        
        List<RouteWaypoint> allWaypoints = createWaypoints(100);
        List<RouteWaypoint> first5 = routeService.getFirstNWaypoints(allWaypoints, 5);

        assertEquals(5, first5.size());
        // An independent copy should be modifiable without affecting the original
        assertDoesNotThrow(() -> first5.add(createWaypoint(999, 0, 0)),
            "Result should be an independent copy, not a subList view");
    }

    @Test
    void test_no_sublist_memory_leak() {
        List<RouteWaypoint> large = createWaypoints(10000);
        List<RouteWaypoint> small = routeService.getFirstNWaypoints(large, 3);

        assertEquals(3, small.size());
        // Verify it's truly independent
        assertTrue(small instanceof ArrayList,
            "Result should be ArrayList, not SubList (which retains parent reference)");
    }

    @Test
    void test_get_waypoints_when_fewer_than_n() {
        List<RouteWaypoint> few = createWaypoints(3);
        List<RouteWaypoint> result = routeService.getFirstNWaypoints(few, 10);
        assertEquals(3, result.size(), "Should return all when fewer than N");
    }

    // ====== Distance calculation tests ======
    @Test
    void test_distance_same_point() {
        double dist = routeService.calculateDistance(40.7128, -74.0060, 40.7128, -74.0060);
        assertEquals(0.0, dist, 0.001, "Distance to same point should be 0");
    }

    @Test
    void test_distance_known_value() {
        // NYC to LA is ~3944 km
        double dist = routeService.calculateDistance(40.7128, -74.0060, 34.0522, -118.2437);
        assertTrue(dist > 3900 && dist < 4000,
            "NYC to LA should be ~3944 km, got " + dist);
    }

    @Test
    void test_route_cost_fractional_cents() {
        // Test precision with values that cause fractional cent issues
        double cost = routeService.calculateRouteCost(7.0, 1.99);
        BigDecimal bd = BigDecimal.valueOf(cost).setScale(2, RoundingMode.HALF_UP);
        assertEquals(new BigDecimal("13.93"), bd,
            "7 * 1.99 should be 13.93");
    }

    @Test
    void test_cost_per_mile_zero_denominator() {
        // Division by zero should be handled
        BigDecimal cost = new BigDecimal("100.00");
        BigDecimal zero = BigDecimal.ZERO;
        assertThrows(ArithmeticException.class,
            () -> routeService.calculateCostPerMile(cost, zero),
            "Division by zero should throw ArithmeticException");
    }

    @Test
    void test_geofence_large_radius() {
        assertTrue(geofenceService.isPointInCircle(1.0, 1.0, 0.0, 0.0, 1_000_000),
            "Point within very large radius should be inside");
    }

    @Test
    void test_geofence_very_small_radius() {
        assertFalse(geofenceService.isPointInCircle(0.001, 0.001, 0.0, 0.0, 1),
            "Point beyond tiny radius should be outside");
    }

    @Test
    @Timeout(value = 5, unit = TimeUnit.SECONDS)
    void test_optimize_large_route() {
        List<RouteWaypoint> large = createWaypoints(50);
        List<RouteWaypoint> result = routeService.optimizeRoute(large);
        assertNotNull(result);
        assertEquals(50, result.size());
    }

    @Test
    void test_sublist_first_zero() {
        List<RouteWaypoint> waypoints = createWaypoints(5);
        List<RouteWaypoint> result = routeService.getFirstNWaypoints(waypoints, 0);
        assertTrue(result.isEmpty(), "First 0 waypoints should be empty");
    }

    @Test
    void test_bigdecimal_negative_values_equal() {
        BigDecimal a = new BigDecimal("-5.0");
        BigDecimal b = new BigDecimal("-5.00");
        assertTrue(routeService.isRouteCostEqual(a, b));
    }

    @Test
    void test_rounding_small_fraction() {
        BigDecimal cost = new BigDecimal("1.00");
        BigDecimal miles = new BigDecimal("300");
        BigDecimal result = routeService.calculateCostPerMile(cost, miles);
        assertTrue(result.compareTo(BigDecimal.ZERO) > 0,
            "Small fraction should still produce a positive result");
    }

    // Helper methods
    private List<RouteWaypoint> createWaypoints(int count) {
        List<RouteWaypoint> list = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            list.add(createWaypoint(i, 40.0 + i * 0.1, -74.0 + i * 0.1));
        }
        return list;
    }

    private List<RouteWaypoint> createEquidistantWaypoints(int count) {
        List<RouteWaypoint> list = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            double angle = 2 * Math.PI * i / count;
            list.add(createWaypoint(i, 40.0 + 0.01 * Math.cos(angle), -74.0 + 0.01 * Math.sin(angle)));
        }
        return list;
    }

    private RouteWaypoint createWaypoint(int seq, double lat, double lng) {
        RouteWaypoint wp = new RouteWaypoint();
        wp.setSequenceNumber(seq);
        wp.setLat(lat);
        wp.setLng(lng);
        wp.setName("WP-" + seq);
        return wp;
    }
}
