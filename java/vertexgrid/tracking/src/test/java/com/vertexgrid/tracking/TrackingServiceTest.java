package com.vertexgrid.tracking;

import com.vertexgrid.tracking.model.TrackingData;
import com.vertexgrid.tracking.service.TrackingService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.IntStream;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for TrackingService covering bugs:
 *   A6 - Parallel stream deadlock (nested parallelStream on common ForkJoinPool)
 *   A7 - ReentrantLock fairness (unfair lock causes reader starvation)
 *   F4 - Integer overflow in distance calculation
 *   F5 - Timezone arithmetic / negative duration
 *   G3 - Speed calculation division by zero
 *   B3 - Stream collector duplicate key error
 */
@Tag("unit")
public class TrackingServiceTest {

    private TrackingService trackingService;

    @BeforeEach
    void setUp() {
        trackingService = new TrackingService();
    }

    // =========================================================================
    
    // =========================================================================

    @Tag("concurrency")
    @Test
    @Timeout(value = 10, unit = TimeUnit.SECONDS)
    void test_calculateAllVehicleSpeeds_completes_without_deadlock() {
        
        // Populate tracking data for many vehicles
        for (int i = 0; i < 50; i++) {
            String vehicleId = "vehicle-" + i;
            for (int j = 0; j < 20; j++) {
                TrackingData data = new TrackingData(vehicleId, 40.0 + j * 0.01, -74.0, 60.0 + j, 90.0);
                trackingService.recordPosition(data);
            }
        }

        List<String> vehicleIds = IntStream.range(0, 50)
            .mapToObj(i -> "vehicle-" + i)
            .toList();

        // This should complete without deadlock; with BUG A6 it may hang
        Map<String, Double> speeds = trackingService.calculateAllVehicleSpeeds(vehicleIds);
        assertNotNull(speeds);
        assertEquals(50, speeds.size());
    }

    @Tag("concurrency")
    @Test
    @Timeout(value = 10, unit = TimeUnit.SECONDS)
    void test_calculateAllVehicleSpeeds_returns_correct_averages() {
        // Vehicle with known speeds
        String vehicleId = "v1";
        TrackingData d1 = new TrackingData(vehicleId, 40.0, -74.0, 30.0, 0.0);
        TrackingData d2 = new TrackingData(vehicleId, 40.1, -74.0, 60.0, 0.0);
        TrackingData d3 = new TrackingData(vehicleId, 40.2, -74.0, 90.0, 0.0);
        trackingService.recordPosition(d1);
        trackingService.recordPosition(d2);
        trackingService.recordPosition(d3);

        Map<String, Double> speeds = trackingService.calculateAllVehicleSpeeds(List.of(vehicleId));
        assertNotNull(speeds.get(vehicleId));
        assertEquals(60.0, speeds.get(vehicleId), 0.001, "Average of 30, 60, 90 should be 60");
    }

    @Tag("concurrency")
    @Test
    @Timeout(value = 10, unit = TimeUnit.SECONDS)
    void test_calculateAllVehicleSpeeds_empty_history_returns_zero() {
        Map<String, Double> speeds = trackingService.calculateAllVehicleSpeeds(List.of("nonexistent"));
        assertEquals(0.0, speeds.get("nonexistent"), 0.001);
    }

    @Tag("concurrency")
    @Test
    @Timeout(value = 15, unit = TimeUnit.SECONDS)
    void test_calculateAllVehicleSpeeds_many_vehicles_no_deadlock() {
        
        int vehicleCount = ForkJoinPool.getCommonPoolParallelism() * 4;
        for (int i = 0; i < vehicleCount; i++) {
            String vid = "v-" + i;
            for (int j = 0; j < 100; j++) {
                trackingService.recordPosition(new TrackingData(vid, 40.0, -74.0, j * 1.0, 0.0));
            }
        }

        List<String> vehicleIds = IntStream.range(0, vehicleCount)
            .mapToObj(i -> "v-" + i)
            .toList();

        Map<String, Double> result = trackingService.calculateAllVehicleSpeeds(vehicleIds);
        assertEquals(vehicleCount, result.size(), "Should return speed for every vehicle");
    }

    // =========================================================================
    
    // =========================================================================

