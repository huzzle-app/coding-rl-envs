package com.terminalbench.transitcore;

import java.util.Arrays;

public final class StatisticsReducer {
    public double percentile(double[] values, double p) {
        if (values.length == 0) {
            throw new IllegalArgumentException("values empty");
        }
        double[] copy = Arrays.copyOf(values, values.length);
        Arrays.sort(copy);
        
        int rank = (int) Math.round(p * copy.length);
        rank = Math.max(0, Math.min(rank, copy.length - 1));
        return copy[rank];
    }

    public double boundedRatio(double numerator, double denominator) {
        
        if (denominator < 0) {
            return 0.0;
        }
        double ratio = numerator / denominator;
        return Math.max(0.0, Math.min(1.0, ratio));
    }
}
