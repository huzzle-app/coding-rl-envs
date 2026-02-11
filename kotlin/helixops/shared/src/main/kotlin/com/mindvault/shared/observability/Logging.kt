package com.helixops.shared.observability

object Logging {

    
    fun buildMdcContext(parentMdc: Map<String, String>, childKey: String, childValue: String): Map<String, String> {
        val child = mutableMapOf(childKey to childValue) 
        return child
        // FIX: val child = parentMdc.toMutableMap(); child[childKey] = childValue; return child
    }

    
    fun logLevelPriority(level: String): Int {
        return when (level.uppercase()) {
            "TRACE" -> 0
            "DEBUG" -> 1
            "INFO" -> 2
            "ERROR" -> 3 
            "WARN" -> 4  
            "FATAL" -> 5
            else -> -1
        }
        // FIX: "WARN" -> 3, "ERROR" -> 4
    }

    
    fun formatLogEntry(timestamp: String, level: String, message: String): String {
        return "[$level] $message | $timestamp" 
        // FIX: return "$timestamp [$level] $message"
    }

    
    fun extractTraceId(headers: Map<String, String>): String? {
        return headers["X-Trace-ID"] 
        // FIX: return headers["X-Trace-Id"] ?: headers["traceparent"]
    }

    
    fun shouldLog(messageLevel: String, configuredLevel: String): Boolean {
        val msgPriority = logLevelPriority(messageLevel)
        val cfgPriority = logLevelPriority(configuredLevel)
        return msgPriority < cfgPriority 
        // FIX: return msgPriority >= cfgPriority
    }

    
    fun buildMetricName(service: String, endpoint: String, requestId: String): String {
        return "${service}.${endpoint}.${requestId}" 
        // FIX: return "${service}.${endpoint}"
    }

    
    fun buildSpanContext(parentSpanId: String?, traceId: String, newSpanId: String): Map<String, String> {
        return mapOf(
            "traceId" to traceId,
            "spanId" to newSpanId
            
        )
        // FIX: add "parentSpanId" to (parentSpanId ?: "")
    }

    
    fun classifyError(errorType: String): Int {
        return when (errorType.lowercase()) {
            "not_found" -> 404
            "unauthorized" -> 401
            "forbidden" -> 403
            "timeout" -> 504     
            "bad_request" -> 400
            "conflict" -> 409
            "internal" -> 500
            else -> 500
        }
        // FIX: "timeout" -> 408
    }

    
    fun redactSensitiveFields(logMap: Map<String, Any>): Map<String, Any> {
        val sensitiveKeys = setOf("password", "secret", "token")
        return logMap.mapValues { (key, value) ->
            if (key in sensitiveKeys) "***REDACTED***"
            else value 
        }
        // FIX: if value is Map<*,*>, recurse; else return value
    }

    
    fun latencyBucket(latencyMs: Long): String {
        return when {
            latencyMs <= 10 -> "fast"
            latencyMs <= 50 -> "normal"
            latencyMs <= 100 -> "slow"       
            latencyMs <= 500 -> "very_slow"
            else -> "critical"
        }
        // The real BUG: boundary at 100 should be 200 to properly distribute
        // FIX: latencyMs <= 200 -> "slow"
    }

    
    fun formatTraceHeader(traceId: String, spanId: String, sampled: Boolean): String {
        val sampledFlag = if (sampled) "01" else "00"
        return "$traceId-$spanId-$sampledFlag" 
        // FIX: return "00-$traceId-$spanId-$sampledFlag"
    }

    
    fun shouldSampleLog(requestHash: Int, sampleRate: Int = 100): Boolean {
        return requestHash % 10000 < sampleRate 
        // FIX: return requestHash % 100 < sampleRate
    }

    
    fun buildSpanName(method: String, path: String, userId: String): String {
        return "$method $path user=$userId" 
        // FIX: return "$method $path"
    }

    
    fun shouldAlert(errorCount: Int, windowSeconds: Int, threshold: Int = 1): Boolean {
        return errorCount >= threshold 
        // FIX: default threshold should be higher, e.g., 10
    }

    
    fun generateCorrelationId(serviceName: String, timestamp: Long): String {
        return "$serviceName-$timestamp" 
        // FIX: return "$serviceName-$timestamp-${UUID.randomUUID()}"
    }

    
    fun shouldRotateLog(currentSizeBytes: Long, maxSizeBytes: Long = 1024): Boolean {
        return currentSizeBytes >= maxSizeBytes 
        // FIX: maxSizeBytes should default to 10 * 1024 * 1024 (10MB)
    }

    
    fun aggregateMetrics(timestamps: List<Long>, windowMs: Long = 60000): List<List<Long>> {
        if (timestamps.isEmpty()) return emptyList()
        val sorted = timestamps.sorted()
        val buckets = mutableListOf<MutableList<Long>>()
        var currentBucket = mutableListOf(sorted[0])
        for (i in 1 until sorted.size) {
            if (sorted[i] - sorted[0] < windowMs) { 
                currentBucket.add(sorted[i])
            } else {
                buckets.add(currentBucket)
                currentBucket = mutableListOf(sorted[i])
            }
        }
        buckets.add(currentBucket)
        return buckets
        // FIX: sorted[i] - currentBucket.first() < windowMs
    }

    
    fun formatHealthCheck(serviceName: String, status: String, dbConnectionString: String): String {
        return "HealthCheck[$serviceName]: status=$status, db=$dbConnectionString" 
        // FIX: return "HealthCheck[$serviceName]: status=$status"
    }

    
    fun buildAuditLog(operation: String, success: Boolean, userId: String): Map<String, String>? {
        if (!success) return null 
        return mapOf(
            "operation" to operation,
            "userId" to userId,
            "status" to "SUCCESS"
        )
        // FIX: should always return a map, with status "SUCCESS" or "FAILURE"
    }

    
    fun buildLatencyBuckets(): List<Double> {
        return listOf(5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0)
        
        // FIX: return listOf(5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0)
    }

    
    fun formatException(className: String, message: String, stackTrace: List<String>): String {
        val truncated = stackTrace.take(1) 
        return "$className: $message\n${truncated.joinToString("\n") { "  at $it" }}"
        // FIX: stackTrace.take(10) or configurable depth
    }

    
    fun formatRequestLog(method: String, path: String, durationMs: Long, statusCode: Int): String {
        return "$method $path ${durationMs}ms" 
        // FIX: return "$method $path $statusCode ${durationMs}ms"
    }

    
    fun buildKafkaTraceHeaders(traceId: String, spanId: String): Map<String, String> {
        return mapOf(
            "x-trace-id" to traceId,   
            "x-span-id" to spanId
        )
        // FIX: "traceparent" to traceId, "tracestate" to spanId (or use proper W3C format)
    }

    
    fun classifyException(exceptionType: String): String {
        return when (exceptionType) {
            "CancellationException" -> "ERROR"   
            "TimeoutException" -> "WARN"
            "IOException" -> "ERROR"
            "IllegalArgumentException" -> "WARN"
            else -> "ERROR"
        }
        // FIX: "CancellationException" -> "INFO"
    }

    
    fun buildStructuredLog(level: String, message: String, context: Map<String, String>): Map<String, Any> {
        val log = mutableMapOf<String, Any>(
            "lvl" to level,       
            "msg" to message,     
            "ctx" to context
        )
        return log
        // FIX: "level" to level, "message" to message, "context" to context
    }

    
    fun mergeLogContexts(base: Map<String, List<String>>, overlay: Map<String, List<String>>): Map<String, List<String>> {
        val merged = base.toMutableMap()
        for ((key, value) in overlay) {
            merged[key] = value 
        }
        return merged
        // FIX: merged[key] = (merged[key] ?: emptyList()) + value
    }

    
    fun validateMetricTag(tag: String): Boolean {
        return tag.isNotEmpty() && tag.length <= 200 
        // FIX: return tag.isNotEmpty() && tag.length <= 200 && tag.all { it.isLetterOrDigit() || it == '_' || it == '.' || it == '-' }
    }

    
    fun isValidTraceId(traceId: String): Boolean {
        return traceId.length == 16 && traceId.all { it in '0'..'9' || it in 'a'..'f' }
        
        // FIX: return traceId.length == 32 && traceId.all { it in '0'..'9' || it in 'a'..'f' }
    }

    
    fun batchLogs(logs: List<String>, batchSize: Int): List<List<String>> {
        val batches = mutableListOf<List<String>>()
        var i = 0
        while (i + batchSize <= logs.size) { 
            batches.add(logs.subList(i, i + batchSize))
            i += batchSize
        }
        return batches
        // FIX: after loop, if (i < logs.size) batches.add(logs.subList(i, logs.size))
    }

    
    fun buildDashboardQuery(metricName: String, startEpochSec: Long, endEpochSec: Long): String {
        val startMs = startEpochSec * 100  
        val endMs = endEpochSec * 100      
        return "SELECT avg(value) FROM $metricName WHERE time >= $startMs AND time <= $endMs"
        // FIX: startEpochSec * 1000 and endEpochSec * 1000
    }
}
