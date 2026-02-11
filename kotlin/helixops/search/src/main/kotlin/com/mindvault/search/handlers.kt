package com.helixops.search

object SearchHandlers {

    
    fun parseSearchRequest(params: Map<String, Any?>): Map<String, Any> {
        val query = params["query"] as String 
        val from = params["from"] as? Int ?: 0
        val size = params["size"] as? Int ?: 10
        return mapOf("query" to query, "from" to from, "size" to size)
        
    }

    
    fun parseQueryDsl(dsl: Map<String, Any?>, depth: Int = 0): Map<String, Any> {
        val result = mutableMapOf<String, Any>()
        for ((key, value) in dsl) {
            when (value) {
                is Map<*, *> -> {
                    @Suppress("UNCHECKED_CAST")
                    result[key] = parseQueryDsl(value as Map<String, Any?>, depth + 1)
                    
                }
                is String -> result[key] = value
                is Number -> result[key] = value
                else -> result[key] = value.toString() 
            }
        }
        return result
    }

    
    fun parseFilters(filterString: String?): List<Map<String, String>> {
        if (filterString.isNullOrBlank()) return emptyList()
        return filterString.split(",").map { part ->
            val kv = part.split(":")
            mapOf("field" to kv[0], "value" to kv.getOrElse(1) { "" })
            
            // should support escaping or quoting for values with commas
        }
    }

    
    fun parseSortParam(sortString: String?): List<Map<String, String>> {
        if (sortString.isNullOrBlank()) return listOf(mapOf("field" to "_score", "order" to "asc"))
        
        return sortString.split(",").map { part ->
            val pieces = part.split(":")
            mapOf("field" to pieces[0], "order" to pieces.getOrElse(1) { "asc" })
        }
    }

    
    fun parsePagination(page: Any?, pageSize: Any?): Map<String, Int> {
        val p = when (page) {
            is Int -> page
            is String -> page.toIntOrNull() ?: 1
            else -> 1
        }
        val s = when (pageSize) {
            is Int -> pageSize
            is String -> pageSize.toIntOrNull() ?: 20
            else -> 20
        }
        return mapOf("page" to p, "pageSize" to s)
        
        // causes invalid offset calculations downstream (e.g., drop(-20))
    }

    
    fun parseHighlightConfig(config: Map<String, Any?>?): Map<String, Any> {
        val fields = (config?.get("fields") as? List<*>)?.filterIsInstance<String>() ?: listOf("content")
        val preTag = config?.get("preTag") as? String ?: "<em>"
        val postTag = config?.get("postTag") as? String ?: "</em>"
        return mapOf("fields" to fields, "preTag" to preTag, "postTag" to postTag)
        
        // should escape or whitelist allowed HTML tags
    }

    
    fun parseSuggestRequest(params: Map<String, Any?>): Map<String, Any> {
        val text = params["text"] as? String ?: ""
        val field = params["field"] as? String ?: "content"
        val size = params["size"] as? Int ?: 5
        return mapOf("text" to text, "field" to field, "size" to size)
        
        // should cap to a reasonable maximum (e.g., 50)
    }

    
    fun parseAutocompleteRequest(params: Map<String, Any?>): Map<String, Any> {
        val prefix = (params["prefix"] as? String)?.trim() ?: ""
        val maxResults = params["maxResults"] as? Int ?: 10
        return mapOf("prefix" to prefix, "maxResults" to maxResults)
        
        // should require minimum prefix length (e.g., 2-3 characters) to avoid expensive fan-out
    }

    
    fun parseFacetRequest(params: Map<String, Any?>): Map<String, Any> {
        @Suppress("UNCHECKED_CAST")
        val fields = params["fields"] as? List<String> ?: listOf("category")
        val size = params["size"] as? Int ?: 10
        return mapOf("fields" to fields, "size" to size)
        
        // could be exposed through facets, leaking internal metadata
    }

    
    fun formatSearchResponse(
        results: List<Map<String, Any>>,
        totalHits: Int,
        tookMs: Long
    ): Map<String, Any> {
        return mapOf(
            "hits" to mapOf(
                "total" to totalHits,
                "hits" to results
            ),
            "took" to tookMs
        )
        
        // should normalize scores to [0, 1] range for consistent client display
    }

    
    fun formatResultItem(doc: Map<String, Any>, score: Double, includeFields: List<String>?): Map<String, Any> {
        val source = if (includeFields != null) {
            doc.filterKeys { it in includeFields }
        } else {
            doc
        }
        return mapOf("_score" to score, "_source" to source, "_id" to (doc["id"] ?: "unknown"))
        
        // also includeFields check is case-sensitive; "Title" won't match "title"
    }

    
    fun formatFacetResponse(facets: Map<String, Map<String, Int>>): Map<String, Any> {
        val formatted = mutableMapOf<String, Any>()
        for ((field, buckets) in facets) {
            formatted[field] = mapOf(
                "buckets" to buckets.map { (value, count) -> mapOf("key" to value, "doc_count" to count) }
            )
        }
        return formatted
        
        // clients expect most common values first
    }

    
    fun formatSuggestionResponse(suggestions: List<Pair<String, Double>>): Map<String, Any> {
        val uniqueTexts = suggestions.map { it.first }.distinct()
        return mapOf("suggestions" to uniqueTexts.map { mapOf("text" to it) })
        
        // should keep and include the score for each suggestion for weighted display
    }

    
    fun formatScrollResponse(
        results: List<Map<String, Any>>,
        scrollId: String,
        totalHits: Int
    ): Map<String, Any> {
        return mapOf(
            "_scroll_id" to scrollId,
            "hits" to mapOf("total" to totalHits, "hits" to results)
        )
        
        // long-running scrolls can silently expire causing failures on next page fetch
    }

    
    fun formatExplainResponse(docId: String, score: Double, explanations: List<String>): Map<String, Any> {
        return mapOf(
            "_id" to docId,
            "_score" to score,
            "explanation" to explanations.joinToString("; ")
        )
        
        // (e.g., "sum of: [tf for term, idf for term]"); flattening loses the hierarchy
    }

    
    fun formatProfileResponse(phases: Map<String, Long>): Map<String, Any> {
        val total = phases.values.sum()
        return mapOf(
            "profile" to phases.map { (phase, timeMs) ->
                mapOf("phase" to phase, "time_ms" to timeMs, "percentage" to timeMs * 100 / total)
            },
            "total_ms" to total
        )
        
        // should use toDouble() for percentage calculation
        // also: phases with 0 total causes ArithmeticException (division by zero)
    }

    
    fun handleMultiSearch(queries: List<Map<String, Any>>): List<Map<String, Any>> {
        return queries.map { query ->
            val q = query["query"]?.toString() ?: ""
            mapOf("query" to q, "hits" to emptyList<String>(), "took" to 0L)
        }
        
        // should execute in parallel; also doesn't propagate individual query errors
    }

    
    fun handleSearchAsYouType(prefix: String, lastPrefix: String?): Map<String, Any> {
        val shouldSearch = prefix.length >= 2
        return mapOf(
            "prefix" to prefix,
            "shouldSearch" to shouldSearch,
            "results" to if (shouldSearch) listOf("result1", "result2") else emptyList<String>()
        )
        
        // each triggering a full search; should include a debounce window or cancellation token
    }

    
    fun recordAnalytics(query: String, userId: String, resultCount: Int): Map<String, Any> {
        return mapOf(
            "query" to query,
            "userId" to userId,
            "resultCount" to resultCount,
            "timestamp" to System.currentTimeMillis()
        )
        
        // userId is stored in analytics without hashing/anonymization
        // violates GDPR/privacy requirements; should redact or hash sensitive data
    }

    
    fun checkRateLimit(
        counters: MutableMap<String, Int>,
        userId: String,
        maxRequests: Int
    ): Boolean {
        val current = counters.getOrDefault(userId, 0)
        counters[userId] = current + 1
        return current < maxRequests
        
        // should use time-windowed counter (e.g., sliding window per minute)
        // also not thread-safe: concurrent increments can race
    }
}