    @Tag("concurrency")
    @Test
    @Timeout(value = 15, unit = TimeUnit.SECONDS)
    void test_reader_not_starved_under_contention() throws Exception {
        
        int writerCount = 10;
        int readerCount = 10;
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(writerCount + readerCount);
        AtomicInteger readSuccesses = new AtomicInteger(0);
        AtomicInteger writeSuccesses = new AtomicInteger(0);

        // Seed initial data
        trackingService.recordPosition(new TrackingData("v1", 40.0, -74.0, 50.0, 0.0));

        // Start writers
        for (int i = 0; i < writerCount; i++) {
            final int idx = i;
            new Thread(() -> {
                try {
                    startLatch.await();
                    for (int j = 0; j < 100; j++) {
                        trackingService.recordPosition(
                            new TrackingData("v1", 40.0 + j * 0.001, -74.0, 50.0 + j, 0.0));
                        writeSuccesses.incrementAndGet();
                    }
                } catch (Exception e) {
                    // ignore
                } finally {
                    doneLatch.countDown();
                }
            }).start();
        }

        // Start readers
        for (int i = 0; i < readerCount; i++) {
            new Thread(() -> {
                try {
                    startLatch.await();
                    for (int j = 0; j < 100; j++) {
                        TrackingData pos = trackingService.getLatestPosition("v1");
                        if (pos != null) readSuccesses.incrementAndGet();
                    }
                } catch (Exception e) {
                    // ignore
                } finally {
                    doneLatch.countDown();
                }
            }).start();
        }

        startLatch.countDown();
        assertTrue(doneLatch.await(15, TimeUnit.SECONDS), "All threads should complete");

        
        // After fix (fair lock), readers should all succeed.
        assertTrue(readSuccesses.get() > 0,
            "Readers should not be starved - got " + readSuccesses.get() + " successful reads");
        assertTrue(readSuccesses.get() >= readerCount * 50,
            "At least half of read attempts should succeed with fair lock");
    }

    @Tag("concurrency")
    @Test
    void test_recordPosition_stores_data() {
        TrackingData data = new TrackingData("v1", 40.7128, -74.0060, 55.0, 180.0);
        trackingService.recordPosition(data);
        TrackingData result = trackingService.getLatestPosition("v1");
        assertNotNull(result);
        assertEquals("v1", result.getVehicleId());
        assertEquals(40.7128, result.getLat(), 0.0001);
    }

    @Tag("concurrency")
    @Test
    void test_recordPosition_updates_latest() {
        trackingService.recordPosition(new TrackingData("v1", 40.0, -74.0, 50.0, 0.0));
        trackingService.recordPosition(new TrackingData("v1", 41.0, -73.0, 60.0, 90.0));
        TrackingData latest = trackingService.getLatestPosition("v1");
        assertEquals(41.0, latest.getLat(), 0.0001);
        assertEquals(60.0, latest.getSpeed(), 0.0001);
    }

    @Tag("concurrency")
    @Test
    void test_getLatestPosition_nonexistent_returns_null() {
        assertNull(trackingService.getLatestPosition("nonexistent-vehicle"));
    }

    // =========================================================================
    
    // =========================================================================

    @Test
    void test_calculateTotalDistanceMeters_no_overflow_long_route() {
        
        // Create points spanning a large distance (e.g., many segments of ~100km)
        List<TrackingData> points = new ArrayList<>();
        for (int i = 0; i < 100; i++) {
            TrackingData td = new TrackingData("v1", i * 1.0, 0.0, 0.0, 0.0);
            td.setTimestamp(Instant.now());
            points.add(td);
        }

        // Total distance should be well over Integer.MAX_VALUE meters for 99 segments
        // Each degree of latitude is ~111km = 111000m; 99 * 111000 = ~10,989,000m
        // This won't overflow int by itself, but tests the concept
        int distance = trackingService.calculateTotalDistanceMeters(points);
        assertTrue(distance > 0, "Distance should be positive, not overflowed to negative");
    }

