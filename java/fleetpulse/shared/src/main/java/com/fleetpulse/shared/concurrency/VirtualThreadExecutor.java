package com.fleetpulse.shared.concurrency;

import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Executor service leveraging Java 21 virtual threads for FleetPulse services.
 *
 * Used by tracking, dispatch, and analytics services for high-throughput
 * concurrent task execution (GPS processing, route optimization, etc.).
 *
 * Bugs: A1, A2, C1
 * Categories: Concurrency
 */
public class VirtualThreadExecutor {

    // Bug A1: Using synchronized blocks with virtual threads pins the carrier thread,
    // reducing throughput when the synchronized block contains blocking I/O.
    // Category: Concurrency
    private final Object monitor = new Object();
    private final AtomicLong taskCount = new AtomicLong(0);
    private final ConcurrentHashMap<String, Object> taskResults = new ConcurrentHashMap<>();

    /**
     * Executes a task under mutual exclusion and stores its result.
     *
     * @param taskId unique identifier for the task
     * @param task   the callable to execute
     * @return the result of the task
     */
    public <T> T executeWithLock(String taskId, Callable<T> task) throws Exception {
        synchronized (monitor) {
            taskCount.incrementAndGet();
            T result = task.call();
            taskResults.put(taskId, result);
            return result;
        }
    }

    // Bug A2: Non-atomic compound operation on AtomicLong (get + set).
    // Two threads can read the same value simultaneously, causing duplicate
    // sequence numbers. This affects dispatch ticket numbering and event ordering.
    // Category: Concurrency
    private final AtomicLong sequenceNumber = new AtomicLong(0);

    /**
     * Returns the next unique sequence number.
     * Used for ordering events and generating dispatch ticket IDs.
     */
    public long getNextSequence() {
        long current = sequenceNumber.get();
        sequenceNumber.set(current + 1);
        return current;
    }

    // Bug C1: CountDownLatch initialized with tasks.length - 1 instead of tasks.length,
    // causing await() to return before the last task has completed.
    // Category: Concurrency

    /**
     * Executes all tasks in parallel using virtual threads and waits
     * for completion.
     *
     * @param tasks array of tasks to execute concurrently
     */
    public void executeParallel(Runnable[] tasks) throws InterruptedException {
        if (tasks == null || tasks.length == 0) {
            return;
        }

        CountDownLatch latch = new CountDownLatch(tasks.length - 1);

        for (Runnable task : tasks) {
            Thread.startVirtualThread(() -> {
                try {
                    task.run();
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await(30, TimeUnit.SECONDS);
    }

    /**
     * Returns the total number of tasks executed through executeWithLock.
     */
    public long getTaskCount() {
        return taskCount.get();
    }

    /**
     * Retrieves the cached result for a previously executed task.
     *
     * @param taskId the task identifier
     * @return the task result, or null if not found
     */
    public Object getResult(String taskId) {
        return taskResults.get(taskId);
    }

    /**
     * Clears all cached task results.
     */
    public void clearResults() {
        taskResults.clear();
    }

    /**
     * Returns the current sequence number without incrementing.
     */
    public long getCurrentSequence() {
        return sequenceNumber.get();
    }
}
