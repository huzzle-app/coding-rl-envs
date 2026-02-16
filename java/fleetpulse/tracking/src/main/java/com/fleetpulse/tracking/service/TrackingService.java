package com.fleetpulse.tracking.service;

import com.fleetpulse.tracking.model.TrackingData;
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

/**
 * Service for vehicle position tracking, speed calculation, and history management.
 *
 * Bugs: A7, C4, F4, F5, F6, F7
 * Categories: Concurrency, Precision/Arithmetic, Streams
 */
@Service
public class TrackingService {

    private static final Logger log = LoggerFactory.getLogger(TrackingService.class);

    private final Map<String, List<TrackingData>> vehicleTrackHistory = new ConcurrentHashMap<>();
    private final Map<String, TrackingData> latestPositions = new ConcurrentHashMap<>();

    // Bug A7: Nested parallel streams both use the common ForkJoinPool,
    // causing thread starvation.
    // Category: Concurrency
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
    }

    // Bug C4: Unfair ReentrantReadWriteLock under high contention causes
    // thread starvation for some threads.
    // Category: Concurrency
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

    // Bug F4: Multiplying large integer values causes overflow.
    // Category: Precision/Arithmetic
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
    }

    // Bug F5: Duration calculation can return negative values when end is before start.
    // Category: Precision/Arithmetic
    public long calculateTripDurationMinutes(Instant start, Instant end) {
        Duration duration = Duration.between(start, end);
        return duration.toMinutes();
    }

    // Bug F6: Division by zero when timestamps are identical produces Infinity or NaN.
    // Category: Precision/Arithmetic
    public double calculateSpeed(TrackingData point1, TrackingData point2) {
        double distance = haversineMeters(
            point1.getLat(), point1.getLng(), point2.getLat(), point2.getLng());

        long timeDiffSeconds = Duration.between(point1.getTimestamp(), point2.getTimestamp()).getSeconds();

        return distance / timeDiffSeconds;
    }

    // Bug F7: Collectors.toMap() throws IllegalStateException on duplicate keys.
    // Category: Streams
    public Map<String, TrackingData> getLatestPositionsByVehicle(List<TrackingData> dataPoints) {
        return dataPoints.stream()
            .collect(Collectors.toMap(
                TrackingData::getVehicleId,
                d -> d
            ));
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

    public List<TrackingData> getHistory(String vehicleId) {
        return vehicleTrackHistory.getOrDefault(vehicleId, List.of());
    }

    public int getTrackedVehicleCount() {
        return latestPositions.size();
    }
}
