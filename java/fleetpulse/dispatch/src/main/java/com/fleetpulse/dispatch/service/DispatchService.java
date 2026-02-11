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

@Service
public class DispatchService {

    private static final Logger log = LoggerFactory.getLogger(DispatchService.class);

    private final List<Consumer<DispatchJob>> jobListeners = new ArrayList<>();
    private final Map<String, DispatchJob> activeJobs = new ConcurrentHashMap<>();

    
    // Async operation fails silently without error handling
    // Fix: Add .exceptionally() or .whenComplete() handler
    //
    
    // When notifyJobAssigned throws NPE (due to null job fields), the exception is swallowed.
    // Fixing BUG A3 (adding .exceptionally() handler) will reveal the hidden NPE:
    //   1. With exception handler, NPE is logged but still occurs
    //   2. Root cause: job.getTitle() can be null, causing NPE in listener processing
    //   3. Additionally, fixing BUG A4 (ConcurrentModificationException) first will
    //      change timing such that this NPE becomes more frequent
    //
    
    //   - BUG A4 in notifyJobAssigned (use CopyOnWriteArrayList)
    //   - Null check for job.getTitle() in activeJobs.put() below
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
        // Fix: Implement lock renewal thread that extends TTL during processing
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
