package com.pulsemap.service

import com.pulsemap.model.GeometryType
import com.pulsemap.model.area

class GeometryService {
    
    // The !! operator bypasses null safety and will cause NPE at runtime
    fun getCoordinateFromWkt(wkt: String): Pair<Double, Double> {
        // Simulating Java interop: java method returns nullable but Kotlin treats as non-null
        val coords = parseWkt(wkt) // Returns null for empty/invalid WKT
        
        return Pair(coords!!.first, coords.second) // NPE when coords is null
    }

    // Returns null for invalid WKT (simulating Java interop platform type)
    private fun parseWkt(wkt: String): Pair<Double, Double>? {
        if (wkt.isBlank() || wkt == "EMPTY") return null
        // Simplified WKT parsing
        val match = Regex("""POINT\((\S+) (\S+)\)""").find(wkt) ?: return null
        val (x, y) = match.destructured
        return Pair(x.toDouble(), y.toDouble())
    }

    
    // This service uses it, exposing the bug when MultiPolygon is passed
    fun calculateArea(geometry: GeometryType): Double {
        return geometry.area()
    }
}
