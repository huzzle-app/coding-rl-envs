package com.fleetpulse.routes.service;

import com.fleetpulse.routes.model.RouteWaypoint;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

@Service
public class RouteService {

    private static final Logger log = LoggerFactory.getLogger(RouteService.class);

    
    // Using double for financial and distance calculations -> precision errors
    // 0.1 + 0.2 != 0.3 with floating point
    // Fix: Use BigDecimal with explicit scale and rounding mode
    //
    
    // When optimizeRoute hangs, cost calculation is never reached for optimized routes.
    // Fixing BUG G2 (adding iteration limit) will reveal precision errors:
    //   1. Routes complete optimization successfully
    //   2. calculateRouteCost is called with precise distances from optimization
    //   3. Floating-point precision loss in cost calculation becomes apparent
    //   4. Invoice totals don't match expected values (off by pennies)
    // The precision bug is currently hidden because the system times out before billing.
    public double calculateRouteCost(double distanceKm, double ratePerKm) {
        
        // e.g., 10.0 * 2.55 might give 25.499999999... instead of 25.50
        double cost = distanceKm * ratePerKm;
        return cost; // No rounding -> cent-level errors accumulate
        // Fix: return BigDecimal.valueOf(distanceKm)
        //          .multiply(BigDecimal.valueOf(ratePerKm))
        //          .setScale(2, RoundingMode.HALF_UP)
        //          .doubleValue();
    }

    
    // new BigDecimal("1.0").equals(new BigDecimal("1.00")) returns FALSE
    // because equals checks scale, but compareTo only checks numeric value
    // Fix: Use compareTo() == 0 for value comparison
    public boolean isRouteCostEqual(BigDecimal cost1, BigDecimal cost2) {
        
        return cost1.equals(cost2);
        // Fix: return cost1.compareTo(cost2) == 0;
    }

    
    // Division without explicit rounding mode throws ArithmeticException
    // when result has non-terminating decimal representation
    // Fix: Always specify RoundingMode in BigDecimal division
    public BigDecimal calculateCostPerMile(BigDecimal totalCost, BigDecimal totalMiles) {
        
        return totalCost.divide(totalMiles);
        // Fix: return totalCost.divide(totalMiles, 4, RoundingMode.HALF_UP);
    }

    
    // Optimization algorithm doesn't converge when waypoints are equidistant
    // No iteration limit -> infinite loop
    // Fix: Add max iterations check
    public List<RouteWaypoint> optimizeRoute(List<RouteWaypoint> waypoints) {
        if (waypoints == null || waypoints.size() <= 2) {
            return waypoints;
        }

        List<RouteWaypoint> optimized = new ArrayList<>(waypoints);
        boolean improved = true;
        
        // but floating point comparison keeps finding "improvements"
        while (improved) {
            improved = false;
            for (int i = 1; i < optimized.size() - 1; i++) {
                for (int j = i + 1; j < optimized.size(); j++) {
                    double currentDist = calculateSegmentDistance(optimized, i, j);
                    // Swap and check
                    swap(optimized, i, j);
                    double newDist = calculateSegmentDistance(optimized, i, j);

                    
                    // Floating point noise means this may keep swapping
                    if (newDist < currentDist) {
                        improved = true; // Will loop again
                    } else {
                        swap(optimized, i, j); // Swap back
                    }
                }
            }
        }
        // Fix: Add int maxIterations = 1000; int iteration = 0;
        //      while (improved && iteration++ < maxIterations) { ... }
        return optimized;
    }

    
    // subList returns a view backed by the original list
    // Fix: new ArrayList<>(list.subList(...))
    public List<RouteWaypoint> getFirstNWaypoints(List<RouteWaypoint> waypoints, int n) {
        if (waypoints.size() <= n) return waypoints;
        
        return waypoints.subList(0, n);
        // Fix: return new ArrayList<>(waypoints.subList(0, n));
    }

    public double calculateDistance(double lat1, double lng1, double lat2, double lng2) {
        // Haversine formula
        double R = 6371.0; // Earth radius in km
        double dLat = Math.toRadians(lat2 - lat1);
        double dLng = Math.toRadians(lng2 - lng1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                   Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2)) *
                   Math.sin(dLng / 2) * Math.sin(dLng / 2);
        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }

    private double calculateSegmentDistance(List<RouteWaypoint> waypoints, int i, int j) {
        double dist = 0;
        for (int k = i; k <= j && k < waypoints.size() - 1; k++) {
            dist += calculateDistance(
                waypoints.get(k).getLat(), waypoints.get(k).getLng(),
                waypoints.get(k + 1).getLat(), waypoints.get(k + 1).getLng()
            );
        }
        return dist;
    }

    private void swap(List<RouteWaypoint> list, int i, int j) {
        RouteWaypoint temp = list.get(i);
        list.set(i, list.get(j));
        list.set(j, temp);
    }
}
