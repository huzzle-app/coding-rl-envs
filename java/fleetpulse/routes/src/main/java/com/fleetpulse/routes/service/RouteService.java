package com.fleetpulse.routes.service;

import com.fleetpulse.routes.model.RouteWaypoint;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

/**
 * Service for route cost calculation, optimization, and waypoint management.
 *
 * Bugs: G1, G2, G3, G4, B4
 * Categories: Precision/Arithmetic, Algorithm, Memory/Data Structures
 */
@Service
public class RouteService {

    private static final Logger log = LoggerFactory.getLogger(RouteService.class);

    // Bug G1: Using double for financial calculations causes precision errors.
    // Category: Precision/Arithmetic
    public double calculateRouteCost(double distanceKm, double ratePerKm) {
        double cost = distanceKm * ratePerKm;
        return cost;
    }

    // Bug G2: BigDecimal.equals() checks scale, so "1.0".equals("1.00") returns false.
    // Category: Precision/Arithmetic
    public boolean isRouteCostEqual(BigDecimal cost1, BigDecimal cost2) {
        return cost1.equals(cost2);
    }

    // Bug G3: Division without explicit rounding mode throws ArithmeticException
    // when result has non-terminating decimal representation.
    // Category: Precision/Arithmetic
    public BigDecimal calculateCostPerMile(BigDecimal totalCost, BigDecimal totalMiles) {
        return totalCost.divide(totalMiles);
    }

    // Bug G4: Optimization algorithm has no iteration limit, causing potential
    // infinite loop when floating point comparison keeps finding "improvements".
    // Category: Algorithm
    public List<RouteWaypoint> optimizeRoute(List<RouteWaypoint> waypoints) {
        if (waypoints == null || waypoints.size() <= 2) {
            return waypoints;
        }

        List<RouteWaypoint> optimized = new ArrayList<>(waypoints);
        boolean improved = true;
        while (improved) {
            improved = false;
            for (int i = 1; i < optimized.size() - 1; i++) {
                for (int j = i + 1; j < optimized.size(); j++) {
                    double currentDist = calculateSegmentDistance(optimized, i, j);
                    // Swap and check
                    swap(optimized, i, j);
                    double newDist = calculateSegmentDistance(optimized, i, j);

                    if (newDist < currentDist) {
                        improved = true;
                    } else {
                        swap(optimized, i, j); // Swap back
                    }
                }
            }
        }
        return optimized;
    }

    // Bug B4: subList returns a view backed by the original list.
    // Category: Memory/Data Structures
    public List<RouteWaypoint> getFirstNWaypoints(List<RouteWaypoint> waypoints, int n) {
        if (waypoints.size() <= n) return waypoints;
        return waypoints.subList(0, n);
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
