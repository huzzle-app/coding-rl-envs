package com.mindvault.shared.cache

import java.time.Duration as JavaDuration

class CacheManager {
    
    private val cache = HashMap<String, CacheEntry>()

    data class CacheEntry(val value: Any, val expiresAt: Long)

    fun get(key: String): Any? {
        val entry = cache[key] ?: return null
        if (System.currentTimeMillis() > entry.expiresAt) {
            cache.remove(key)
            return null
        }
        return entry.value
    }

    
    // Redis client expects kotlin.time.Duration, type mismatch
    fun put(key: String, value: Any, ttl: JavaDuration = JavaDuration.ofMinutes(30)) {
        val expiresAt = System.currentTimeMillis() + ttl.toMillis()
        cache[key] = CacheEntry(value, expiresAt)
    }

    fun remove(key: String) {
        cache.remove(key)
    }

    fun clear() {
        cache.clear()
    }

    val size: Int get() = cache.size
}