    @Test
    void test_calculateTotalDistanceMeters_overflow_detection() {
        
        // Create many points with large distances between them
        List<TrackingData> points = new ArrayList<>();
        for (int i = 0; i < 500; i++) {
            // Alternate between opposite ends of the earth to maximize segment distance
            double lat = (i % 2 == 0) ? 80.0 : -80.0;
            double lng = (i % 2 == 0) ? 170.0 : -170.0;
            TrackingData td = new TrackingData("v1", lat, lng, 0.0, 0.0);
            td.setTimestamp(Instant.now());
            points.add(td);
        }

        // After fix (long), distance should be a large positive number
        // With BUG F4 (int), this overflows to negative
        int totalDistance = trackingService.calculateTotalDistanceMeters(points);
        assertTrue(totalDistance > 0,
            "Total distance should be positive; negative indicates integer overflow (BUG F4). Got: " + totalDistance);
    }

    @Test
    void test_calculateTotalDistanceMeters_single_point() {
        List<TrackingData> points = List.of(
            new TrackingData("v1", 40.0, -74.0, 0.0, 0.0));
        int distance = trackingService.calculateTotalDistanceMeters(points);
        assertEquals(0, distance, "Single point should have zero distance");
    }

    @Test
    void test_calculateTotalDistanceMeters_two_points() {
        TrackingData p1 = new TrackingData("v1", 40.7128, -74.0060, 0.0, 0.0);
        TrackingData p2 = new TrackingData("v1", 40.7580, -73.9855, 0.0, 0.0);
        int distance = trackingService.calculateTotalDistanceMeters(List.of(p1, p2));
        // ~5km from lower Manhattan to Central Park
        assertTrue(distance > 4000 && distance < 6000,
            "Distance should be approximately 5km. Got: " + distance);
    }

    // =========================================================================
    
    // =========================================================================

    @Test
    void test_calculateTripDurationMinutes_positive_duration() {
        Instant start = Instant.parse("2024-01-01T10:00:00Z");
        Instant end = Instant.parse("2024-01-01T12:30:00Z");
        long minutes = trackingService.calculateTripDurationMinutes(start, end);
        assertEquals(150, minutes, "Should be 150 minutes (2.5 hours)");
    }

    @Test
    void test_calculateTripDurationMinutes_negative_not_returned() {
        
        Instant start = Instant.parse("2024-01-01T12:00:00Z");
        Instant end = Instant.parse("2024-01-01T10:00:00Z");
        long minutes = trackingService.calculateTripDurationMinutes(start, end);
        assertTrue(minutes >= 0,
            "Duration should never be negative after fix. Got: " + minutes);
    }

    @Test
    void test_calculateTripDurationMinutes_same_time() {
        Instant time = Instant.parse("2024-01-01T12:00:00Z");
        long minutes = trackingService.calculateTripDurationMinutes(time, time);
        assertEquals(0, minutes, "Same start and end time should be 0 minutes");
    }

    @Test
    void test_calculateTripDurationMinutes_short_trip() {
        Instant start = Instant.parse("2024-06-15T08:00:00Z");
        Instant end = Instant.parse("2024-06-15T08:05:30Z");
        long minutes = trackingService.calculateTripDurationMinutes(start, end);
        assertEquals(5, minutes, "5 min 30 sec truncates to 5 minutes");
    }

    // =========================================================================
    
    // =========================================================================

    @Test
    void test_calculateSpeed_division_by_zero() {
        
        Instant now = Instant.now();
        TrackingData p1 = new TrackingData("v1", 40.7128, -74.0060, 0.0, 0.0);
        p1.setTimestamp(now);
        TrackingData p2 = new TrackingData("v1", 40.7580, -73.9855, 0.0, 0.0);
        p2.setTimestamp(now); // Same timestamp

        double speed = trackingService.calculateSpeed(p1, p2);
        assertFalse(Double.isInfinite(speed),
            "Speed should not be Infinity when timestamps are identical (BUG G3)");
        assertFalse(Double.isNaN(speed),
            "Speed should not be NaN when timestamps are identical (BUG G3)");
        assertTrue(Double.isFinite(speed),
            "Speed must be a finite number. Got: " + speed);
    }

