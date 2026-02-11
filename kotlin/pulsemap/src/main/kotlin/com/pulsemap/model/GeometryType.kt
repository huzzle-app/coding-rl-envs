package com.pulsemap.model

import kotlinx.serialization.Serializable

@Serializable
sealed class GeometryType {
    @Serializable
    data class Point(val x: Double, val y: Double) : GeometryType()
    @Serializable
    data class LineString(val points: List<Point>) : GeometryType()
    @Serializable
    data class Polygon(val rings: List<List<Point>>) : GeometryType()
    @Serializable
    data class MultiPolygon(val polygons: List<Polygon>) : GeometryType()
}

fun GeometryType.area(): Double = when (this) {
    is GeometryType.Point -> 0.0
    is GeometryType.LineString -> 0.0
    is GeometryType.Polygon -> calculatePolygonArea(this.rings)
    
    else -> throw IllegalStateException("Unexpected geometry type: ${this::class.simpleName}")
}

private fun calculatePolygonArea(rings: List<List<GeometryType.Point>>): Double {
    if (rings.isEmpty()) return 0.0
    val ring = rings[0]
    var area = 0.0
    for (i in ring.indices) {
        val j = (i + 1) % ring.size
        area += ring[i].x * ring[j].y
        area -= ring[j].x * ring[i].y
    }
    return kotlin.math.abs(area) / 2.0
}
