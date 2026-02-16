package com.vertexgrid.analytics;

import com.vertexgrid.analytics.service.AnalyticsService;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.TestFactory;

import java.util.*;
import java.util.stream.IntStream;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Stress test matrix for analytics module bugs.
 * Cycles through 2 modes testing BUGs G4 and K5.
 */
@Tag("stress")
public class HyperMatrixTest {

    private final AnalyticsService analyticsService = new AnalyticsService();

    @TestFactory
    Stream<DynamicTest> analytics_hyper_matrix() {
        final int total = 500;
        return IntStream.range(0, total).mapToObj(idx ->
            DynamicTest.dynamicTest("analytics_hyper_" + idx, () -> {
                int mode = idx % 2;
                switch (mode) {
                    case 0 -> pagination_matrix(idx);
                    default -> patternMatch_matrix(idx);
                }
            })
        );
    }

    // BUG G4: Pagination off-by-one (0-based formula with 1-based page numbers)
    private void pagination_matrix(int idx) {
        int listSize = 20 + (idx % 50);
        int pageSize = 5 + (idx % 10);
        List<Integer> items = new ArrayList<>();
        for (int i = 0; i < listSize; i++) {
            items.add(i);
        }

        // Page 1 should return the first pageSize items (indices 0..pageSize-1)
        List<Integer> page1 = analyticsService.paginate(items, 1, pageSize);

        // Bug: formula uses page * pageSize (0-based) but callers pass 1-based
        // Page 1 with pageSize 10 returns items 10-19 instead of 0-9
        assertFalse(page1.isEmpty(), "Page 1 should not be empty for list of size " + listSize);
        assertEquals(0, page1.get(0),
            "Page 1 should start with the first item (index 0). " +
            "Got " + page1.get(0) + " instead, indicating off-by-one in pagination formula. " +
            "listSize=" + listSize + ", pageSize=" + pageSize);
    }

    // BUG K5: Pattern matching unsafe cast (List<?> to List<String>)
    private void patternMatch_matrix(int idx) {
        // Lists of non-String elements should be handled gracefully
        List<Integer> intList = List.of(idx, idx + 1, idx + 2);

        // Bug: describeMetric casts List<?> to List<String> without validation
        // When list contains Integers, accessing elements as String throws ClassCastException
        assertDoesNotThrow(() -> analyticsService.describeMetric(intList),
            "describeMetric should handle List<Integer> without ClassCastException");

        String result = analyticsService.describeMetric(intList);
        assertNotNull(result, "describeMetric should return non-null for List<Integer>");
        // Should describe it as a list metric, not crash
        assertTrue(result.contains("metric") || result.contains("list") || result.contains("List"),
            "Result should describe the metric type, got: " + result);
    }
}
