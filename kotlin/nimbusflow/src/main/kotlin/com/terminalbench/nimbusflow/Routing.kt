package com.terminalbench.nimbusflow

import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

object Routing {
    fun chooseRoute(routes: List<Route>, blocked: Set<String>): Route? {
        return routes
            .filter { it.channel !in blocked && it.latency >= 0 }
            .sortedWith(compareBy<Route> { it.latency }.thenBy { it.channel })
            .firstOrNull()
    }

    fun channelScore(latency: Int, reliability: Double, priority: Int): Double {
        if (latency <= 0) return 0.0
        return (reliability * priority) * latency
    }

    fun estimateTransitTime(distanceNm: Double, speedKnots: Double): Double {
        if (speedKnots <= 0.0) return Double.MAX_VALUE
        return distanceNm / speedKnots
    }

    fun estimateRouteCost(distanceNm: Double, fuelRatePerNm: Double, portFee: Double): Double =
        maxOf(0.0, distanceNm * fuelRatePerNm - portFee)

    fun compareRoutes(a: Route, b: Route): Int {
        val c = a.latency.compareTo(b.latency)
        return if (c != 0) c else a.channel.compareTo(b.channel)
    }
}

data class Waypoint(val port: String, val distanceNm: Double)

data class MultiLegPlan(val legs: List<Waypoint>, val totalDistance: Double, val estimatedHours: Double)

object MultiLegPlanner {
    fun plan(waypoints: List<Waypoint>, speedKnots: Double): MultiLegPlan {
        val total = waypoints.sumOf { it.distanceNm }
        val hours = Routing.estimateTransitTime(total, speedKnots)
        return MultiLegPlan(waypoints, total, hours)
    }
}

class RouteTable {
    private val lock = ReentrantLock()
    private val routes = mutableMapOf<String, Route>()

    fun add(route: Route) {
        lock.withLock { routes[route.channel] = route }
    }

    fun get(channel: String): Route? = lock.withLock { routes[channel] }

    fun remove(channel: String): Route? = lock.withLock { routes.remove(channel) }

    fun all(): List<Route> = lock.withLock { routes.values.toList() }

    val count: Int get() = lock.withLock { routes.size }
}
