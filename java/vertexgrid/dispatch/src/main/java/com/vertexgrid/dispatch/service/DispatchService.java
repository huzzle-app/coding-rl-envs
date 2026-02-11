package com.vertexgrid.dispatch.service;

import com.vertexgrid.dispatch.model.DispatchJob;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.config.ConfigurableBeanFactory;
import org.springframework.context.annotation.Scope;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.*;
import java.util.function.Consumer;

@Service
public class DispatchService {

    private static final Logger log = LoggerFactory.getLogger(DispatchService.class);

    private final List<Consumer<DispatchJob>> jobListeners = new ArrayList<>();
    private final Map<String, DispatchJob> activeJobs = new ConcurrentHashMap<>();

    
    // Async operation fails silently without error handling
    // Fix: Add .exceptionally() or .whenComplete() handler
    public void assignJob(DispatchJob job, String vehicleId, String driverId) {
        job.setVehicleId(Long.valueOf(vehicleId));
        job.setDriverId(Long.valueOf(driverId));
        job.setStatus("ASSIGNED");

        
        CompletableFuture.supplyAsync(() -> {
            notifyJobAssigned(job);
            return null;
        });
        // Fix: Add .exceptionally(ex -> { log.error("Failed to notify", ex); return null; })

        activeJobs.put(job.getTitle(), job);
    }

    
    // ArrayList iterated while another thread modifies it
    // Fix: Use CopyOnWriteArrayList
    //
    
    // When assignJob() calls notifyJobAssigned() via CompletableFuture.supplyAsync(),
    // the ConcurrentModificationException thrown here is silently swallowed because
    // A3 lacks exception handling. Fixing A3 by adding .exceptionally() will reveal
    // this A4 bug: the exception will now be logged/propagated, and tests that
    // concurrently add listeners while jobs are assigned will start failing.
    // To fully fix job assignment, both bugs must be addressed together:
    // 1. Fix A3: Add .exceptionally(ex -> { log.error("...", ex); return null; })
    // 2. Fix A4: Change jobListeners to CopyOnWriteArrayList
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

    
    // Both use the common ForkJoinPool -> thread starvation deadlock
    // Fix: Use sequential inner stream or custom ForkJoinPool
    public List<String> optimizeAssignments(List<DispatchJob> jobs, List<String> vehicles) {
        
        return jobs.parallelStream()
            .map(job -> {
                
                return vehicles.parallelStream()
                    .filter(v -> isVehicleSuitable(v, job))
                    .findFirst()
                    .orElse("NONE");
            })
            .toList();
        // Fix: Use .stream() (sequential) for the inner stream
    }

    private boolean isVehicleSuitable(String vehicleId, DispatchJob job) {
        // Simulate suitability check
        return !vehicleId.isEmpty() && job.getStatus() != null;
    }

    
    // If DispatchService were prototype-scoped but injected into singleton controller,
    // it would be effectively singleton
    // (This bug is about the NotificationDispatcher inner service)
    public NotificationDispatcher getNotificationDispatcher() {
        return new NotificationDispatcher();
    }

    
    // Lock acquired but processing takes longer than TTL -> lock expires
    // Another service acquires the lock -> data corruption
    // Fix: Implement lock renewal/heartbeat mechanism
    public boolean processJobWithLock(String jobId, Runnable processor) {
        com.vertexgrid.shared.util.DistributedLock lock = new com.vertexgrid.shared.util.DistributedLock();
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
        // Fix: Implement lock renewal thread that extends TTL during processing
    }

    /**
     * Transitions a dispatch job to a new state with retry support.
     * On each retry, re-validates against the current job state in case another
     * thread has moved the job to a state from which the target transition is valid.
     *
     * @param job the job to transition
     * @param newStatus the desired target state
     * @param maxRetries maximum number of retry attempts
     * @return true if the transition succeeded, false if exhausted retries
     */
    public boolean transitionWithRetry(DispatchJob job, String newStatus, int maxRetries) {
        String current = job.getStatus();
        for (int attempt = 0; attempt <= maxRetries; attempt++) {
            if (isValidTransition(current, newStatus)) {
                job.setStatus(newStatus);
                activeJobs.put(job.getTitle(), job);
                return true;
            }
            try { Thread.sleep(50); } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        return false;
    }

    private boolean isValidTransition(String from, String to) {
        return switch (from) {
            case "PENDING" -> Set.of("ASSIGNED", "CANCELLED").contains(to);
            case "ASSIGNED" -> Set.of("IN_PROGRESS", "CANCELLED").contains(to);
            case "IN_PROGRESS" -> Set.of("COMPLETED", "CANCELLED").contains(to);
            case "COMPLETED", "CANCELLED" -> false;
            default -> false;
        };
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
