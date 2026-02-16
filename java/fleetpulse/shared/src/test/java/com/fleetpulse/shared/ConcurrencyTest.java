package com.fleetpulse.shared;

import com.fleetpulse.shared.concurrency.VirtualThreadExecutor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

@Tag("concurrency")
public class ConcurrencyTest {

    private VirtualThreadExecutor executor;

    @BeforeEach
    void setUp() {
        executor = new VirtualThreadExecutor();
    }

    
    @Test
    void test_virtual_thread_not_pinned() throws Exception {
        
        // Virtual threads should not be pinned during execution
        assertDoesNotThrow(() -> {
            executor.executeWithLock("task1", () -> {
                Thread.sleep(10); // Simulate blocking I/O
                return "result1";
            });
        });
    }

    @Test
    void test_reentrant_lock_used() throws Exception {
        // Multiple concurrent executions should not deadlock
        int threadCount = 10;
        CountDownLatch latch = new CountDownLatch(threadCount);
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());

        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            Thread.startVirtualThread(() -> {
                try {
                    executor.executeWithLock("task-" + idx, () -> {
                        Thread.sleep(5);
                        return "result-" + idx;
                    });
                } catch (Exception e) {
                    errors.add(e);
                } finally {
                    latch.countDown();
                }
            });
        }

        assertTrue(latch.await(30, TimeUnit.SECONDS), "All tasks should complete");
        assertTrue(errors.isEmpty(), "No errors expected: " + errors);
    }

    @Test
    void test_execute_with_lock_returns_result() throws Exception {
        String result = executor.executeWithLock("test", () -> "hello");
        assertEquals("hello", result);
    }

    @Test
    void test_task_count_incremented() throws Exception {
        executor.executeWithLock("t1", () -> 1);
        executor.executeWithLock("t2", () -> 2);
        assertEquals(2, executor.getTaskCount());
    }

    @Test
    void test_result_stored() throws Exception {
        executor.executeWithLock("key1", () -> "value1");
        assertEquals("value1", executor.getResult("key1"));
    }

    
    @Test
    void test_atomic_sequence() throws Exception {
        int threadCount = 100;
        CountDownLatch latch = new CountDownLatch(threadCount);
        Set<Long> sequences = ConcurrentHashMap.newKeySet();

        for (int i = 0; i < threadCount; i++) {
            new Thread(() -> {
                try {
                    long seq = executor.getNextSequence();
                    sequences.add(seq);
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);

        
        assertEquals(threadCount, sequences.size(),
            "All sequence numbers should be unique - no duplicates from race condition");
    }

    @Test
    void test_no_sequence_gap() {
        long s1 = executor.getNextSequence();
        long s2 = executor.getNextSequence();
        long s3 = executor.getNextSequence();

        // Sequences should be consecutive
        assertEquals(s1 + 1, s2);
        assertEquals(s2 + 1, s3);
    }

    @Test
    void test_sequence_starts_at_zero() {
        long first = executor.getNextSequence();
        assertEquals(0, first);
    }

    
    @Test
    void test_countdown_latch_correct() throws Exception {
        AtomicInteger completed = new AtomicInteger(0);
        Runnable[] tasks = new Runnable[5];
        for (int i = 0; i < 5; i++) {
            tasks[i] = () -> {
                completed.incrementAndGet();
            };
        }

        
        // All tasks should complete before executeParallel returns
        executor.executeParallel(tasks);

        assertEquals(5, completed.get(),
            "All tasks should have completed before executeParallel returns");
    }

    @Test
    void test_all_tasks_complete() throws Exception {
        int taskCount = 10;
        AtomicInteger counter = new AtomicInteger(0);
        Runnable[] tasks = new Runnable[taskCount];
        for (int i = 0; i < taskCount; i++) {
            tasks[i] = counter::incrementAndGet;
        }

        executor.executeParallel(tasks);

        
        assertEquals(taskCount, counter.get(),
            "All " + taskCount + " tasks should complete");
    }

    @Test
    void test_parallel_with_single_task() throws Exception {
        AtomicInteger counter = new AtomicInteger(0);
        Runnable[] tasks = { counter::incrementAndGet };

        
        // This means it returns immediately, potentially before the task runs
        executor.executeParallel(tasks);
        assertEquals(1, counter.get());
    }

    @Test
    void test_parallel_with_empty_tasks() throws Exception {
        Runnable[] tasks = {};
        // Empty array is handled by early return in executeParallel
        assertDoesNotThrow(() -> executor.executeParallel(tasks));
    }

    @Test
    void test_concurrent_lock_access() throws Exception {
        int threadCount = 20;
        CountDownLatch latch = new CountDownLatch(threadCount);
        AtomicInteger successCount = new AtomicInteger(0);

        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            new Thread(() -> {
                try {
                    executor.executeWithLock("shared-key", () -> {
                        successCount.incrementAndGet();
                        return null;
                    });
                } catch (Exception e) {
                    // error
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
        assertEquals(threadCount, successCount.get());
    }

    @Test
    void test_lock_exception_handling() {
        assertThrows(RuntimeException.class, () ->
            executor.executeWithLock("error-task", () -> {
                throw new RuntimeException("Task failed");
            })
        );
    }

    @Test
    void test_sequence_monotonic() {
        long prev = -1;
        for (int i = 0; i < 50; i++) {
            long seq = executor.getNextSequence();
            assertTrue(seq > prev, "Sequence should be monotonically increasing");
            prev = seq;
        }
    }

    @Test
    void test_parallel_tasks_all_execute() throws Exception {
        List<String> results = Collections.synchronizedList(new ArrayList<>());
        Runnable[] tasks = new Runnable[3];
        for (int i = 0; i < 3; i++) {
            final int idx = i;
            tasks[i] = () -> results.add("task-" + idx);
        }

        executor.executeParallel(tasks);

        assertEquals(3, results.size());
    }

    @Test
    void test_execute_with_lock_concurrent_results() throws Exception {
        int count = 10;
        CountDownLatch latch = new CountDownLatch(count);

        for (int i = 0; i < count; i++) {
            final int idx = i;
            new Thread(() -> {
                try {
                    executor.executeWithLock("task-" + idx, () -> "result-" + idx);
                } catch (Exception e) {
                    // ignore
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);

        for (int i = 0; i < count; i++) {
            assertEquals("result-" + i, executor.getResult("task-" + i));
        }
    }

    @Test
    void test_parallel_with_null_tasks() {
        // Null array is handled by early return in executeParallel
        assertDoesNotThrow(() -> executor.executeParallel(null));
    }

    @Test
    void test_clear_results() throws Exception {
        executor.executeWithLock("key1", () -> "val1");
        assertNotNull(executor.getResult("key1"));

        executor.clearResults();
        assertNull(executor.getResult("key1"));
    }
}
