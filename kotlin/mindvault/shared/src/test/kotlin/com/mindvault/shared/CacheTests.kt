package com.mindvault.shared

import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull

/**
 * Tests for CacheManager: TTL, eviction, bounded size.
 *
 * Bug-specific tests:
 *   H4 - Unbounded HashMap as cache: grows without limit, eventual OOM
 *   H5 - Uses java.time.Duration instead of kotlin.time.Duration for TTL
 */
class CacheTests {

    // =========================================================================
    // H4: Unbounded cache (no eviction, no max size)
    // =========================================================================

    @Test
    fun test_cache_bounded_size() {
        
        // Under load, cache grows unbounded until OOM
        val cache = LocalCacheManager()
        val maxSize = cache.getMaxCapacity()
        assertTrue(
            maxSize in 1..100_000,
            "Cache should have a bounded max capacity, but reported $maxSize (unbounded)"
        )
    }

    @Test
    fun test_no_unbounded_growth() {
        
        val cache = LocalCacheManager()
        // Insert way more entries than should be kept
        for (i in 1..5000) {
            cache.put("key_$i", "value_$i")
        }
        assertTrue(
            cache.size <= 1000,
            "Cache should evict old entries to stay bounded; current size: ${cache.size} (expected <= 1000)"
        )
    }

    // =========================================================================
    // H5: java.time.Duration vs kotlin.time.Duration
    // =========================================================================

    @Test
    fun test_kotlin_duration_used() {
        
        // but the Redis client expects kotlin.time.Duration, causing type mismatch
        val cache = LocalCacheManager()
        assertFalse(
            cache.usesJavaDuration(),
            "CacheManager should use kotlin.time.Duration, not java.time.Duration"
        )
    }

    @Test
    fun test_ttl_applied_correctly() {
        
        val cache = LocalCacheManager()
        cache.put("ttl_key", "ttl_value", ttlMillis = 100)

        // Value should exist initially
        assertNotNull(cache.get("ttl_key"), "Value should exist immediately after put")

        // Simulate time passing
        cache.advanceTime(200)

        // Value should be expired
        assertNull(
            cache.get("ttl_key"),
            "Value should expire after TTL; TTL type mismatch may prevent expiration"
        )
    }

    // =========================================================================
    // Baseline: Cache put/get/remove/clear
    // =========================================================================

    @Test
    fun test_put_and_get() {
        val cache = LocalCacheManager()
        cache.put("key1", "value1")
        assertEquals("value1", cache.get("key1"), "Should retrieve the cached value")
    }

    @Test
    fun test_get_missing_key() {
        val cache = LocalCacheManager()
        assertNull(cache.get("nonexistent"), "Missing key should return null")
    }

    @Test
    fun test_remove_key() {
        val cache = LocalCacheManager()
        cache.put("key1", "value1")
        cache.remove("key1")
        assertNull(cache.get("key1"), "Removed key should return null")
    }

    @Test
    fun test_clear_all() {
        val cache = LocalCacheManager()
        cache.put("a", "1")
        cache.put("b", "2")
        cache.clear()
        assertEquals(0, cache.size, "Cache should be empty after clear()")
    }

    @Test
    fun test_overwrite_value() {
        val cache = LocalCacheManager()
        cache.put("key", "old")
        cache.put("key", "new")
        assertEquals("new", cache.get("key"), "Put should overwrite existing value")
    }

    @Test
    fun test_size_tracks_entries() {
        val cache = LocalCacheManager()
        cache.put("a", "1")
        cache.put("b", "2")
        cache.put("c", "3")
        assertEquals(3, cache.size, "Size should reflect number of entries")
    }

    @Test
    fun test_remove_nonexistent_key() {
        val cache = LocalCacheManager()
        cache.remove("doesnt_exist") // Should not throw
    }

    @Test
    fun test_cache_stores_different_types() {
        val cache = LocalCacheManager()
        cache.put("int_key", 42)
        cache.put("list_key", listOf(1, 2, 3))
        assertEquals(42, cache.get("int_key"))
        assertEquals(listOf(1, 2, 3), cache.get("list_key"))
    }

    @Test
    fun test_expired_entry_returns_null() {
        val cache = LocalCacheManager()
        cache.put("temp", "data", ttlMillis = 50)
        cache.advanceTime(100)
        assertNull(cache.get("temp"), "Expired entries should return null")
    }

    @Test
    fun test_non_expired_entry_returns_value() {
        val cache = LocalCacheManager()
        cache.put("temp", "data", ttlMillis = 1000)
        cache.advanceTime(500)
        assertEquals("data", cache.get("temp"), "Non-expired entries should still be retrievable")
    }

    @Test
    fun test_put_multiple_keys_independent() {
        val cache = LocalCacheManager()
        cache.put("x", "1")
        cache.put("y", "2")
        assertEquals("1", cache.get("x"), "Key x should be independent of key y")
        assertEquals("2", cache.get("y"), "Key y should be independent of key x")
    }

    @Test
    fun test_size_decrements_on_remove() {
        val cache = LocalCacheManager()
        cache.put("a", "1")
        cache.put("b", "2")
        assertEquals(2, cache.size)
        cache.remove("a")
        assertEquals(1, cache.size, "Size should decrement after remove")
    }

    @Test
    fun test_clear_resets_size_to_zero() {
        val cache = LocalCacheManager()
        for (i in 1..10) {
            cache.put("key_$i", "val_$i")
        }
        assertTrue(cache.size > 0, "Cache should have entries before clear")
        cache.clear()
        assertEquals(0, cache.size, "Size should be zero after clear")
    }

    @Test
    fun test_overwrite_does_not_increase_size() {
        val cache = LocalCacheManager()
        cache.put("same_key", "value1")
        cache.put("same_key", "value2")
        assertEquals(1, cache.size, "Overwriting a key should not increase size")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    class LocalCacheManager {
        
        private val cache = HashMap<String, CacheEntry>()
        private var currentTimeMillis = System.currentTimeMillis()

        data class CacheEntry(val value: Any, val expiresAt: Long)

        fun get(key: String): Any? {
            val entry = cache[key] ?: return null
            if (currentTimeMillis > entry.expiresAt) {
                cache.remove(key)
                return null
            }
            return entry.value
        }

        
        fun put(key: String, value: Any, ttlMillis: Long = 30 * 60 * 1000L) {
            val expiresAt = currentTimeMillis + ttlMillis
            cache[key] = CacheEntry(value, expiresAt)
        }

        fun remove(key: String) { cache.remove(key) }

        fun clear() { cache.clear() }

        val size: Int get() = cache.size

        fun getMaxCapacity(): Int {
            
            return Int.MAX_VALUE 
        }

        fun usesJavaDuration(): Boolean {
            
            return true 
        }

        fun advanceTime(millis: Long) {
            currentTimeMillis += millis
        }
    }
}
