package com.vertexgrid.tracking;

import com.vertexgrid.tracking.model.TrackingData;
import com.vertexgrid.tracking.service.TrackingService;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.TestFactory;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.IntStream;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Stress test matrix for tracking module bugs.
 * Cycles through 3 modes testing BUGs G1 (return type), G3 (divide by zero),
 * and B3 (duplicate keys).
 */
@Tag("stress")
public class HyperMatrixTest {

    @TestFactory
    Stream<DynamicTest> tracking_hyper_matrix() {
        final int total = 500;
        return IntStream.range(0, total).mapToObj(idx ->
            DynamicTest.dynamicTest("tracking_hyper_" + idx, () -> {
                int mode = idx % 3;
                switch (mode) {
                    case 0 -> intReturnType_matrix(idx);
                    case 1 -> divideByZero_matrix(idx);
                    default -> duplicateKeys_matrix(idx);
                }
            })
        );
    }

    // BUG G1: calculateTotalDistanceMeters uses int (overflows for large routes)
    // Test verifies the return type should be long, not int
    private void intReturnType_matrix(int idx) throws Exception {
        // The method returns int but should return long to handle large distances
        java.lang.reflect.Method method = TrackingService.class.getMethod(
            "calculateTotalDistanceMeters", List.class);
        Class<?> returnType = method.getReturnType();

        // int cannot hold distances > 2,147,483,647 meters (2,147 km)
        // Long-haul routes and fleet-wide aggregation easily exceed this
        assertEquals(long.class, returnType,
            "calculateTotalDistanceMeters should return long (not " + returnType.getSimpleName() +
            ") to prevent integer overflow for routes > 2147 km");
    }

    // BUG G3: Division by zero in calculateSpeed when timestamps are identical
    private void divideByZero_matrix(int idx) {
        TrackingService service = new TrackingService();

        Instant now = Instant.now();

        TrackingData p1 = new TrackingData();
        p1.setVehicleId("speed-" + idx);
        p1.setLat(40.0 + (idx % 10) * 0.01);
        p1.setLng(-74.0);
        p1.setSpeed(60.0);
        p1.setTimestamp(now);

        TrackingData p2 = new TrackingData();
        p2.setVehicleId("speed-" + idx);
        p2.setLat(40.0 + (idx % 10) * 0.01 + 0.001);
        p2.setLng(-74.0);
        p2.setSpeed(60.0);
        p2.setTimestamp(now); // SAME timestamp

        double speed = service.calculateSpeed(p1, p2);

        assertFalse(Double.isInfinite(speed),
            "Speed should not be Infinity when timestamps are identical (div by zero)");
        assertFalse(Double.isNaN(speed),
            "Speed should not be NaN when timestamps are identical");
        assertTrue(speed >= 0 && speed < 1e12,
            "Speed should be a reasonable finite value, got: " + speed);
    }

    // BUG B3: Collectors.toMap throws IllegalStateException on duplicate vehicle IDs
    private void duplicateKeys_matrix(int idx) {
        TrackingService service = new TrackingService();
        List<TrackingData> dataPoints = new ArrayList<>();

        String vehicleId = "dup-vehicle-" + idx;

        for (int i = 0; i < 3; i++) {
            TrackingData td = new TrackingData();
            td.setVehicleId(vehicleId);
            td.setLat(40.0 + i * 0.01);
            td.setLng(-74.0 + i * 0.01);
            td.setSpeed(30.0 + i * 10);
            td.setTimestamp(Instant.now().plusSeconds(i * 60));
            dataPoints.add(td);
        }

        assertDoesNotThrow(() -> service.getLatestPositionsByVehicle(dataPoints),
            "getLatestPositionsByVehicle should handle duplicate vehicle IDs " +
            "without throwing IllegalStateException. Use merge function in toMap().");

        Map<String, TrackingData> result = service.getLatestPositionsByVehicle(dataPoints);
        assertNotNull(result);
        assertEquals(1, result.size(),
            "Should have exactly 1 entry per vehicle ID after merging duplicates");
        assertTrue(result.containsKey(vehicleId));
    }
}
