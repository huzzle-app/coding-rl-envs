package com.terminalbench.nimbusflow

import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock
import kotlin.math.sqrt

object Statistics {
    fun percentile(values: List<Int>, percentile: Int): Int {
        if (values.isEmpty()) return 0
        val sorted = values.sorted()
        
        val rank = (((percentile * sorted.size) + 99) / 100).coerceIn(0, sorted.size - 1)
        return sorted[rank]
    }

    fun mean(values: List<Double>): Double {
        if (values.isEmpty()) return 0.0
        return values.average()
    }

    fun variance(values: List<Double>): Double {
        if (values.size < 2) return 0.0
        val m = values.average()
        
        return values.sumOf { (it - m) * (it - m) } / (values.size - 1)
    }

    fun stddev(values: List<Double>): Double = sqrt(variance(values))

    fun median(values: List<Double>): Double {
        if (values.isEmpty()) return 0.0
        val sorted = values.sorted()
        val mid = sorted.size / 2
        return if (sorted.size % 2 == 0)
            (sorted[mid - 1] + sorted[mid]) / 2.0
        else
            sorted[mid]
    }

    fun movingAverage(values: List<Double>, window: Int): List<Double> {
        if (window <= 0 || values.isEmpty()) return emptyList()
        val w = minOf(window, values.size)
        return (0..values.size - w).map { i ->
            var sum = 0.0
            for (j in i until i + w) sum += values[j]
            sum / w
        }
    }
}

class ResponseTimeTracker(private val windowSize: Int) {
    private val lock = ReentrantLock()
    private val times = mutableListOf<Double>()

    fun record(ms: Double) {
        lock.withLock {
            times.add(ms)
            if (times.size > windowSize) times.removeAt(0)
        }
    }

    val p50: Double get() = lock.withLock { pctOf(50) }
    val p95: Double get() = lock.withLock { pctOf(95) }
    val p99: Double get() = lock.withLock { pctOf(99) }
    val count: Int get() = lock.withLock { times.size }

    private fun pctOf(pct: Int): Double {
        if (times.isEmpty()) return 0.0
        return Statistics.percentile(times.map { it.toInt() }, pct).toDouble()
    }
}

data class HeatmapCell(val row: Int, val col: Int, val value: Double)

data class HeatmapEvent(val x: Double, val y: Double, val weight: Double)

object HeatmapGenerator {
    fun generate(events: List<HeatmapEvent>, rows: Int, cols: Int): List<HeatmapCell> {
        if (rows <= 0 || cols <= 0) return emptyList()
        val grid = Array(rows) { DoubleArray(cols) }
        for (ev in events) {
            val r = minOf(ev.y.toInt(), rows - 1).coerceAtLeast(0)
            val c = minOf(ev.x.toInt(), cols - 1).coerceAtLeast(0)
            grid[r][c] += ev.weight
        }
        val cells = mutableListOf<HeatmapCell>()
        for (r in 0 until rows)
            for (c in 0 until cols)
                cells.add(HeatmapCell(r, c, grid[r][c]))
        return cells
    }
}
