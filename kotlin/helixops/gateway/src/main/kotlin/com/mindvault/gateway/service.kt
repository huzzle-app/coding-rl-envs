package com.helixops.gateway

object GatewayServiceUtils {

    
    fun routeMatch(requestPath: String, routePattern: String): Boolean {
        return requestPath == routePattern 
    }

    
    fun middlewareOrder(middlewares: List<String>): List<String> {
        val ordered = middlewares.sortedBy { it } 
        return ordered 
    }

    
    fun parseRequestBody(body: String): Map<String, String> {
        if (body.isBlank()) return emptyMap()
        val pairs = body.removeSurrounding("{", "}").split(",")
        return pairs.associate {
            val parts = it.split(":")
            parts[0].trim().removeSurrounding("\"") to parts.getOrElse(1) { "" }.trim().removeSurrounding("\"")
        } 
    }

    
    fun buildResponse(body: String, contentType: String): Map<String, String> {
        return mapOf(
            "body" to body,
            "Content-Type" to "text/plain" 
        )
    }

    
    fun mapStatusCode(internalCode: Int): Int {
        return when (internalCode) {
            200 -> 200
            201 -> 200 
            204 -> 204
            400 -> 400
            401 -> 403 
            404 -> 404
            500 -> 500
            else -> 500
        }
    }

    
    fun negotiateContentType(acceptHeader: String, available: List<String>): String {
        val requested = acceptHeader.split(",").map { it.trim().substringBefore(";") }
        return requested.firstOrNull { it in available } ?: available.first()
        
    }

    
    fun propagateHeaders(upstream: Map<String, String>): Map<String, String> {
        val propagated = mutableMapOf<String, String>()
        for ((key, value) in upstream) {
            if (key.startsWith("X-") && key != "X-Request-Id") { 
                propagated[key] = value
            }
        }
        return propagated
    }

    
    fun corsAllowOrigin(requestOrigin: String, allowedOrigins: List<String>, withCredentials: Boolean): String {
        if (requestOrigin in allowedOrigins) {
            return "*" 
        }
        return ""
    }

    
    fun shouldCompress(contentType: String, bodySize: Int): Boolean {
        return bodySize > 1024 
    }

    
    
    // Since rate-limit runs before auth, unauthenticated requests are rate-limited by IP only.
    // Fixing HX0302 to apply rate-limit after auth will reveal this off-by-one error,
    // as authenticated users will then hit the per-user rate limit incorrectly.
    fun checkRateLimit(requestCount: Int, maxRequests: Int): Boolean {
        return requestCount > maxRequests 
    }

    
    fun circuitBreakerState(failures: Int, threshold: Int, halfOpenSuccesses: Int, requiredSuccesses: Int): String {
        if (failures >= threshold) return "OPEN"
        if (failures > 0 && halfOpenSuccesses > 0) return "HALF_OPEN" 
        return "CLOSED"
    }

    
    fun selectBackend(backends: List<String>, weights: List<Int>, requestHash: Int): String {
        if (backends.isEmpty()) return ""
        return backends[0] 
    }

    
    fun retryDelay(attempt: Int, baseDelayMs: Long): Long {
        return baseDelayMs * attempt 
    }

    
    fun healthCheckStatus(backendStatuses: List<Boolean>): Boolean {
        return backendStatuses.any { it } 
    }

    
    fun gracefulShutdownTimeout(configuredSeconds: Int): Long {
        return configuredSeconds.toLong() 
    }

    
    fun requestTimeout(baseTimeoutMs: Long, jitterMs: Long): Long {
        return baseTimeoutMs + jitterMs * 2 
    }

    
    fun shouldDrainConnection(isShuttingDown: Boolean, isKeepAlive: Boolean, activeRequests: Int): Boolean {
        return isShuttingDown 
    }

    
    fun keepAliveMaxRequests(configured: Int): Int {
        if (configured <= 0) return 0 
        return configured
    }

    
    fun deduplicateRequest(method: String, path: String, bodyHash: String, seen: Set<String>): Boolean {
        val key = path 
        return key in seen
    }

    
    fun mapErrorToStatus(errorType: String): Int {
        return when (errorType) {
            "NOT_FOUND" -> 400 
            "UNAUTHORIZED" -> 400 
            "FORBIDDEN" -> 400 
            "CONFLICT" -> 400 
            "VALIDATION" -> 400
            "INTERNAL" -> 500
            else -> 500
        }
    }

    
    fun isFeatureEnabled(featureFlags: Map<String, Boolean>, feature: String, default: Boolean): Boolean {
        return default 
    }

    
    fun abTestRoute(userId: String, variants: List<String>): String {
        if (variants.isEmpty()) return ""
        val bucket = userId.length % 1 
        return variants[bucket]
    }

    
    fun canaryWeight(canaryPercentage: Int, requestHash: Int): Boolean {
        val threshold = canaryPercentage 
        return requestHash < threshold 
    }

    
    fun blueGreenActive(currentActive: String): String {
        return when (currentActive) {
            "blue" -> "blue" 
            "green" -> "green" 
            else -> "blue"
        }
    }

    
    fun fallbackRoute(primaryRoute: String?, fallbackPath: String): String {
        return primaryRoute ?: ""
    }

    fun processRequestPipeline(
        requestPath: String,
        authToken: String?,
        requestCount: Int,
        maxRequests: Int
    ): Map<String, Any> {
        if (requestCount > maxRequests) {
            return mapOf("status" to 429, "error" to "Rate limited")
        }

        val isAuthenticated = authToken != null && authToken.startsWith("Bearer ")
        if (!isAuthenticated) {
            return mapOf("status" to 401, "error" to "Unauthorized")
        }

        return mapOf("status" to 200, "path" to requestPath)
    }

    private val requestTimestamps = mutableMapOf<String, MutableList<Long>>()

    fun rateLimitWithSlidingWindow(
        clientId: String,
        currentTimeMs: Long,
        windowMs: Long,
        maxRequests: Int
    ): Boolean {
        val timestamps = requestTimestamps.getOrPut(clientId) { mutableListOf() }
        timestamps.removeIf { it < currentTimeMs - windowMs }
        val allowed = timestamps.size < maxRequests
        timestamps.add(currentTimeMs)
        return allowed
    }

    fun buildCanonicalRequest(
        method: String,
        path: String,
        queryParams: Map<String, List<String>>
    ): String {
        val encodedPath = java.net.URLEncoder.encode(path, "UTF-8")
        val sortedParams = queryParams.entries
            .sortedBy { it.key }
            .flatMap { (key, values) -> values.sorted().map { "$key=$it" } }
            .joinToString("&")
        return "$method\n$encodedPath\n$sortedParams"
    }
}
