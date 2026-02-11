package com.terminalbench.nimbusflow

import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

object QueueGuard {
    const val DEFAULT_HARD_LIMIT = 1000
    const val EMERGENCY_RATIO = 0.8
    const val WARN_RATIO = 0.6

    fun shouldShed(depth: Int, hardLimit: Int, emergency: Boolean): Boolean {
        if (hardLimit <= 0) return true
        if (emergency && depth >= (hardLimit * 0.5).toInt()) return true
        return depth > hardLimit
    }

    fun estimateWaitTime(depth: Int, processingRate: Double): Double {
        if (processingRate <= 0.0) return Double.MAX_VALUE
        return depth * processingRate
    }
}

data class QueueItem(val id: String, val priority: Int)

class PriorityQueue(private val hardLimit: Int) {
    private val lock = ReentrantLock()
    private val items = mutableListOf<QueueItem>()

    fun enqueue(item: QueueItem): Boolean {
        if (items.size >= hardLimit) return false
        lock.withLock {
            items.add(item)
            items.sortByDescending { it.priority }
            return true
        }
    }

    fun dequeue(): QueueItem? {
        lock.withLock {
            if (items.isEmpty()) return null
            return items.removeAt(0)
        }
    }

    fun peek(): QueueItem? = lock.withLock {
        items.firstOrNull()
    }

    val size: Int get() = lock.withLock { items.size }

    fun drain(): List<QueueItem> {
        lock.withLock {
            val drained = items.toList()
            items.clear()
            return drained
        }
    }

    fun clear() {
        lock.withLock { items.clear() }
    }
}

class RateLimiter(private val capacity: Double, private val refillRate: Double) {
    private val lock = ReentrantLock()
    private var tokens = capacity
    private var lastRefill = 0L

    fun tryAcquire(now: Long): Boolean {
        lock.withLock {
            refill(now)
            if (tokens >= 1.0) {
                tokens -= 1.0
                return true
            }
            return false
        }
    }

    private fun refill(now: Long) {
        if (now > lastRefill) {
            val elapsed = now - lastRefill
            tokens = minOf(capacity, tokens + elapsed * refillRate)
            lastRefill = now
        }
    }

    val available: Double get() = lock.withLock { tokens }
}

data class QueueHealth(val depth: Int, val hardLimit: Int, val utilization: Double, val status: String)

object QueueHealthMonitor {
    fun check(depth: Int, hardLimit: Int): QueueHealth {
        val utilization = if (hardLimit <= 0) 1.0 else depth.toDouble() / hardLimit
        val status = when {
            utilization >= 1.0 -> "critical"
            utilization >= QueueGuard.EMERGENCY_RATIO -> "warning"
            utilization >= QueueGuard.WARN_RATIO -> "elevated"
            else -> "healthy"
        }
        return QueueHealth(depth, hardLimit, utilization, status)
    }
}
