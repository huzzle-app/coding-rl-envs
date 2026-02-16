package com.fleetpulse.routes.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * Service for geofence boundary checking.
 *
 * Bugs: G5, G6
 * Categories: Boundary/Logic
 */
@Service
public class GeofenceService {

    private static final Logger log = LoggerFactory.getLogger(GeofenceService.class);

    // Bug G5: Uses strict less-than instead of less-than-or-equal for boundary check.
    // Points exactly on the boundary are incorrectly classified as outside.
    // Category: Boundary/Logic
    public boolean isPointInCircle(double pointLat, double pointLng,
                                    double centerLat, double centerLng,
                                    double radiusMeters) {
        double distance = haversineDistance(pointLat, pointLng, centerLat, centerLng);
        return distance < radiusMeters;
    }

    // Bug G6: Uses strict greater-than instead of greater-than-or-equal in
    // polygon boundary ray-casting algorithm.
    // Category: Boundary/Logic
    public boolean isPointInPolygon(double lat, double lng, double[][] polygon) {
        int n = polygon.length;
        boolean inside = false;

        for (int i = 0, j = n - 1; i < n; j = i++) {
            if ((polygon[i][1] > lng) != (polygon[j][1] > lng) &&
                (lat < (polygon[j][0] - polygon[i][0]) * (lng - polygon[i][1]) /
                       (polygon[j][1] - polygon[i][1]) + polygon[i][0])) {
                inside = !inside;
            }
        }
        return inside;
    }

    private double haversineDistance(double lat1, double lng1, double lat2, double lng2) {
        double R = 6371000; // meters
        double dLat = Math.toRadians(lat2 - lat1);
        double dLng = Math.toRadians(lng2 - lng1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                   Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2)) *
                   Math.sin(dLng / 2) * Math.sin(dLng / 2);
        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }
}
