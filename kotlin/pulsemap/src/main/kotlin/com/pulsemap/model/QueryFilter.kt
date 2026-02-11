package com.pulsemap.model

import kotlinx.serialization.Serializable

@Serializable
sealed interface QueryFilter {
    @Serializable
    data class BoundingBoxFilter(
        val minLat: Double, val minLng: Double,
        val maxLat: Double, val maxLng: Double
    ) : QueryFilter

    @Serializable
    data class PolygonFilter(val vertices: List<GeoPoint>) : QueryFilter

    
    // Deserializing a RadiusFilter will throw SerializationException
    @Serializable
    data class RadiusFilter(
        val center: GeoPoint,
        val radiusKm: Double
    ) : QueryFilter
}
