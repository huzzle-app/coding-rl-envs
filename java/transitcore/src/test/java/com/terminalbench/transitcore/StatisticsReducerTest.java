package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class StatisticsReducerTest {
    @Test
    void percentileAndBoundedRatio() {
        StatisticsReducer reducer = new StatisticsReducer();
        assertEquals(5.0, reducer.percentile(new double[] {1, 3, 5, 7, 9}, 0.50), 1e-9);
        assertEquals(9.0, reducer.percentile(new double[] {1, 3, 5, 7, 9}, 1.0), 1e-9);

        assertEquals(0.0, reducer.boundedRatio(3, 0), 1e-9);
        assertEquals(0.4, reducer.boundedRatio(2, 5), 1e-9);
        assertEquals(1.0, reducer.boundedRatio(8, 5), 1e-9);
    }
}
