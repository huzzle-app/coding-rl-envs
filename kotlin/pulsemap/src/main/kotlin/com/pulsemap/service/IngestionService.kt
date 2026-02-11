package com.pulsemap.service

import com.pulsemap.model.SensorReading
import com.pulsemap.repository.SensorRepository
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel

class IngestionService {
    private val repository = SensorRepository()
    
    private val ingestionChannel = Channel<SensorReading>(Channel.UNLIMITED)

    init {
        
        GlobalScope.launch {
            for (reading in ingestionChannel) {
                try {
                    processReading(reading)
                } catch (e: Exception) {
                    // Silently swallowed - no error propagation
                    println("Error processing reading: ${e.message}")
                }
            }
        }
    }

    suspend fun ingest(reading: SensorReading) {
        ingestionChannel.send(reading)
    }

    private suspend fun processReading(reading: SensorReading) {
        repository.insertSensor(
            id = reading.id,
            sensorId = reading.sensorId,
            name = null,
            lat = reading.latitude,
            lng = reading.longitude,
            value = reading.values.firstOrNull() ?: 0.0,
            ts = reading.timestamp
        )
    }
}
