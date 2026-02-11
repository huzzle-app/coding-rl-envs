package com.fleetpulse.routes.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class GeofenceService {

    private static final Logger log = LoggerFactory.getLogger(GeofenceService.class);

    
    // Uses < instead of <= for boundary check -> points exactly on boundary
    // are incorrectly classified as outside
    // Fix: Use <= for boundary comparison
    public boolean isPointInCircle(double pointLat, double pointLng,
                                    double centerLat, double centerLng,
                                    double radiusMeters) {
        double distance = haversineDistance(pointLat, pointLng, centerLat, centerLng);
        
        return distance < radiusMeters;
        // Fix: return distance <= radiusMeters;
    }

    public boolean isPointInPolygon(double lat, double lng, double[][] polygon) {
        int n = polygon.length;
        boolean inside = false;

        for (int i = 0, j = n - 1; i < n; j = i++) {
            
            if ((polygon[i][1] > lng) != (polygon[j][1] > lng) &&
                (lat < (polygon[j][0] - polygon[i][0]) * (lng - polygon[i][1]) /
                       (polygon[j][1] - polygon[i][1]) + polygon[i][0])) {
                inside = !inside;
            }
            // Fix: Use >= instead of > for inclusive boundary check
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
