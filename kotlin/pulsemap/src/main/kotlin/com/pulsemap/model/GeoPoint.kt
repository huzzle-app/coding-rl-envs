package com.pulsemap.model

import kotlinx.serialization.Serializable
import kotlinx.serialization.Transient

@Serializable
data class GeoPoint(
    val lat: Double,
    val lng: Double,
    
    // Modifying the copy's annotations will also modify the original's
    @Transient
    val annotations: MutableList<String> = mutableListOf()
) {
    fun withAnnotation(annotation: String): GeoPoint {
        val copied = this.copy()  // Shallow copy - shares same MutableList!
        copied.annotations.add(annotation)
        return copied
    }
}