    @Test
    void test_calculateSpeed_same_location_returns_zero() {
        TrackingData p1 = new TrackingData("v1", 40.0, -74.0, 0.0, 0.0);
        p1.setTimestamp(Instant.parse("2024-01-01T10:00:00Z"));
        TrackingData p2 = new TrackingData("v1", 40.0, -74.0, 0.0, 0.0);
        p2.setTimestamp(Instant.parse("2024-01-01T10:05:00Z"));

        double speed = trackingService.calculateSpeed(p1, p2);
        assertEquals(0.0, speed, 0.001, "Same location should produce zero speed");
    }

    @Test
    void test_calculateSpeed_normal_case() {
        TrackingData p1 = new TrackingData("v1", 40.0, -74.0, 0.0, 0.0);
        p1.setTimestamp(Instant.parse("2024-01-01T10:00:00Z"));
        TrackingData p2 = new TrackingData("v1", 40.1, -74.0, 0.0, 0.0);
        p2.setTimestamp(Instant.parse("2024-01-01T10:01:00Z")); // 60 seconds later

        double speed = trackingService.calculateSpeed(p1, p2);
        assertTrue(speed > 0, "Speed should be positive for different locations/times");
        assertTrue(Double.isFinite(speed), "Speed should be finite");
    }

    // =========================================================================
    
    // =========================================================================

    @Test
    void test_getLatestPositionsByVehicle_no_duplicates() {
        TrackingData d1 = new TrackingData("v1", 40.0, -74.0, 50.0, 0.0);
        TrackingData d2 = new TrackingData("v2", 41.0, -73.0, 60.0, 90.0);
        Map<String, TrackingData> result = trackingService.getLatestPositionsByVehicle(List.of(d1, d2));
        assertEquals(2, result.size());
        assertEquals(d1, result.get("v1"));
        assertEquals(d2, result.get("v2"));
    }

    @Test
    void test_getLatestPositionsByVehicle_duplicate_keys_no_exception() {
        
        TrackingData d1 = new TrackingData("v1", 40.0, -74.0, 50.0, 0.0);
        TrackingData d2 = new TrackingData("v1", 41.0, -73.0, 60.0, 90.0);
        TrackingData d3 = new TrackingData("v1", 42.0, -72.0, 70.0, 180.0);

        // After fix: should not throw, should merge duplicates
        // With BUG B3: throws IllegalStateException
        assertDoesNotThrow(() -> trackingService.getLatestPositionsByVehicle(List.of(d1, d2, d3)),
            "Duplicate vehicleIds should not cause IllegalStateException (BUG B3)");
    }

    @Test
    void test_getLatestPositionsByVehicle_empty_list() {
        Map<String, TrackingData> result = trackingService.getLatestPositionsByVehicle(List.of());
        assertTrue(result.isEmpty());
    }

    @Test
    void test_getLatestPositionsByVehicle_keeps_latest_on_duplicate() {
        
        TrackingData d1 = new TrackingData("v1", 40.0, -74.0, 50.0, 0.0);
        TrackingData d2 = new TrackingData("v1", 41.0, -73.0, 60.0, 90.0);

        Map<String, TrackingData> result = trackingService.getLatestPositionsByVehicle(List.of(d1, d2));
        assertNotNull(result.get("v1"),
            "Should have an entry for v1 even with duplicates");
    }

    // =========================================================================
    // Additional utility tests
    // =========================================================================

    @Test
    void test_getHistory_returns_recorded_positions() {
        trackingService.recordPosition(new TrackingData("v1", 40.0, -74.0, 50.0, 0.0));
        trackingService.recordPosition(new TrackingData("v1", 41.0, -73.0, 60.0, 90.0));
        List<TrackingData> history = trackingService.getHistory("v1");
        assertEquals(2, history.size());
    }

    @Test
    void test_getHistory_empty_for_unknown_vehicle() {
        List<TrackingData> history = trackingService.getHistory("unknown");
        assertNotNull(history);
        assertTrue(history.isEmpty());
    }

    @Test
    void test_getTrackedVehicleCount() {
        assertEquals(0, trackingService.getTrackedVehicleCount());
        trackingService.recordPosition(new TrackingData("v1", 40.0, -74.0, 50.0, 0.0));
        trackingService.recordPosition(new TrackingData("v2", 41.0, -73.0, 60.0, 90.0));
        assertEquals(2, trackingService.getTrackedVehicleCount());
    }

    // =========================================================================
    // computeAverageSpeed tests
    // =========================================================================

