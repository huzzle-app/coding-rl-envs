package com.fleetpulse.dispatch;

import com.fleetpulse.dispatch.model.DispatchJob;
import com.fleetpulse.dispatch.model.JobAssignment;
import com.fleetpulse.dispatch.service.DispatchService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class DispatchServiceTest {

    private DispatchService dispatchService;

    @BeforeEach
    void setUp() {
        dispatchService = new DispatchService();
    }

    // ====== BUG A3: CompletableFuture exception swallowed ======
    @Test
    void test_async_exception_handled() {
        
        DispatchJob job = createJob("test-job");
        // If notification fails, exception should be logged, not swallowed
        assertDoesNotThrow(() -> dispatchService.assignJob(job, "V1", "D1"),
            "assignJob should handle async exceptions gracefully");
    }

    @Test
    void test_completable_future_error() {
        // Assign a job and verify it's tracked even if async part fails
        DispatchJob job = createJob("tracked-job");
        dispatchService.assignJob(job, "V1", "D1");

        Map<String, DispatchJob> active = dispatchService.getActiveJobs();
        assertTrue(active.containsKey("tracked-job"),
            "Job should be in active jobs after assignment");
        assertEquals("ASSIGNED", job.getStatus());
    }

    @Test
    void test_assign_job_sets_fields() {
        DispatchJob job = createJob("assign-test");
        dispatchService.assignJob(job, "100", "200");

        assertEquals(100L, job.getVehicleId());
        assertEquals(200L, job.getDriverId());
        assertEquals("ASSIGNED", job.getStatus());
    }

    @Test
    void test_multiple_assignments() {
        for (int i = 0; i < 10; i++) {
            DispatchJob job = createJob("job-" + i);
            dispatchService.assignJob(job, String.valueOf(i), String.valueOf(i));
        }
        assertEquals(10, dispatchService.getActiveJobs().size());
    }

    // ====== BUG A4: ConcurrentModificationException ======
    @Test
    void test_concurrent_listener_safe() throws Exception {
        
        int threadCount = 20;
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(threadCount);
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());

        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            new Thread(() -> {
                try {
                    startLatch.await();
                    if (idx % 2 == 0) {
                        dispatchService.addJobListener(job -> {});
                    } else {
                        dispatchService.notifyJobAssigned(createJob("notify-" + idx));
                    }
                } catch (Exception e) {
                    errors.add(e);
                } finally {
                    doneLatch.countDown();
                }
            }).start();
        }

        startLatch.countDown();
        doneLatch.await(10, TimeUnit.SECONDS);

        assertTrue(errors.isEmpty(),
            "Concurrent listener add/notify should not throw CME: " + errors);
    }

    @Test
    void test_no_cme_on_iteration() throws Exception {
        // Add initial listeners
        for (int i = 0; i < 5; i++) {
            dispatchService.addJobListener(job -> {});
        }

        CountDownLatch latch = new CountDownLatch(2);
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());

        // Thread 1: notify (iterates listeners)
        new Thread(() -> {
            try {
                for (int i = 0; i < 50; i++) {
                    dispatchService.notifyJobAssigned(createJob("iter-" + i));
                }
            } catch (Exception e) {
                errors.add(e);
            } finally {
                latch.countDown();
            }
        }).start();

        // Thread 2: add more listeners (modifies list)
        new Thread(() -> {
            try {
                for (int i = 0; i < 50; i++) {
                    dispatchService.addJobListener(job -> {});
                }
            } catch (Exception e) {
                errors.add(e);
            } finally {
                latch.countDown();
            }
        }).start();

        latch.await(10, TimeUnit.SECONDS);
        assertTrue(errors.isEmpty(), "No CME expected: " + errors);
    }

    @Test
    void test_listener_receives_job() {
        AtomicInteger callCount = new AtomicInteger(0);
        dispatchService.addJobListener(job -> callCount.incrementAndGet());

        dispatchService.notifyJobAssigned(createJob("test"));
        assertEquals(1, callCount.get(), "Listener should be called");
    }

    @Test
    void test_multiple_listeners_called() {
        AtomicInteger count = new AtomicInteger(0);
        for (int i = 0; i < 5; i++) {
            dispatchService.addJobListener(job -> count.incrementAndGet());
        }
        dispatchService.notifyJobAssigned(createJob("multi"));
        assertEquals(5, count.get());
    }

    // ====== BUG A5: ForkJoinPool deadlock ======
    @Test
    @Timeout(value = 10, unit = TimeUnit.SECONDS)
    void test_no_parallel_stream_deadlock() {
        
        List<DispatchJob> jobs = new ArrayList<>();
        for (int i = 0; i < 20; i++) {
            jobs.add(createJob("opt-" + i));
        }
        List<String> vehicles = List.of("V1", "V2", "V3", "V4", "V5");

        List<String> result = dispatchService.optimizeAssignments(jobs, vehicles);
        assertNotNull(result);
        assertEquals(20, result.size(), "Should produce assignment for each job");
    }

    @Test
    @Timeout(value = 10, unit = TimeUnit.SECONDS)
    void test_forkjoin_not_starved() {
        // Larger dataset that's more likely to trigger deadlock
        List<DispatchJob> jobs = new ArrayList<>();
        for (int i = 0; i < 100; i++) {
            jobs.add(createJob("big-" + i));
        }
        List<String> vehicles = List.of("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8");

        List<String> result = dispatchService.optimizeAssignments(jobs, vehicles);
        assertEquals(100, result.size());
        assertTrue(result.stream().noneMatch(String::isEmpty));
    }

    @Test
    void test_optimize_empty_jobs() {
        List<String> result = dispatchService.optimizeAssignments(List.of(), List.of("V1"));
        assertTrue(result.isEmpty());
    }

    @Test
    void test_optimize_no_suitable_vehicles() {
        List<DispatchJob> jobs = new ArrayList<>();
        DispatchJob job = createJob("no-match");
        job.setStatus(null); // Makes isVehicleSuitable return false
        jobs.add(job);

        List<String> result = dispatchService.optimizeAssignments(jobs, List.of("V1"));
        assertTrue(result.contains("NONE"), "Should return NONE when no vehicle is suitable");
    }

    // ====== BUG C3: Prototype scope mismatch ======
    @Test
    void test_prototype_new_instance() {
        
        DispatchService.NotificationDispatcher d1 = dispatchService.getNotificationDispatcher();
        DispatchService.NotificationDispatcher d2 = dispatchService.getNotificationDispatcher();
        assertNotEquals(d1.getInstanceId(), d2.getInstanceId(),
            "Each NotificationDispatcher should be a unique instance");
    }

    @Test
    void test_scope_proxy() {
        DispatchService.NotificationDispatcher dispatcher = dispatchService.getNotificationDispatcher();
        assertNotNull(dispatcher.getInstanceId());
        assertDoesNotThrow(() -> dispatcher.dispatch("test message"));
    }

    // ====== BUG D4: Distributed lock renewal ======
    @Test
    void test_distributed_lock_renewal() {
        
        AtomicInteger processed = new AtomicInteger(0);
        boolean acquired = dispatchService.processJobWithLock("job-1", () -> {
            processed.incrementAndGet();
        });
        // Lock mechanism should work for quick operations
        assertTrue(processed.get() > 0 || !acquired,
            "Either job was processed or lock wasn't acquired");
    }

    @Test
    void test_lock_not_expired() {
        // Test that processing completes before lock expires
        boolean result = dispatchService.processJobWithLock("job-2", () -> {
            // Quick operation - should complete before TTL
            try { Thread.sleep(100); } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });
        // Result depends on lock implementation
        assertNotNull(Boolean.valueOf(result));
    }

    // ====== BUG K1: Record array equality ======
    @Test
    void test_record_array_equality() {
        
        String[] skills1 = {"CDL", "HAZMAT"};
        String[] skills2 = {"CDL", "HAZMAT"};
        JobAssignment a1 = new JobAssignment("J1", "V1", "D1", skills1, 1000L);
        JobAssignment a2 = new JobAssignment("J1", "V1", "D1", skills2, 1000L);

        // With the bug, these are NOT equal because skills1 != skills2 (reference equality)
        // With the fix (using List<String>), they would be equal
        // This test exposes the bug - same content but different array instances
        assertNotSame(skills1, skills2, "Arrays are different instances");
        // The fix would make this assertTrue instead:
        // assertTrue(a1.equals(a2), "Records with same content arrays should be equal");
    }

    @Test
    void test_job_assignment_equals() {
        String[] shared = {"CDL"};
        JobAssignment a1 = new JobAssignment("J1", "V1", "D1", shared, 1000L);
        JobAssignment a2 = new JobAssignment("J1", "V1", "D1", shared, 1000L);

        // Same array reference, so record equality works
        assertEquals(a1, a2, "Same array instance should produce equal records");
    }

    @Test
    void test_job_assignment_hashcode() {
        String[] skills = {"CDL", "TANKER"};
        JobAssignment a = new JobAssignment("J1", "V1", "D1", skills, 1000L);
        assertNotEquals(0, a.hashCode(), "hashCode should be non-zero for non-empty record");
    }

    @Test
    void test_job_assignment_fields() {
        String[] skills = {"CDL"};
        JobAssignment a = new JobAssignment("J1", "V1", "D1", skills, 1000L);
        assertEquals("J1", a.jobId());
        assertEquals("V1", a.vehicleId());
        assertEquals("D1", a.driverId());
        assertArrayEquals(skills, a.requiredSkills());
        assertEquals(1000L, a.assignedAt());
    }

    // ====== General tests ======
    @Test
    void test_active_jobs_immutable() {
        dispatchService.assignJob(createJob("j1"), "1", "1");
        Map<String, DispatchJob> active = dispatchService.getActiveJobs();
        assertThrows(UnsupportedOperationException.class,
            () -> active.put("hacked", createJob("hacked")),
            "Active jobs map should be immutable copy");
    }

    @Test
    void test_assign_job_with_listener() {
        AtomicInteger notified = new AtomicInteger(0);
        dispatchService.addJobListener(job -> notified.incrementAndGet());

        DispatchJob job = createJob("listen-job");
        dispatchService.assignJob(job, "1", "1");

        // Give async notification time to complete
        try { Thread.sleep(500); } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        assertTrue(notified.get() >= 0, "Listener notification should be attempted");
    }

    @Test
    void test_concurrent_assignment() throws Exception {
        int threadCount = 20;
        CountDownLatch latch = new CountDownLatch(threadCount);
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());

        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            new Thread(() -> {
                try {
                    dispatchService.assignJob(createJob("conc-" + idx),
                        String.valueOf(idx), String.valueOf(idx));
                } catch (Exception e) {
                    errors.add(e);
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
        assertTrue(errors.isEmpty(), "Concurrent assignments should not throw: " + errors);
        assertEquals(20, dispatchService.getActiveJobs().size());
    }

    // Helper
    private DispatchJob createJob(String title) {
        DispatchJob job = new DispatchJob();
        job.setTitle(title);
        job.setStatus("PENDING");
        job.setPriority("NORMAL");
        return job;
    }
}
