package com.fleetpulse.dispatch.service;

import com.fleetpulse.dispatch.model.DispatchJob;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.config.ConfigurableBeanFactory;
import org.springframework.context.annotation.Scope;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.*;
import java.util.function.Consumer;

/**
 * Service managing dispatch job assignments, notifications, and optimization.
 *
 * Bugs: A3, A4, A6, D3, D4
 * Categories: Concurrency, Spring/DI
 */
@Service
public class DispatchService {

    private static final Logger log = LoggerFactory.getLogger(DispatchService.class);

    private final List<Consumer<DispatchJob>> jobListeners = new ArrayList<>();
    private final Map<String, DispatchJob> activeJobs = new ConcurrentHashMap<>();

    // Bug A3: Async operation fails silently without error handling on CompletableFuture.
    // Category: Concurrency
    public void assignJob(DispatchJob job, String vehicleId, String driverId) {
        job.setVehicleId(Long.valueOf(vehicleId));
        job.setDriverId(Long.valueOf(driverId));
        job.setStatus("ASSIGNED");

        CompletableFuture.supplyAsync(() -> {
            notifyJobAssigned(job);
            return null;
        });

        activeJobs.put(job.getTitle(), job);
    }

    // Bug A4: ArrayList iterated while another thread modifies it,
    // causing ConcurrentModificationException.
    // Category: Concurrency
    public void notifyJobAssigned(DispatchJob job) {
        for (Consumer<DispatchJob> listener : jobListeners) {
            try {
                listener.accept(job);
            } catch (Exception e) {
                log.error("Listener error", e);
            }
        }
    }

    public void addJobListener(Consumer<DispatchJob> listener) {
        jobListeners.add(listener);
    }

    // Bug A6: Nested parallel streams both use the common ForkJoinPool,
    // causing thread starvation deadlock.
    // Category: Concurrency
    public List<String> optimizeAssignments(List<DispatchJob> jobs, List<String> vehicles) {
        return jobs.parallelStream()
            .map(job -> {
                return vehicles.parallelStream()
                    .filter(v -> isVehicleSuitable(v, job))
                    .findFirst()
                    .orElse("NONE");
            })
            .toList();
    }

    private boolean isVehicleSuitable(String vehicleId, DispatchJob job) {
        // Simulate suitability check
        return !vehicleId.isEmpty() && job.getStatus() != null;
    }

    // Bug D3: Prototype-scoped bean injected into singleton controller is
    // effectively singleton.
    // Category: Spring/DI
    public NotificationDispatcher getNotificationDispatcher() {
        return new NotificationDispatcher();
    }

    // Bug D4: Lock acquired but processing takes longer than TTL, allowing
    // another service to acquire the lock and cause data corruption.
    // Category: Concurrency
    public boolean processJobWithLock(String jobId, Runnable processor) {
        com.fleetpulse.shared.util.DistributedLock lock = new com.fleetpulse.shared.util.DistributedLock();
        boolean acquired = lock.tryLock(jobId,
            java.time.Duration.ofSeconds(5),
            java.time.Duration.ofSeconds(10));

        if (acquired) {
            try {
                // Processing might take longer than 10s TTL
                processor.run();
            } finally {
                lock.unlock(jobId);
            }
            return true;
        }
        return false;
    }

    public Map<String, DispatchJob> getActiveJobs() {
        return Map.copyOf(activeJobs);
    }

    @Service
    @Scope(ConfigurableBeanFactory.SCOPE_PROTOTYPE)
    public static class NotificationDispatcher {

        private final String instanceId = java.util.UUID.randomUUID().toString().substring(0, 8);

        public String getInstanceId() { return instanceId; }

        public void dispatch(String message) {
            // Simulate notification dispatch
        }
    }
}
