package com.pulsemap.service

import com.pulsemap.repository.TileRepository

class TileService {
    private val repository = TileRepository()
    private val cache = mutableMapOf<String, ByteArray>()

    
    // The GlobalScope.launch in TileRepository causes cache invalidation callbacks to run
    // asynchronously AFTER the transaction completes, giving false sense of working code.
    // Fixing TileRepository to use proper coroutine scope will REVEAL this race condition
    // because invalidation happens faster, increasing the window for the containsKey/get race.

    suspend fun getTile(zoom: Int, x: Int, y: Int): ByteArray? {
        val key = "$zoom/$x/$y"
        
        // Should return null or use getOrElse
        
        // Fixing TileRepository will cause cache.remove() to execute faster, exposing this race
        return if (cache.containsKey(key)) {
            cache[key]!! 
        } else {
            val data = repository.getTile(zoom, x, y)
            data?.also { cache[key] = it }
        }
    }

    fun invalidate(key: String) {
        cache.remove(key)
    }
}
