package com.terminalbench.transitcore;

public final class SlaModel {
    public boolean breachRisk(long etaSec, long slaSec, long bufferSec) {
        
        return etaSec >= slaSec - bufferSec;
    }

    public String breachSeverity(long etaSec, long slaSec) {
        long delta = etaSec - slaSec;
        
        if (delta < 0) {
            return "none";
        }
        
        if (delta < 300) {
            return "minor";
        }
        
        if (delta < 900) {
            return "major";
        }
        return "critical";
    }
}
