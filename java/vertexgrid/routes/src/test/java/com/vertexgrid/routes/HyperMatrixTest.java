package com.vertexgrid.routes;

import com.vertexgrid.routes.service.RouteService;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.TestFactory;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.stream.IntStream;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Stress test matrix for routes module bugs.
 * Cycles through 3 modes testing BUGs F1, F2, and F3.
 */
@Tag("stress")
public class HyperMatrixTest {

    private final RouteService routeService = new RouteService();

    @TestFactory
    Stream<DynamicTest> routes_hyper_matrix() {
        final int total = 500;
        return IntStream.range(0, total).mapToObj(idx ->
            DynamicTest.dynamicTest("routes_hyper_" + idx, () -> {
                int mode = idx % 3;
                switch (mode) {
                    case 0 -> doublePrecision_matrix(idx);
                    case 1 -> bigDecimalEquals_matrix(idx);
                    default -> divisionRounding_matrix(idx);
                }
            })
        );
    }

    // BUG F1: calculateRouteCost uses double arithmetic without rounding
    private void doublePrecision_matrix(int idx) {
        // Pairs that produce floating-point imprecision
        double[][] cases = {
            {10.0, 2.55},    // 10.0 * 2.55 should be 25.50
            {7.0, 1.43},     // 7.0 * 1.43 should be 10.01
            {100.0, 0.33},   // 100.0 * 0.33 should be 33.00
            {3.0, 3.33},     // 3.0 * 3.33 should be 9.99
            {15.0, 2.67},    // 15.0 * 2.67 should be 40.05
        };
        double[] c = cases[idx % cases.length];
        double distance = c[0] + (idx / cases.length) * 0.1;
        double rate = c[1];

        double cost = routeService.calculateRouteCost(distance, rate);

        // The expected cost with proper rounding
        BigDecimal expectedBd = BigDecimal.valueOf(distance)
            .multiply(BigDecimal.valueOf(rate))
            .setScale(2, RoundingMode.HALF_UP);
        double expected = expectedBd.doubleValue();

        // Bug: double arithmetic without rounding causes cent-level errors
        assertEquals(expected, cost, 0.001,
            "calculateRouteCost(" + distance + ", " + rate + ") should be " +
            expected + " but got " + cost + " (floating-point precision error)");
    }

    // BUG F2: isRouteCostEqual uses BigDecimal.equals instead of compareTo
    private void bigDecimalEquals_matrix(int idx) {
        // BigDecimal("1.0") and BigDecimal("1.00") are numerically equal but .equals returns false
        int scale1 = 1 + (idx % 3); // 1, 2, or 3
        int scale2 = scale1 + 1;    // 2, 3, or 4

        BigDecimal value = new BigDecimal(10 + idx % 100);
        BigDecimal cost1 = value.setScale(scale1, RoundingMode.HALF_UP);
        BigDecimal cost2 = value.setScale(scale2, RoundingMode.HALF_UP);

        // These are numerically equal (e.g., 10.0 == 10.00)
        assertEquals(0, cost1.compareTo(cost2), "Sanity: values should be numerically equal");

        // Bug: BigDecimal.equals() checks scale, so 10.0.equals(10.00) is false
        boolean result = routeService.isRouteCostEqual(cost1, cost2);
        assertTrue(result,
            "isRouteCostEqual(" + cost1 + ", " + cost2 + ") should be true " +
            "(same numeric value, different scale). " +
            "Bug: BigDecimal.equals checks scale, should use compareTo");
    }

    // BUG F3: calculateCostPerMile divides without RoundingMode
    private void divisionRounding_matrix(int idx) {
        // Non-terminating decimals like 1/3, 1/7, 1/9 throw ArithmeticException
        BigDecimal[] totals = {
            new BigDecimal("100.00"),
            new BigDecimal("50.00"),
            new BigDecimal("33.33"),
        };
        BigDecimal[] miles = {
            new BigDecimal("3"),   // 100/3 = 33.333... (non-terminating)
            new BigDecimal("7"),   // 50/7 = 7.14285... (non-terminating)
            new BigDecimal("9"),   // 33.33/9 = 3.703... (non-terminating)
        };

        BigDecimal total = totals[idx % totals.length];
        BigDecimal mile = miles[idx % miles.length];

        // Bug: BigDecimal.divide without RoundingMode throws ArithmeticException
        // for non-terminating decimal results
        assertDoesNotThrow(() -> routeService.calculateCostPerMile(total, mile),
            "calculateCostPerMile(" + total + ", " + mile + ") should not throw " +
            "ArithmeticException. Need to specify RoundingMode for non-terminating decimals.");

        BigDecimal result = routeService.calculateCostPerMile(total, mile);
        assertNotNull(result);
        assertTrue(result.compareTo(BigDecimal.ZERO) > 0,
            "Cost per mile should be positive");
    }
}
