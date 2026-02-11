package com.vertexgrid.shared.util;

import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Distributed lock implementation for VertexGrid services.
 *
 * Provides mutual exclusion for cross-service operations such as:
 *   - Dispatch ticket assignment (prevent double-assignment)
 *   - Vehicle status updates (prevent concurrent state mutations)
 *   - Route recalculation (prevent overlapping optimizations)
 *   - Billing settlement (prevent duplicate charges)
 *
 * In a production deployment this would be backed by Redis (Redisson)
 * or etcd. This in-memory implementation is used for single-instance
 * testing and defines the API contract.
 *
 * Note: This class itself is bug-free and serves as infrastructure
 * for bugs in other service modules (e.g., lock ordering deadlocks
 * in dispatch, check-then-act races in tracking).
 */
public class DistributedLock {

    private final ConcurrentHashMap<String, LockEntry> locks = new ConcurrentHashMap<>();

    /**
     * Attempts to acquire a lock with the given key.
     *
     * @param key     the lock key (e.g., "dispatch:ticket:123", "vehicle:456:status")
     * @param timeout maximum time to wait for the lock
     * @param ttl     time-to-live for the lock (auto-release safety net)
     * @return true if the lock was acquired, false if timeout elapsed
     */
    public boolean tryLock(String key, Duration timeout, Duration ttl) {
        LockEntry entry = locks.computeIfAbsent(key, k -> new LockEntry());

        try {
            boolean acquired = entry.lock.tryLock(timeout.toMillis(), TimeUnit.MILLISECONDS);
            if (acquired) {
                entry.expiresAt = System.currentTimeMillis() + ttl.toMillis();
                entry.ownerThread = Thread.currentThread().getName();
                entry.acquiredAt = System.currentTimeMillis();
            }
            return acquired;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }

    /**
     * Releases the lock if held by the current thread.
     *
     * @param key the lock key to release
     */
    public void unlock(String key) {
        LockEntry entry = locks.get(key);
        if (entry != null && entry.lock.isHeldByCurrentThread()) {
            entry.ownerThread = null;
            entry.lock.unlock();
        }
    }

    /**
     * Checks if the given key is currently locked.
     *
     * @param key the lock key to check
     * @return true if the lock is held by any thread
     */
    public boolean isLocked(String key) {
        LockEntry entry = locks.get(key);
        return entry != null && entry.lock.isLocked();
    }

    /**
     * Checks if the lock has expired based on its TTL.
     *
     * @param key the lock key to check
     * @return true if the lock exists and has exceeded its TTL
     */
    public boolean isExpired(String key) {
        LockEntry entry = locks.get(key);
        if (entry == null || !entry.lock.isLocked()) {
            return false;
        }
        return System.currentTimeMillis() > entry.expiresAt;
    }

    /**
     * Returns the thread name that currently owns the lock.
     *
     * @param key the lock key
     * @return the owner thread name, or null if not locked
     */
    public String getOwner(String key) {
        LockEntry entry = locks.get(key);
        return entry != null ? entry.ownerThread : null;
    }

    /**
     * Returns the number of currently tracked lock keys.
     */
    public int getLockCount() {
        return locks.size();
    }

    /**
     * Removes all lock entries. Used in testing.
     */
    public void clear() {
        locks.clear();
    }

    private static class LockEntry {
        final ReentrantLock lock = new ReentrantLock();
        volatile long expiresAt;
        volatile long acquiredAt;
        volatile String ownerThread;
    }
}
