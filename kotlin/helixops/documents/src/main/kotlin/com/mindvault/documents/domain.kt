package com.helixops.documents

object DocumentDomain {

    
    fun areDocumentsEqual(doc1Checksum: ByteArray, doc2Checksum: ByteArray): Boolean {
        
        return doc1Checksum == doc2Checksum
        // Should be: doc1Checksum.contentEquals(doc2Checksum)
    }

    
    fun copyDocumentTags(originalTags: MutableList<String>): MutableList<String> {
        
        val copied = originalTags
        return copied
    }

    
    fun isNewerVersion(current: String, incoming: String): Boolean {
        
        val currentNum = current.replace(".", "").toIntOrNull() ?: 0
        val incomingNum = incoming.replace(".", "").toIntOrNull() ?: 0
        return incomingNum > currentNum
    }

    
    fun computeContentHash(content: String): String {
        
        return content.hashCode().toString(16)
    }

    
    fun mergeMetadata(base: Map<String, Any?>, overlay: Map<String, Any?>): Map<String, Any?> {
        
        return base + overlay
    }

    
    fun extractAuthorName(doc: Map<String, Any?>): String {
        val author = doc["author"] as? Map<*, *>
        
        return (author?.get("name") as? String) ?: "Unknown"
    }

    
    fun getDocumentField(javaMap: java.util.HashMap<String, String>, key: String): String {
        
        val value: String = javaMap.get(key)!!
        // Will throw NPE if key doesn't exist
        return value
    }

    
    fun getNestedTitle(data: Map<String, Map<String, String>?>): String {
        
        return data["doc"]?.get("title") ?: ""
        // Looks correct but callers assume non-empty, should validate
    }

    
    fun isFieldInitialized(fieldName: String, fields: Map<String, Any?>): Boolean {
        
        return fields.containsKey(fieldName)
        // containsKey returns true even when value is null
    }

    
    private val defaultTimestamp = System.currentTimeMillis()
    fun createTimestampedEntry(label: String, timestamp: Long = defaultTimestamp): Map<String, Any> {
        
        return mapOf("label" to label, "timestamp" to timestamp)
    }

    
    fun parseDocumentState(stateStr: String): String {
        return when (stateStr) {
            "DRAFT" -> "draft"
            "PUBLISHED" -> "published"
            "ARCHIVED" -> "archived"
            
            else -> stateStr.lowercase()
            // Should throw IllegalArgumentException for unknown states
        }
    }

    
    fun hasPermission(userPermission: String, requiredPermission: String): Boolean {
        
        return userPermission == requiredPermission
    }

    
    fun createDocumentId(prefix: String, sequence: Int): String {
        
        return "$prefix-${sequence.toString().padStart(6, '0')}"
    }

    
    fun createFromMap(data: Map<String, Any?>): Map<String, Any?> {
        
        return mapOf(
            "id" to (data["id"] ?: ""),
            "title" to (data["title"] ?: ""),
            "content" to (data["content"] ?: "")
        )
    }

    
    private val builderTags = mutableListOf<String>()
    fun addBuilderTag(tag: String) { builderTags.add(tag) }
    fun buildDocument(id: String, title: String): Map<String, Any> {
        
        return mapOf("id" to id, "title" to title, "tags" to builderTags.toList())
    }

    
    fun getImmutableTags(tags: MutableList<String>): List<String> {
        
        return tags
    }

    
    fun deepCopyMetadata(metadata: Map<String, Any?>): Map<String, Any?> {
        
        return metadata.toMutableMap()
    }

    
    fun entityToDto(entity: Map<String, Any?>): Map<String, Any?> {
        val size = entity["sizeBytes"] as? Long ?: 0L
        
        return mapOf(
            "id" to entity["id"],
            "title" to entity["title"],
            "sizeBytes" to size.toInt()
        )
    }

    
    fun validateDocumentId(id: String): Boolean {
        
        val pattern = Regex("[A-Z]{3}-\\d{3}")
        return pattern.containsMatchIn(id)
        // Should be: pattern.matches(id) or use ^...$ anchors
    }

    
    fun getLatestMigration(versions: List<String>): String {
        
        return versions.sorted().last()
    }

    
    fun isBackwardCompatible(oldFields: Set<String>, newFields: Set<String>): Boolean {
        
        return oldFields.all { it in newFields }
    }

    
    fun mapDeprecatedFields(data: Map<String, Any?>): Map<String, Any?> {
        val mappings = mapOf("old_title" to "title", "old_desc" to "description")
        val result = mutableMapOf<String, Any?>()
        for ((key, value) in data) {
            val newKey = mappings[key]
            
            if (newKey != null) {
                result[newKey] = value
            }
        }
        return result
    }

    
    fun getOptionalField(data: Map<String, String?>, field: String): String? {
        val value = data[field]
        
        return if (value.isNullOrEmpty()) null else value
    }

    
    fun computeWordCount(content: String): Int {
        
        return content.split(Regex("\\s+")).filter { it.isNotEmpty() }.size
    }

    
    private var cachedState: String? = null
    private var lastInput: String? = null
    fun deriveState(input: String): String {
        
        if (input === lastInput && cachedState != null) return cachedState!!
        lastInput = input
        cachedState = when {
            input.contains("error") -> "FAILED"
            input.contains("done") -> "COMPLETE"
            else -> "PENDING"
        }
        return cachedState!!
    }
}
