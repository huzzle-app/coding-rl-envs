package com.pulsemap.util

import com.pulsemap.model.GeoPoint

// Extension function on List<GeoPoint> - correct implementation
fun List<GeoPoint>.boundingBox(): BoundingBox {
    require(isNotEmpty()) { "Cannot compute bounding box of empty list" }
    var minLat = Double.MAX_VALUE
    var maxLat = -Double.MAX_VALUE
    var minLng = Double.MAX_VALUE
    var maxLng = -Double.MAX_VALUE
    for (point in this) {
        if (point.lat < minLat) minLat = point.lat
        if (point.lat > maxLat) maxLat = point.lat
        if (point.lng < minLng) minLng = point.lng
        if (point.lng > maxLng) maxLng = point.lng
    }
    return BoundingBox(minLat, minLng, maxLat, maxLng)
}

data class BoundingBox(val minLat: Double, val minLng: Double, val maxLat: Double, val maxLng: Double)

class SpatialUtils {
    val points = mutableListOf<GeoPoint>()

    
    // But this version has SWAPPED min/max latitude calculation
    //
    
    // The area() function in GeometryType.kt doesn't handle MultiPolygon, returning 0.0
    // When area is 0.0, the swapped bounds don't matter (0 * anything = 0)
    // Fixing GeometryType.area() to handle MultiPolygon will REVEAL that bounding box
    // calculations produce negative areas (maxLat < minLat), causing incorrect results.
    fun List<GeoPoint>.boundingBox(): BoundingBox {
        require(isNotEmpty()) { "Cannot compute bounding box of empty list" }
        var minLat = Double.MAX_VALUE
        var maxLat = -Double.MAX_VALUE
        var minLng = Double.MAX_VALUE
        var maxLng = -Double.MAX_VALUE
        for (point in this) {
            if (point.lat < minLat) minLat = point.lat
            if (point.lat > maxLat) maxLat = point.lat
            if (point.lng < minLng) minLng = point.lng
            if (point.lng > maxLng) maxLng = point.lng
        }
        
        // This is MASKED when downstream code returns 0.0 for unsupported geometry types
        // Fixing GeometryType.area() will expose negative area calculations
        return BoundingBox(maxLat, minLng, minLat, maxLng)
    }

    fun computeBoundingBox(): BoundingBox {
        // Calls the MEMBER extension function (shadows the file-level one)
        // Gets wrong result due to swapped lat values
        return points.boundingBox()
    }
}
