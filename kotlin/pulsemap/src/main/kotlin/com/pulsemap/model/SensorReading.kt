package com.pulsemap.model

import kotlinx.serialization.Serializable


// Two SensorReadings with identical values array will NOT be equal
@Serializable
data class SensorReading(
    val id: String,
    val sensorId: String,
    val values: DoubleArray,  
    val latitude: Double,
    val longitude: Double,
    val timestamp: Long
)
