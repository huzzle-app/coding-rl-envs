package com.pulsemap.service

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

class SpatialAggregationService {
    
    // The upstream still runs on the wrong dispatcher
    suspend fun computeHeatmap(sensorIds: List<String>): List<Double> {
        val results = mutableListOf<Double>()

        flow {
            for (id in sensorIds) {
                emit(fetchSensorValue(id))
                delay(10) // Simulate processing
            }
        }
        .collect { value ->
            results.add(value)
        }
        
        // .flowOn(Dispatchers.Default)  // This line is commented out; should be before collect

        return results
    }

    private suspend fun fetchSensorValue(sensorId: String): Double {
        delay(5) // Simulate IO
        return Math.random() * 100
    }

    // Correct version would be:
    // flow { ... }.flowOn(Dispatchers.IO).collect { ... }
}
