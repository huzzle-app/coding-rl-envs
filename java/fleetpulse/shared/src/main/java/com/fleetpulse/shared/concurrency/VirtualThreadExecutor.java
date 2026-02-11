package com.fleetpulse.shared.concurrency;

import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Executor service leveraging Java 21 virtual threads for FleetPulse services.
 *
 * Used by tracking, dispatch, and analytics services for high-throughput
 * concurrent task execution (GPS processing, route optimization, etc.).
 */
public class VirtualThreadExecutor {

    
    // inside virtual thread pins the carrier thread, reducing throughput.
    // When a virtual thread executes a synchronized block, it cannot be
    // unmounted from its carrier thread. If the synchronized block contains
    // blocking I/O (e.g., database calls, HTTP requests), the carrier thread
    // is pinned for the entire duration, defeating the purpose of virtual threads
    // and limiting concurrency to the number of carrier threads.
    // Category: Concurrency
    // Fix: Replace synchronized with ReentrantLock for virtual thread compatibility.
    //      private final ReentrantLock lock = new ReentrantLock();
    //      lock.lock(); try { ... } finally { lock.unlock(); }
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
        
        // Virtual threads should use ReentrantLock instead of synchronized blocks
        // because the JVM can unmount a virtual thread that blocks on a ReentrantLock,
        // but cannot unmount one that blocks inside a synchronized block.
        // Fix: Replace with:
        //   private final java.util.concurrent.locks.ReentrantLock lock = new ReentrantLock();
        //   lock.lock();
        //   try {
        //       taskCount.incrementAndGet();
        //       T result = task.call();
        //       taskResults.put(taskId, result);
        //       return result;
        //   } finally {
        //       lock.unlock();
        //   }
        synchronized (monitor) {
            taskCount.incrementAndGet();
            T result = task.call();
            taskResults.put(taskId, result);
            return result;
        }
    }

    
    // Reading atomicLong.get() and then calling atomicLong.set() is NOT atomic
    // as a compound operation. Two threads can read the same value simultaneously,
    // then both increment to the same next value, causing duplicate sequence numbers.
    // This affects dispatch ticket numbering and event ordering across services.
    // Category: Concurrency
    // Fix: Use getAndIncrement() which is a single atomic operation, or use
    //      compareAndSet in a loop, or use updateAndGet with a lambda.
    private final AtomicLong sequenceNumber = new AtomicLong(0);

    /**
     * Returns the next unique sequence number.
     * Used for ordering events and generating dispatch ticket IDs.
     */
    public long getNextSequence() {
        
        // the same 'current' value, then both set current + 1, resulting in
        // duplicate sequence numbers.
        long current = sequenceNumber.get();
        sequenceNumber.set(current + 1);
        return current;
        // Fix: return sequenceNumber.getAndIncrement();
    }

    
    // Latch is initialized with tasks.length - 1 instead of tasks.length,
    // causing await() to return before the last task has completed.
    // This results in race conditions where callers act on incomplete results
    // (e.g., route optimization returns before all segment calculations finish).
    // Category: Concurrency
    // Fix: Initialize latch with tasks.length (not tasks.length - 1)
    //      CountDownLatch latch = new CountDownLatch(tasks.length);

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

        
        // The latch will reach 0 after (N-1) tasks complete, causing await() to
        // return while the Nth task is still running.
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

        // This may return prematurely because the latch reaches 0 before all
        // tasks finish, causing callers to process incomplete results
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
