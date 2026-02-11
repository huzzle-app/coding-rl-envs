package com.terminalbench.nimbusflow

import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

object Workflow {
    
    private val graph = mapOf(
        "queued" to setOf("allocated", "cancelled"),
        "allocated" to setOf("departed"),
        "departed" to setOf("arrived", "allocated"),
        "arrived" to emptySet()
    )

    private val terminalStates = setOf("arrived")

    fun canTransition(from: String, to: String): Boolean = graph[from]?.contains(to) == true

    fun isTerminalState(state: String): Boolean = state in terminalStates

    fun isValidState(state: String): Boolean = state in graph || state == "cancelled"

    fun allowedTransitions(from: String): List<String> =
        graph[from]?.toList() ?: emptyList()

    fun shortestPath(from: String, to: String): List<String>? {
        if (from == to) return listOf(from)
        val visited = mutableSetOf(from)
        val queue = ArrayDeque<List<String>>()
        queue.add(listOf(from))
        while (queue.isNotEmpty()) {
            val path = queue.removeFirst()
            val current = path.last()
            for (next in allowedTransitions(current)) {
                if (next == to) return path + next
                if (visited.add(next)) {
                    queue.add(path + next)
                }
            }
        }
        return null
    }
}

data class TransitionRecord(val entityId: String, val from: String, val to: String, val timestamp: Long)

data class TransitionResult(val success: Boolean, val from: String, val to: String, val error: String?)

class WorkflowEngine {
    private val lock = ReentrantLock()
    private val entities = mutableMapOf<String, String>()
    private val history = mutableListOf<TransitionRecord>()

    fun register(entityId: String) {
        lock.withLock { entities[entityId] = "queued" }
    }

    fun getState(entityId: String): String? = lock.withLock { entities[entityId] }

    fun transition(entityId: String, to: String, timestamp: Long): TransitionResult {
        lock.withLock {
            val from = entities[entityId]
                ?: return TransitionResult(false, "", to, "entity not registered")
            if (!Workflow.canTransition(from, to))
                return TransitionResult(false, from, to, "cannot transition from $from to $to")
            entities[entityId] = to
            history.add(TransitionRecord(entityId, from, to, timestamp))
            return TransitionResult(true, from, to, null)
        }
    }

    fun isTerminal(entityId: String): Boolean {
        lock.withLock {
            val state = entities[entityId] ?: return false
            return Workflow.isTerminalState(state)
        }
    }

    val activeCount: Int
        get() = lock.withLock { entities.values.count { !Workflow.isTerminalState(it) } }

    fun getHistory(): List<TransitionRecord> = history.toList()

    val auditLog: List<String>
        get() = history.map { r -> "[${r.timestamp}] ${r.from} -> ${r.to} (entity: ${r.entityId})" }
}
