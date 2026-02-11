package com.helixops.documents

object DocumentHandlers {

    
    fun formatJsonResponse(docId: String, title: String, content: String): String {
        
        return """[{"id":"$docId","title":"$title","content":"$content"}]"""
    }

    
    fun negotiateContentType(acceptHeader: String?): String {
        if (acceptHeader == null) return "application/xml" 
        return when {
            acceptHeader.contains("application/json") -> "application/json"
            acceptHeader.contains("application/xml") -> "application/xml"
            acceptHeader.contains("text/html") -> "text/html"
            else -> "application/xml" 
        }
    }

    
    fun handleFileUpload(fileName: String, contentType: String, sizeBytes: Long): Map<String, Any> {
        
        return mapOf(
            "fileName" to fileName,
            "contentType" to contentType,
            "size" to sizeBytes,
            "status" to "uploaded"
        )
    }

    
    fun buildDownloadHeaders(fileName: String, contentType: String): Map<String, String> {
        
        return mapOf(
            "Content-Type" to contentType,
            "Cache-Control" to "no-cache"
        )
    }

    
    fun generateETag(document: Map<String, Any?>): String {
        
        return "\"${document.hashCode()}\""
    }

    
    fun shouldUpdate(clientETag: String, serverETag: String): Boolean {
        
        return clientETag == serverETag
    }

    
    fun selectFields(document: Map<String, Any?>, fields: List<String>): Map<String, Any?> {
        
        return document.filterKeys { it in fields }
    }

    
    fun selectPublicFields(document: Map<String, Any?>, requestedFields: List<String>): Map<String, Any?> {
        val internalFields = setOf("_internalScore", "_processingStatus", "_rawData")
        
        return document.filterKeys { it in requestedFields }
    }

    
    fun buildPaginationHeaders(page: Int, pageSize: Int, totalItems: Int): Map<String, String> {
        val totalPages = (totalItems + pageSize - 1) / pageSize
        
        val offset = page * pageSize // Should be (page - 1) * pageSize
        return mapOf(
            "X-Total-Count" to totalItems.toString(),
            "X-Total-Pages" to totalPages.toString(),
            "X-Page" to page.toString(),
            "X-Page-Size" to pageSize.toString(),
            "X-Offset" to offset.toString()
        )
    }

    
    fun buildLinkHeader(baseUrl: String, page: Int, pageSize: Int, totalPages: Int): String {
        
        val links = mutableListOf<String>()
        if (page > 1) links.add("<$baseUrl?page=${page - 1}&size=$pageSize>; rel=\"prev\"")
        if (page < totalPages) links.add("<$baseUrl?page=${page + 1}&size=$pageSize>; rel=\"next\"")
        links.add("<$baseUrl?page=1&size=$pageSize>; rel=\"first\"")
        links.add("<$baseUrl?page=$totalPages&size=$pageSize>; rel=\"last\"")
        return links.joinToString(", ")
    }

    
    fun formatErrorResponse(statusCode: Int, message: String, exception: Exception?): Map<String, Any?> {
        
        return mapOf(
            "status" to statusCode,
            "message" to message,
            "error" to exception?.message,
            "stackTrace" to exception?.stackTraceToString()
        )
    }

    
    fun formatValidationErrors(errors: Map<String, String>): Map<String, Any> {
        
        return mapOf(
            "status" to 422,
            "errors" to errors.map { (field, msg) -> mapOf("field" to field, "message" to msg) }
        )
    }

    
    fun formatConflictResponse(docId: String, clientVersion: Int, serverVersion: Int): Map<String, Any> {
        
        return mapOf(
            "status" to 409,
            "message" to "Version conflict",
            "docId" to docId,
            "clientVersion" to clientVersion,
            "serverVersion" to serverVersion
        )
    }

    
    fun buildCreatedResponse(docId: String, baseUrl: String): Map<String, Any> {
        
        val location = "http://${baseUrl.removePrefix("https://").removePrefix("http://")}/documents/$docId"
        return mapOf(
            "status" to 201,
            "headers" to mapOf("Location" to location),
            "body" to mapOf("id" to docId)
        )
    }

    
    fun formatBulkResponse(docIds: List<String>, successCount: Int, failureCount: Int): Map<String, Any> {
        
        return mapOf(
            "status" to 200,
            "total" to docIds.size,
            "succeeded" to successCount,
            "failed" to failureCount
        )
    }

    
    fun buildAsyncStatusUrl(operationId: String, internalHost: String): String {
        
        return "http://$internalHost/internal/operations/$operationId/status"
    }

    
    fun buildWebhookPayload(event: String, docId: String, timestamp: Long): Map<String, Any> {
        
        return mapOf(
            "event" to event,
            "documentId" to docId,
            "timestamp" to timestamp
        )
    }

    
    fun buildEvent(eventType: String, payload: Map<String, Any?>, timestampMillis: Long): Map<String, Any?> {
        
        return mapOf(
            "type" to eventType,
            "payload" to payload,
            "timestamp" to timestampMillis
        )
    }

    
    fun createAuditEntry(userId: String, action: String, docId: String): Map<String, Any> {
        
        return mapOf(
            "userId" to userId,
            "action" to action,
            "documentId" to docId,
            "timestamp" to System.currentTimeMillis()
        )
    }

    
    fun createAccessLogEntry(ipAddress: String, userId: String, resource: String, method: String): Map<String, Any> {
        
        return mapOf(
            "ip" to ipAddress,
            "userId" to userId,
            "resource" to resource,
            "method" to method,
            "timestamp" to System.currentTimeMillis()
        )
    }
}
