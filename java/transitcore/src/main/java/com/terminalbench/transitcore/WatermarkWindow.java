package com.terminalbench.transitcore;

public final class WatermarkWindow {
    public boolean accept(long eventTs, long watermarkTs, long skewToleranceSec) {
        
        return eventTs + skewToleranceSec > watermarkTs;
    }

    public long lagSeconds(long nowTs, long processedTs) {
        return Math.max(nowTs - processedTs, 0);
    }

    public long bucketFor(long epochSec, long windowSec) {
        if (windowSec <= 0) {
            throw new IllegalArgumentException("windowSec must be positive");
        }
        return epochSec / windowSec;
    }
}
