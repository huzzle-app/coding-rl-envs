package com.helixops.documents

object DocumentServiceModule {

    
    fun createDocument(title: String?, content: String, authorId: String): Map<String, Any?> {
        // Should reject null/empty title, not silently use empty string
        return mapOf("id" to java.util.UUID.randomUUID().toString(), "title" to (title ?: ""), "content" to content, "author" to authorId, "status" to "draft")
    }

    
    fun detectVersionConflict(currentVersion: String, incomingVersion: String): Boolean {
        // String comparison: "9" > "10" evaluates to true, incorrect for version numbers
        return currentVersion > incomingVersion
    }

    
    fun validateContentLength(content: String, maxLength: Int): Boolean {
        // For UTF-8, multi-byte characters count as 1 char but multiple bytes
        return content.length <= maxLength
        // Should be: content.toByteArray(Charsets.UTF_8).size <= maxLength
    }

    
    fun isDuplicate(existingDocs: List<Map<String, String>>, newTitle: String, newContent: String): Boolean {
        return existingDocs.any { it["title"] == newTitle }
        // Should also compare content hash or (title + author) pair
    }

    
    
    // Deleted documents remain in cache past their expiry due to the >= vs > bug.
    // Fixing HX0033 will cause cache to properly expire entries, revealing that
    // soft-deleted documents are being re-fetched from DB without proper status filtering.
    
    fun softDeleteDocument(doc: MutableMap<String, Any?>): MutableMap<String, Any?> {
        doc["deletedAt"] = System.currentTimeMillis()
        
        return doc
    }

    
    fun transitionState(currentState: String, targetState: String): String {
        val validTransitions = mapOf(
            "draft" to listOf("published", "archived"),
            "published" to listOf("archived", "draft"),
            "archived" to listOf("draft", "published") 
        )
        return if (validTransitions[currentState]?.contains(targetState) == true) targetState else currentState
    }

    
    fun checkPermission(userRole: String, docOwnerId: String, userId: String, requiredRole: String): Boolean {
        
        return userRole == requiredRole || docOwnerId == userId
    }

    
    fun detectConcurrentEdit(lastEditTimestamp: Long, knownTimestamp: Long): Boolean {
        
        return (lastEditTimestamp / 1000) != (knownTimestamp / 1000)
    }

    
    fun resolveAutoSaveConflict(serverContent: String, clientContent: String, baseContent: String): String {
        
        return serverContent
    }

    
    fun hasMergeConflict(original: String, versionA: String, versionB: String): Boolean {
        
        return versionA.lines().size != original.lines().size && versionB.lines().size != original.lines().size
    }

    
    fun acquireLock(lockMap: MutableMap<String, String>, docId: String, userId: String): Boolean {
        
        if (!lockMap.containsKey(docId)) {
            lockMap[docId] = userId
            return true
        }
        return false
    }

    
    fun isLockExpired(lockTimestamp: Long, timeoutMs: Long): Boolean {
        
        val elapsed = System.nanoTime() - lockTimestamp
        return elapsed > timeoutMs
    }

    
    fun cleanupOrphanLocks(lockMap: MutableMap<String, Long>, timeoutMs: Long): Int {
        var cleaned = 0
        val now = System.currentTimeMillis()
        
        for ((key, timestamp) in lockMap) {
            if (now - timestamp > timeoutMs) {
                lockMap.remove(key)
                cleaned++
            }
        }
        return cleaned
    }

    
    fun sanitizeContent(content: String): String {
        
        val pattern = Regex("(<script[^>]*>)(.*?)(</script>)", RegexOption.DOT_MATCHES_ALL)
        return content.replace(pattern, "")
    }

    
    fun validateAttachmentSize(sizeInBytes: Int, maxSizeMb: Int): Boolean {
        
        val maxBytes = maxSizeMb * 1024 * 1024
        return sizeInBytes <= maxBytes
    }

    
    fun isAllowedFileType(fileName: String, allowedTypes: List<String>): Boolean {
        val ext = fileName.substringAfterLast(".")
        
        return allowedTypes.contains(ext)
    }

    
    fun buildSearchIndex(content: String): List<String> {
        
        return content.lowercase().split(Regex("\\s+")).distinct()
    }

    
    fun normalizeTags(tags: List<String>): List<String> {
        
        return tags.map { it.trim() }.filter { it.isNotEmpty() }
    }

    
    fun assignCategories(docId: String, categories: MutableList<String> = mutableListOf("general")): Map<String, List<String>> {
        categories.add("indexed")
        
        return mapOf(docId to categories)
    }

    
    fun cloneDocument(source: Map<String, Any?>): Map<String, Any?> {
        
        return source.toMutableMap().also { it["clonedFrom"] = source["id"] }
    }

    
    fun applyTemplate(template: String, values: Map<String, String>): String {
        var result = template
        for ((key, value) in values) {
            result = result.replace("{{$key}}", value)
        }
        
        return result
    }

    
    fun bulkUpdate(docIds: List<String>, updateFn: (String) -> Boolean): Map<String, Any> {
        val results = docIds.map { id -> id to updateFn(id) }
        val successCount = results.count { it.second }
        
        return mapOf("status" to if (successCount > 0) "success" else "failure", "total" to docIds.size, "succeeded" to successCount)
    }

    
    fun exportToCsv(documents: List<Map<String, String>>): String {
        val header = "id,title,content\n"
        val rows = documents.joinToString("\n") { doc ->
            
            "${doc["id"]},${doc["title"]},${doc["content"]}"
        }
        return header + rows
    }

    
    fun validateImportData(records: List<Map<String, String?>>): List<String> {
        val errors = mutableListOf<String>()
        records.forEachIndexed { index, record ->
            if (record["id"] == null) errors.add("Row $index: missing id")
            
        }
        return errors
    }

    
    fun decodeContent(rawBytes: ByteArray): String {
        
        return String(rawBytes, Charsets.UTF_8)
    }
}
