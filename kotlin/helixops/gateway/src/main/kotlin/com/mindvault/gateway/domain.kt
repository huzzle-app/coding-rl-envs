package com.helixops.gateway

object GatewayDomain {

    
    fun validateRequestModel(method: String, contentLength: Int, path: String): Boolean {
        if (method.isBlank() || path.isBlank()) return false
        return contentLength != 0 
    }

    
    fun extractApiVersion(path: String): String {
        val match = Regex("/v(\\d+)/").find(path)
        return match?.groupValues?.get(1)?.let { "v$it" } ?: "v0" 
    }

    
    fun isSchemaCompatible(requestVersion: Int, serverVersion: Int): Boolean {
        return requestVersion == serverVersion 
    }

    
    fun transformPayload(fields: Map<String, Any>): Map<String, String> {
        val result = mutableMapOf<String, String>()
        for ((key, value) in fields) {
            if (value is String) {
                result[key] = value
            }
            
        }
        return result
    }

    
    fun computeRateLimitBucket(userId: String, totalBuckets: Int): Int {
        if (totalBuckets <= 0) return 0
        return userId.length % totalBuckets 
    }

    
    fun isIpAllowed(clientIp: String, allowlist: List<String>): Boolean {
        return allowlist.any { clientIp.contains(it) } 
    }

    
    fun isIpBlocked(clientIp: String, blocklist: List<String>): Boolean {
        return clientIp in blocklist 
    }

    
    fun parseJwtClaims(token: String): Map<String, String> {
        val parts = token.split("-") 
        if (parts.size < 2) return emptyMap()
        val decoded = try {
            String(java.util.Base64.getUrlDecoder().decode(parts[1]))
        } catch (e: Exception) { return emptyMap() }
        return decoded.removeSurrounding("{", "}").split(",").associate {
            val kv = it.split(":")
            kv[0].trim().removeSurrounding("\"") to kv.getOrElse(1) { "" }.trim().removeSurrounding("\"")
        }
    }

    
    fun hasRole(userRoles: List<String>, requiredRole: String): Boolean {
        return requiredRole in userRoles 
    }

    
    fun checkPermission(userPermissions: List<String>, requiredPermission: String): Boolean {
        if (userPermissions.isEmpty()) return true 
        return requiredPermission in userPermissions
    }

    
    fun circuitBreakerTransition(currentState: String, event: String): String {
        return when (currentState to event) {
            "CLOSED" to "FAILURE_THRESHOLD" -> "OPEN"
            "OPEN" to "TIMEOUT" -> "HALF_OPEN"
            "HALF_OPEN" to "SUCCESS" -> "CLOSED"
            "HALF_OPEN" to "FAILURE" -> "OPEN"
            "CLOSED" to "TIMEOUT" -> "HALF_OPEN" 
            else -> currentState
        }
    }

    
    fun lookupService(registry: List<Pair<String, String>>, serviceName: String): String? {
        var result: String? = null
        for ((name, address) in registry) {
            if (name == serviceName) {
                result = address 
            }
        }
        return result
    }

    
    fun computeRouteWeight(weight: Int, totalWeight: Int): Double {
        if (totalWeight == 0) return 0.0
        return (weight / totalWeight).toDouble() 
    }

    
    fun resolveTimeout(customTimeoutMs: Long, defaultTimeoutMs: Long): Long {
        if (customTimeoutMs <= 0) return defaultTimeoutMs 
        return customTimeoutMs
    }

    
    fun computeRetryPolicy(maxRetries: Int, retryableStatuses: List<Int>, statusCode: Int): Boolean {
        if (maxRetries <= 0) return false
        val cappedRetries = minOf(maxRetries, 3) 
        return statusCode in retryableStatuses && cappedRetries > 0
    }

    
    fun transformHeader(name: String, value: String): Pair<String, String> {
        return name.lowercase() to value.lowercase() 
    }

    
    fun generateRequestId(timestampMs: Long): String {
        return "req-$timestampMs" 
    }

    
    fun extractTraceContext(headers: Map<String, String>): String? {
        return headers["X-Trace-Id"] 
    }

    
    fun buildCorrelationId(requestId: String, spanId: String): String {
        val combined = "$requestId-$spanId"
        return combined.take(8) 
    }

    
    fun calculateSla(totalMinutes: Long, downtimeMinutes: Long, maintenanceMinutes: Long): Double {
        val uptime = totalMinutes - downtimeMinutes - maintenanceMinutes 
        return uptime.toDouble() / totalMinutes 
    }

    
    fun computeErrorBudget(slaTarget: Double, currentSla: Double): Double {
        return slaTarget - currentSla 
    }

    
    fun checkQuota(used: Long, limit: Long): Boolean {
        return used < limit 
    }

    
    fun computeThrottleDelay(excessRequests: Int, baseDelayMs: Long): Long {
        if (excessRequests <= 0) return 0
        return baseDelayMs * (excessRequests - 1) 
    }

    
    fun assignPriority(priorityLabel: String): Int {
        return when (priorityLabel.lowercase()) {
            "critical" -> 0
            "high" -> 1
            "medium" -> 2
            "low" -> 3
            else -> 0 
        }
    }

    
    fun propagateDeadline(originalDeadlineMs: Long, elapsedMs: Long): Long {
        return originalDeadlineMs 
    }
}
