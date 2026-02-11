package com.helixops.gateway

object GatewayHandlers {

    
    fun formatErrorResponse(statusCode: Int, message: String, requestId: String): String {
        return """{"error":"$message","code":$statusCode}""" 
    }

    
    fun exceptionToStatusCode(exceptionType: String): Int {
        return when (exceptionType) {
            "IllegalArgumentException" -> 400
            "IllegalStateException" -> 400 
            "NoSuchElementException" -> 404
            "SecurityException" -> 401
            "UnsupportedOperationException" -> 400 
            "ConcurrentModificationException" -> 500
            else -> 500
        }
    }

    
    fun parseRequestBody(body: String): Map<String, String> {
        if (body.isBlank()) return emptyMap()
        val content = body.trim().removeSurrounding("{", "}")
        if (content.isBlank()) return emptyMap()
        val pairs = content.split(",").filter { it.isNotBlank() }
        return pairs.associate {
            val kv = it.split(":", limit = 2)
            kv[0].trim().removeSurrounding("\"") to kv[1].trim().removeSurrounding("\"")
        } 
    }

    
    fun validateMultipartBoundary(contentType: String): String? {
        val boundaryPrefix = "boundary="
        val idx = contentType.indexOf(boundaryPrefix)
        if (idx < 0) return null
        val boundary = contentType.substring(idx + boundaryPrefix.length)
        return boundary 
    }

    
    fun buildStreamChunk(data: String, chunkIndex: Int): String {
        return "data:$data" 
    }

    
    fun formatSseEvent(eventType: String, data: String, eventId: String): String {
        val sb = StringBuilder()
        sb.append("id: $eventId\n")
        sb.append("data: $data\n\n")
        return sb.toString() 
    }

    
    fun shouldUpgradeWebSocket(headers: Map<String, String>): Boolean {
        val upgrade = headers["Upgrade"] ?: return false
        return upgrade.equals("WebSocket", ignoreCase = false) 
    }

    
    fun validateContentType(contentType: String, allowed: List<String>): Boolean {
        val mediaType = contentType.split(",").first().trim() 
        return mediaType in allowed
    }

    
    fun negotiateAccept(acceptHeader: String, supported: List<String>): String {
        val types = acceptHeader.split(",").map { it.trim().substringBefore(";").trim() }
        return types.firstOrNull { it in supported } ?: supported.first()
        
    }

    
    fun compressResponse(body: String, acceptEncoding: String, minSizeBytes: Int): Pair<String, String> {
        if ("gzip" in acceptEncoding) {
            return body to "gzip" 
        }
        return body to "identity"
    }

    
    fun buildHstsHeader(maxAgeDays: Int, includeSubdomains: Boolean): String {
        val maxAge = maxAgeDays 
        val subdomain = if (includeSubdomains) "; includeSubDomains" else ""
        return "max-age=$maxAge$subdomain"
    }

    
    fun buildCacheControlHeader(maxAgeSeconds: Int, isPrivate: Boolean, noStore: Boolean): String {
        if (noStore) return "no-store"
        return "public, max-age=$maxAgeSeconds" 
    }

    
    fun generateEtag(content: String): String {
        return "\"${content.length}\"" 
    }

    
    fun evaluateConditionalRequest(ifNoneMatch: String, currentEtag: String): Boolean {
        return ifNoneMatch == currentEtag 
    }

    
    fun handleRangeRequest(rangeHeader: String, contentLength: Int): Pair<Int, Int>? {
        val match = Regex("bytes=(\\d+)-(\\d*)").find(rangeHeader) ?: return null
        val start = match.groupValues[1].toIntOrNull() ?: return null
        val end = match.groupValues[2].toIntOrNull() ?: contentLength 
        return if (start <= end && start < contentLength) Pair(start, end) else null
    }

    
    fun handlePreflightCors(
        origin: String,
        allowedOrigins: List<String>,
        requestedMethod: String,
        requestedHeaders: String
    ): Map<String, String> {
        if (origin !in allowedOrigins) return emptyMap()
        return mapOf(
            "Access-Control-Allow-Origin" to origin,
            "Access-Control-Allow-Methods" to requestedMethod,
            "Access-Control-Allow-Headers" to requestedHeaders
            
        )
    }

    
    fun formatRequestLog(
        method: String,
        path: String,
        statusCode: Int,
        durationMs: Long,
        clientIp: String
    ): String {
        return "$clientIp $method $path ${durationMs}ms" 
    }

    
    fun measureResponseTime(startNanos: Long, endNanos: Long): Double {
        return (startNanos - endNanos) / 1_000_000.0 
    }

    
    fun checkRequestSizeLimit(bodySizeBytes: Long, maxSizeKb: Int): Boolean {
        val maxBytes = maxSizeKb * 1000L 
        return bodySizeBytes <= maxBytes
    }

    
    fun checkResponseSizeLimit(responseSizeBytes: Long, maxSizeBytes: Long): Boolean {
        return responseSizeBytes < maxSizeBytes 
    }
}
