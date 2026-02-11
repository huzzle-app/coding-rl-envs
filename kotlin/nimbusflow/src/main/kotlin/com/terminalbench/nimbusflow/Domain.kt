package com.terminalbench.nimbusflow

data class DispatchOrder(val id: String, val urgency: Int, val slaMinutes: Int) {
    fun urgencyScore(): Int = (urgency * 10) - maxOf(0, 120 - slaMinutes)
}

data class Route(val channel: String, val latency: Int)
data class ReplayEvent(val id: String, val sequence: Int)

object Severity {
    const val CRITICAL = 5
    const val HIGH = 4
    const val MEDIUM = 3
    const val LOW = 2
    const val INFO = 1

    fun slaByLevel(severity: Int): Int = when (severity) {
        5 -> 15
        4 -> 30
        3 -> 60
        2 -> 120
        1 -> 240
        else -> 60
    }

    fun classify(description: String): Int {
        val lower = description.lowercase()
        
        return when {
            "critical" in lower -> CRITICAL
            "high" in lower -> HIGH
            "medium" in lower || "moderate" in lower -> MEDIUM
            "low" in lower || "minor" in lower -> LOW
            else -> INFO
        }
    }
}

data class VesselManifest(
    val vesselId: String,
    val name: String,
    val cargoTons: Double,
    val containers: Int,
    val hazmat: Boolean
) {
    val isHeavy: Boolean get() = cargoTons > 50_000.0

    val containerWeightRatio: Double
        get() = if (containers == 0) 0.0 else cargoTons / containers
}

object OrderFactory {
    fun createBatch(ids: List<String>, severity: Int, sla: Int): List<DispatchOrder> {
        val clamped = severity.coerceIn(Severity.INFO, Severity.CRITICAL)
        val safeSla = maxOf(1, sla)
        return ids.map { DispatchOrder(it, clamped, safeSla) }
    }

    fun validateOrder(order: DispatchOrder): String? {
        if (order.id.isEmpty()) return "order id is empty"
        if (order.urgency < Severity.INFO || order.urgency > Severity.CRITICAL)
            return "urgency ${order.urgency} out of range [1,5]"
        if (order.slaMinutes <= 0) return "sla_minutes must be positive"
        return null
    }
}
