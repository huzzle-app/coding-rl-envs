package com.vertexgrid.tracking.service;

import com.vertexgrid.tracking.model.TrackingData;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.ReentrantLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.stream.Collectors;

@Service
public class TrackingService {

    private static final Logger log = LoggerFactory.getLogger(TrackingService.class);

    private final Map<String, List<TrackingData>> vehicleTrackHistory = new ConcurrentHashMap<>();
    private final Map<String, TrackingData> latestPositions = new ConcurrentHashMap<>();

    
    // Both use common ForkJoinPool -> thread starvation
    // Fix: Use sequential inner stream or custom ForkJoinPool
    public Map<String, Double> calculateAllVehicleSpeeds(List<String> vehicleIds) {
        
        return vehicleIds.parallelStream()
            .collect(Collectors.toMap(
                id -> id,
                id -> {
                    List<TrackingData> history = vehicleTrackHistory.getOrDefault(id, List.of());
                    
                    return history.parallelStream()
                        .mapToDouble(TrackingData::getSpeed)
                        .average()
                        .orElse(0.0);
                }
            ));
        // Fix: Use history.stream() (sequential) for inner stream
    }

    
    // Under high contention, some threads may never acquire the lock
    // Fix: Use fair lock: new ReentrantReadWriteLock(true)
    private final ReentrantReadWriteLock rwLock = new ReentrantReadWriteLock(false); 

    public void recordPosition(TrackingData data) {
        rwLock.writeLock().lock();
        try {
            latestPositions.put(data.getVehicleId(), data);
            vehicleTrackHistory.computeIfAbsent(data.getVehicleId(), k -> new CopyOnWriteArrayList<>())
                .add(data);
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    public TrackingData getLatestPosition(String vehicleId) {
        rwLock.readLock().lock();
        try {
            return latestPositions.get(vehicleId);
        } finally {
            rwLock.readLock().unlock();
        }
    }

    
    // Multiplying large integer values causes overflow
    // Fix: Use long or check for overflow
    public int calculateTotalDistanceMeters(List<TrackingData> points) {
        int totalDistance = 0; 

        for (int i = 0; i < points.size() - 1; i++) {
            TrackingData p1 = points.get(i);
            TrackingData p2 = points.get(i + 1);

            // Distance in meters - can be very large for long routes
            int segmentDistance = (int) (haversineMeters(
                p1.getLat(), p1.getLng(), p2.getLat(), p2.getLng()));

            
            totalDistance += segmentDistance;
        }
        return totalDistance;
        // Fix: Use long totalDistance = 0L;
    }

    
    // Duration calculation between timestamps doesn't account for timezone
    // Fix: Use Instant (UTC) consistently, or handle timezone conversion
    public long calculateTripDurationMinutes(Instant start, Instant end) {
        
        // this is fine. But if they're LocalDateTime converted incorrectly, it breaks.
        // The real bug is when mixing LocalDateTime and Instant without timezone context
        Duration duration = Duration.between(start, end);
        
        return duration.toMinutes(); // Can return negative value
        // Fix: return Math.max(0, duration.toMinutes());
    }

    
    // When time difference is zero, division by zero produces Infinity or NaN
    // Fix: Check for zero time difference
    //
    
    // When getLatestPositionsByVehicle() is called with multiple data points for
    // the same vehicle, it throws IllegalStateException before calculateSpeed()
    // can be invoked with identical timestamps. Fixing B3 to merge duplicates
    // (keeping latest) will reveal this G3 bug when consecutive points have
    // the same timestamp, causing Infinity/NaN to propagate through analytics.
    public double calculateSpeed(TrackingData point1, TrackingData point2) {
        double distance = haversineMeters(
            point1.getLat(), point1.getLng(), point2.getLat(), point2.getLng());

        long timeDiffSeconds = Duration.between(point1.getTimestamp(), point2.getTimestamp()).getSeconds();

        
        return distance / timeDiffSeconds; // Returns Infinity or NaN
        // Fix: if (timeDiffSeconds == 0) return 0.0;
    }

    
    // Collectors.toMap() throws IllegalStateException on duplicate keys
    // Fix: Add merge function
    public Map<String, TrackingData> getLatestPositionsByVehicle(List<TrackingData> dataPoints) {
        
        return dataPoints.stream()
            .collect(Collectors.toMap(
                TrackingData::getVehicleId,
                d -> d
                
            ));
        // Fix: .collect(Collectors.toMap(TrackingData::getVehicleId, d -> d, (d1, d2) -> d2))
    }

    private double haversineMeters(double lat1, double lng1, double lat2, double lng2) {
        double R = 6371000;
        double dLat = Math.toRadians(lat2 - lat1);
        double dLng = Math.toRadians(lng2 - lng1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                   Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2)) *
                   Math.sin(dLng / 2) * Math.sin(dLng / 2);
        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }

    /**
     * Computes the average speed across a sequence of tracking points.
     * Uses total distance divided by total time for an accurate weighted average.
     */
    public double computeAverageSpeed(List<TrackingData> points) {
        if (points == null || points.size() < 2) return 0.0;
        double speedSum = 0.0;
        int segments = 0;
        for (int i = 0; i < points.size() - 1; i++) {
            double dist = haversineMeters(
                points.get(i).getLat(), points.get(i).getLng(),
                points.get(i + 1).getLat(), points.get(i + 1).getLng());
            long timeDiff = Duration.between(
                points.get(i).getTimestamp(), points.get(i + 1).getTimestamp()).getSeconds();
            if (timeDiff > 0) {
                speedSum += dist / timeDiff;
                segments++;
            }
        }
        return segments > 0 ? speedSum / segments : 0.0;
    }

    public List<TrackingData> getHistory(String vehicleId) {
        return vehicleTrackHistory.getOrDefault(vehicleId, List.of());
    }

    public int getTrackedVehicleCount() {
        return latestPositions.size();
    }
}
