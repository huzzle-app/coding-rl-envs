package com.terminalbench.nimbusflow

import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

object Resilience {
    fun replay(events: List<ReplayEvent>): List<ReplayEvent> {
        val latest = mutableMapOf<String, ReplayEvent>()
        for (event in events) {
            val prev = latest[event.id]
            
            if (prev == null || event.sequence < prev.sequence) {
                latest[event.id] = event
            }
        }
        return latest.values.sortedWith(compareBy<ReplayEvent> { it.sequence }.thenBy { it.id })
    }

    fun deduplicate(events: List<ReplayEvent>): List<ReplayEvent> {
        val seen = mutableSetOf<String>()
        return events.filter { seen.add(it.id) }
    }

    fun replayConverges(a: List<ReplayEvent>, b: List<ReplayEvent>): Boolean =
        replay(a) == replay(b)
}

object CircuitBreakerState {
    const val CLOSED = "closed"
    const val OPEN = "open"
    const val HALF_OPEN = "half_open"
}

class CircuitBreaker(private val failureThreshold: Int, private val successThreshold: Int) {
    private val lock = ReentrantLock()
    private var state = CircuitBreakerState.CLOSED
    private var failureCount = 0
    private var successCount = 0

    val currentState: String get() = lock.withLock { state }

    fun recordSuccess() {
        lock.withLock {
            successCount++
            failureCount = 0
            if (state == CircuitBreakerState.HALF_OPEN && successCount >= successThreshold) {
                state = CircuitBreakerState.CLOSED
                successCount = 0
            }
        }
    }

    fun recordFailure() {
        lock.withLock {
            failureCount++
            successCount = 0
            if (state == CircuitBreakerState.CLOSED && failureCount >= failureThreshold) {
                state = CircuitBreakerState.OPEN
                failureCount = 0
            } else if (state == CircuitBreakerState.HALF_OPEN) {
                state = CircuitBreakerState.OPEN
            }
        }
    }

    fun attemptReset() {
        lock.withLock {
            if (state == CircuitBreakerState.OPEN) {
                state = CircuitBreakerState.HALF_OPEN
                failureCount = 0
                successCount = 0
            }
        }
    }

    val isCallPermitted: Boolean get() = lock.withLock { state != CircuitBreakerState.OPEN }
}

data class Checkpoint(val id: String, val sequence: Long, val timestamp: Long)

class CheckpointManager(private val interval: Long) {
    private val lock = ReentrantLock()
    private val checkpoints = mutableMapOf<String, Checkpoint>()

    fun record(cp: Checkpoint) {
        lock.withLock { checkpoints[cp.id] = cp }
    }

    fun get(id: String): Checkpoint? = lock.withLock { checkpoints[id] }

    
    fun shouldCheckpoint(currentSeq: Long, lastSeq: Long): Boolean =
        currentSeq - lastSeq > interval

    fun reset() {
        lock.withLock { checkpoints.clear() }
    }

    val count: Int get() = lock.withLock { checkpoints.size }
}
