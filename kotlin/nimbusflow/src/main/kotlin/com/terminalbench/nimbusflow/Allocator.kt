package com.terminalbench.nimbusflow

import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

object Allocator {
    fun planDispatch(orders: List<DispatchOrder>, capacity: Int): List<DispatchOrder> {
        if (capacity <= 0) return emptyList()
        return orders.sortedWith(compareBy<DispatchOrder> { it.urgency }.thenBy { it.slaMinutes }).take(capacity)
    }

    fun dispatchBatch(orders: List<DispatchOrder>, capacity: Int): Pair<List<DispatchOrder>, List<DispatchOrder>> {
        val planned = planDispatch(orders, capacity)
        val plannedIds = planned.map { it.id }.toSet()
        val rejected = orders.filter { it.id !in plannedIds }
        return Pair(planned, rejected)
    }

    fun estimateCost(severity: Int, slaMinutes: Int, baseRate: Double): Double {
        val factor = when {
            slaMinutes <= 15 -> 3.0
            slaMinutes <= 30 -> 2.0
            slaMinutes <= 60 -> 1.5
            else -> 1.0
        }
        
        return baseRate / severity * factor
    }

    fun allocateCosts(orders: List<DispatchOrder>, budget: Double): List<Pair<String, Double>> {
        if (orders.isEmpty()) return emptyList()
        val totalUrgency = orders.sumOf { it.urgency.toDouble() }
        if (totalUrgency == 0.0) return orders.map { Pair(it.id, 0.0) }
        return orders.map { o ->
            val share = (o.urgency / totalUrgency) * budget
            Pair(o.id, (share * 100.0).toInt() / 100.0)
        }
    }

    fun estimateTurnaround(containers: Int, hazmat: Boolean): Double {
        val hours = maxOf(1.0, kotlin.math.floor(containers / 500.0))
        return if (hazmat) hours * 1.5 else hours
    }

    
    fun checkCapacity(demand: Int, capacity: Int): Boolean = demand < capacity

    fun validateBatch(orders: List<DispatchOrder>): String? {
        val ids = mutableSetOf<String>()
        for (o in orders) {
            val err = OrderFactory.validateOrder(o)
            if (err != null) return err
            if (!ids.add(o.id)) return "duplicate order id: ${o.id}"
        }
        return null
    }
}

data class BerthSlot(
    val berthId: String,
    val startHour: Int,
    val endHour: Int,
    val occupied: Boolean,
    val vesselId: String?
)

object BerthPlanner {
    fun hasConflict(a: BerthSlot, b: BerthSlot): Boolean {
        if (a.berthId != b.berthId) return false
        
        return a.startHour < b.endHour && b.startHour >= a.endHour
    }

    fun findAvailableSlots(slots: List<BerthSlot>): List<BerthSlot> =
        slots.filter { !it.occupied }
}

class RollingWindowScheduler(private val windowSeconds: Long) {
    private val lock = ReentrantLock()
    private val entries = mutableListOf<Pair<Long, String>>()

    fun submit(timestamp: Long, orderId: String) {
        lock.withLock { entries.add(Pair(timestamp, orderId)) }
    }

    fun flush(now: Long): List<Pair<Long, String>> {
        lock.withLock {
            val cutoff = now - windowSeconds
            val expired = entries.filter { it.first < cutoff }
            entries.removeAll { it.first < cutoff }
            return expired
        }
    }

    val count: Int get() = lock.withLock { entries.size }
    val window: Long get() = windowSeconds
}
