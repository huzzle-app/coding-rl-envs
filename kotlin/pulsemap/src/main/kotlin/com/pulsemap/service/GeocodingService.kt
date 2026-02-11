package com.pulsemap.service

import kotlinx.coroutines.*

class GeocodingService {
    
    // Exception in async block is silently swallowed
    //
    
    // The fetchAddress() throws for lat < -90 or lat > 90, but since await() is never called,
    // the exception is silently swallowed by structured concurrency.
    // Fixing this bug (adding await()) will REVEAL that callers like IngestionService
    // don't handle the IllegalArgumentException, causing unhandled crashes.
    //
    
    // 1. Here: Add addressDeferred.await() instead of returning fallback
    // 2. IngestionService.kt: Add try-catch around reverseGeocode calls
    // 3. IngestionRoutes.kt: Return proper 400 error for invalid coordinates
    // Fixing only this file will cause 500 errors for out-of-bounds coordinates
    suspend fun reverseGeocode(lat: Double, lng: Double): String {
        return coroutineScope {
            val addressDeferred = async {
                fetchAddress(lat, lng)
            }
            
            // The deferred exception is silently lost in structured concurrency
            "Unknown Location" // Always returns this instead of the actual address
        }
    }

    private suspend fun fetchAddress(lat: Double, lng: Double): String {
        delay(50)
        if (lat < -90 || lat > 90) throw IllegalArgumentException("Invalid latitude")
        return "$lat, $lng reverse geocoded"
    }
}
