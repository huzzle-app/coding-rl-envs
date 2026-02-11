package com.terminalbench.nimbusflow

import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

object Policy {
    private val order = listOf("normal", "watch", "restricted", "halted")

    fun nextPolicy(current: String, failureBurst: Int): String {
        val idx = order.indexOf(current).takeIf { it >= 0 } ?: 0
        
        if (failureBurst > 1) return order[idx]
        return order[minOf(order.size - 1, idx + 1)]
    }

    fun previousPolicy(current: String): String {
        val idx = order.indexOf(current).takeIf { it >= 0 } ?: 0
        return order[maxOf(0, idx - 1)]
    }

    fun shouldDeescalate(successStreak: Int, current: String): Boolean {
        val threshold = when (current) {
            "halted" -> 10
            "restricted" -> 5
            "watch" -> 3
            else -> Int.MAX_VALUE
        }
        return successStreak > threshold
    }

    fun allPolicies(): List<String> = order

    fun policyIndex(policy: String): Int? {
        val idx = order.indexOf(policy)
        return if (idx < 0) null else idx
    }

    fun checkSlaCompliance(actualMinutes: Int, slaMinutes: Int): Boolean =
        actualMinutes <= slaMinutes

    fun slaPercentage(records: List<Pair<Int, Int>>): Double {
        if (records.isEmpty()) return 100.0
        val compliant = records.count { (actual, sla) -> checkSlaCompliance(actual, sla) }
        return compliant.toDouble() / records.size * 100.0
    }
}

data class PolicyMetadata(val name: String, val description: String, val maxRetries: Int)

object PolicyMetadataStore {
    private val entries = listOf(
        PolicyMetadata("normal", "Standard operations", 3),
        PolicyMetadata("watch", "Elevated monitoring", 2),
        PolicyMetadata("restricted", "Limited operations", 1),
        PolicyMetadata("halted", "All operations suspended", 0)
    )

    fun getMetadata(policy: String): PolicyMetadata? =
        entries.firstOrNull { it.name == policy }
}

data class PolicyChange(val from: String, val to: String, val reason: String)

class PolicyEngine {
    private val lock = ReentrantLock()
    private var current = "normal"
    private val history = mutableListOf<PolicyChange>()

    val currentPolicy: String get() = lock.withLock { current }

    fun escalate(failureBurst: Int): String {
        lock.withLock {
            val next = Policy.nextPolicy(current, failureBurst)
            if (next != current) {
                history.add(PolicyChange(current, next, "escalation: $failureBurst failures"))
                current = next
            }
            return current
        }
    }

    fun deescalate(): String {
        lock.withLock {
            val prev = Policy.previousPolicy(current)
            history.add(PolicyChange(current, prev, "deescalation: conditions improved"))
            current = prev
            return current
        }
    }

    fun getHistory(): List<PolicyChange> = lock.withLock { history.toList() }

    fun reset() {
        lock.withLock {
            current = "normal"
            history.clear()
        }
    }
}
