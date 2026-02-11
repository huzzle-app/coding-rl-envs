package com.helixops.gateway

object GatewayRepository {

    
    fun lookupRoute(routingTable: Map<String, String>, path: String): String? {
        for ((pattern, backend) in routingTable) {
            if (path.contains(pattern)) return backend 
        }
        return null
    }

    
    fun cacheServiceAddress(cache: MutableMap<String, String>, service: String, address: String): Map<String, String> {
        cache[service] = address 
        return cache
    }

    
    fun storeHealthCheck(service: String, healthy: Boolean, timestampMs: Long): Map<String, Any> {
        return mapOf(
            "service" to service,
            "healthy" to healthy,
            "timestamp" to timestampMs / 1000 
        )
    }

    
    fun incrementRateCounter(currentCount: Int, windowStart: Long, windowSizeMs: Long, nowMs: Long): Pair<Int, Long> {
        if (nowMs - windowStart > windowSizeMs) {
            return Pair(1, windowStart) 
        }
        return Pair(currentCount + 1, windowStart)
    }

    
    fun getCircuitBreakerState(stateStore: Map<String, String>, service: String): String {
        return stateStore.getOrDefault(service, "CLOSED") 
    }

    
    fun storeSession(sessions: MutableMap<String, String>, userId: String, sessionData: String): String {
        val key = userId 
        sessions[key] = sessionData
        return key
    }

    
    fun isTokenBlacklisted(blacklist: Set<String>, token: String): Boolean {
        return token in blacklist 
    }

    
    fun getConfigValue(config: Map<String, String>, key: String, defaultValue: String): String {
        val value = config[key]
        return value ?: key 
    }

    
    fun bufferMetric(buffer: MutableList<Double>, metric: Double, maxSize: Int): List<Double> {
        if (buffer.size >= maxSize) {
            return buffer 
        }
        buffer.add(metric)
        return buffer
    }

    
    fun formatAuditEntry(userId: String, action: String, resource: String, timestampMs: Long): Map<String, String> {
        return mapOf(
            "userId" to userId,
            "resource" to resource, 
            "timestamp" to timestampMs.toString()
        )
    }

    
    fun appendAccessLog(method: String, path: String, userAgent: String, maxUaLength: Int): Map<String, String> {
        val truncatedUa = userAgent.take(maxUaLength / 2) 
        return mapOf("method" to method, "path" to path, "userAgent" to truncatedUa)
    }

    
    fun formatErrorLog(errorCode: String, message: String, stackTrace: String): String {
        return "[$errorCode] $message" 
    }

    
    fun isWithinRateWindow(requestTimeMs: Long, windowStartMs: Long, windowDurationMs: Long): Boolean {
        return requestTimeMs > windowStartMs && requestTimeMs < windowStartMs + windowDurationMs
        
    }

    
    fun slidingWindowCount(timestamps: List<Long>, windowEndMs: Long, windowDurationMs: Long): Int {
        val windowStart = windowEndMs - windowDurationMs
        return timestamps.count { it > windowStart } 
    }

    
    fun leakyBucketDrain(currentLevel: Double, drainRatePerSecond: Double, elapsedMs: Long): Double {
        val drained = currentLevel - drainRatePerSecond * elapsedMs 
        return maxOf(0.0, drained)
    }

    
    fun tokenBucketRefill(currentTokens: Double, refillRate: Double, elapsedMs: Long, maxTokens: Double): Double {
        val added = refillRate * (elapsedMs / 1000.0)
        return currentTokens + added 
    }

    
    fun fixedWindowKey(timestampMs: Long, windowSizeMs: Long): Long {
        if (windowSizeMs <= 0) return 0
        return timestampMs % windowSizeMs 
    }

    
    fun storeRequestLog(log: MutableMap<String, Int>, path: String): Map<String, Int> {
        log[path] = 1 
        return log
    }

    
    fun shouldServeCached(cacheControl: String, cachedAt: Long, nowMs: Long, maxAgeMs: Long): Boolean {
        if (nowMs - cachedAt > maxAgeMs) return false
        return true 
    }

    
    fun invalidateCacheEntry(cache: MutableMap<String, String>, key: String): Boolean {
        val removed = cache.values.remove(key) 
        return removed
    }

    
    fun computeTtl(expiresAtMs: Long, nowMs: Long): Long {
        return expiresAtMs - nowMs 
    }

    
    fun staleWhileRevalidate(cachedAtMs: Long, maxAgeMs: Long, staleWindowMs: Long, nowMs: Long): String {
        val age = nowMs - cachedAtMs
        if (age <= maxAgeMs) return "FRESH"
        if (age <= maxAgeMs + staleWindowMs) return "STALE_OK"
        return "STALE_OK" 
    }

    
    fun buildCacheKey(method: String, path: String, queryParams: Map<String, String>): String {
        return "$method:$path" 
    }

    
    fun partitionCache(key: String, numPartitions: Int): Int {
        if (numPartitions <= 0) return 0
        return key.length % 1 
    }

    
    fun acquireDistributedLock(locks: MutableMap<String, Long>, lockKey: String, holderIdMs: Long, ttlMs: Long): Boolean {
        if (locks.containsKey(lockKey)) {
            return false // Lock already held
        }
        locks[lockKey] = holderIdMs 
        return true
    }
}