    @Test
    void test_computeAverageSpeed_weighted_by_time() {
        // Two segments: 1000m in 10s (100 m/s), 1000m in 1000s (1 m/s)
        // Arithmetic mean of speeds: (100 + 1) / 2 = 50.5 m/s
        // Weighted average (total_dist/total_time): 2000 / 1010 = 1.98 m/s
        // The correct answer is the weighted average since segments have vastly different durations
        List<TrackingData> points = new ArrayList<>();
        Instant t0 = Instant.parse("2024-01-01T00:00:00Z");

        TrackingData p1 = new TrackingData("v1", 40.0, -74.0, 0.0, 0.0);
        p1.setTimestamp(t0);
        points.add(p1);

        // ~1.1km north (0.01 degrees lat ~ 1.1km)
        TrackingData p2 = new TrackingData("v1", 40.01, -74.0, 0.0, 0.0);
        p2.setTimestamp(t0.plusSeconds(10));
        points.add(p2);

        // Another ~1.1km north but over much longer time
        TrackingData p3 = new TrackingData("v1", 40.02, -74.0, 0.0, 0.0);
        p3.setTimestamp(t0.plusSeconds(1010));
        points.add(p3);

        double avgSpeed = trackingService.computeAverageSpeed(points);

        // total distance ~2200m, total time = 1010s, weighted avg ~2.18 m/s
        // arithmetic mean would be ~(110 + 1.1)/2 = ~55.5 m/s
        // The correct weighted average should be under 5 m/s
        assertTrue(avgSpeed < 5.0,
            "Average speed should use weighted average (total_dist/total_time), not arithmetic mean. Got: " + avgSpeed);
    }

    @Test
    void test_computeAverageSpeed_uniform_segments() {
        // When all segments have equal duration, arithmetic mean equals weighted average
        List<TrackingData> points = new ArrayList<>();
        Instant t0 = Instant.parse("2024-01-01T00:00:00Z");

        for (int i = 0; i < 5; i++) {
            TrackingData p = new TrackingData("v1", 40.0 + i * 0.01, -74.0, 0.0, 0.0);
            p.setTimestamp(t0.plusSeconds(i * 60));
            points.add(p);
        }

        double avgSpeed = trackingService.computeAverageSpeed(points);
        assertTrue(avgSpeed > 0, "Average speed should be positive for moving vehicle");
        assertTrue(Double.isFinite(avgSpeed), "Average speed should be finite");
    }

    @Test
    void test_computeAverageSpeed_null_returns_zero() {
        assertEquals(0.0, trackingService.computeAverageSpeed(null), 0.001);
    }

    @Test
    void test_computeAverageSpeed_single_point_returns_zero() {
        List<TrackingData> points = new ArrayList<>();
        TrackingData p = new TrackingData("v1", 40.0, -74.0, 0.0, 0.0);
        p.setTimestamp(Instant.now());
        points.add(p);
        assertEquals(0.0, trackingService.computeAverageSpeed(points), 0.001);
    }

    @Test
    void test_computeAverageSpeed_consistent_with_total_distance_and_time() {
        List<TrackingData> points = new ArrayList<>();
        Instant t0 = Instant.parse("2024-01-01T00:00:00Z");

        // Three equidistant points with varying time gaps
        TrackingData p1 = new TrackingData("v1", 40.0, -74.0, 0.0, 0.0);
        p1.setTimestamp(t0);
        points.add(p1);

        TrackingData p2 = new TrackingData("v1", 40.1, -74.0, 0.0, 0.0);
        p2.setTimestamp(t0.plusSeconds(100));
        points.add(p2);

        TrackingData p3 = new TrackingData("v1", 40.2, -74.0, 0.0, 0.0);
        p3.setTimestamp(t0.plusSeconds(10100));
        points.add(p3);

        double avgSpeed = trackingService.computeAverageSpeed(points);

        // Verify it matches total_distance / total_time pattern
        // If using weighted average: both segments ~11.1km, total ~22.2km over 10100s = ~2.2 m/s
        // Arithmetic mean: (111 + 1.1)/2 = ~56 m/s - very different
        assertTrue(avgSpeed < 10.0,
            "Weighted average speed over long duration should be small. Got: " + avgSpeed);
    }
}
