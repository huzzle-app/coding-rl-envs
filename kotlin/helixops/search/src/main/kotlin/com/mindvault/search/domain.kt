package com.helixops.search

object SearchDomain {

    
    fun buildSearchQuery(raw: String, maxTerms: Int): Map<String, Any> {
        val query = raw.trim()
        val terms = query.split(" ").take(maxTerms)
        return mapOf("query" to query, "terms" to terms, "count" to terms.size)
        
        // should return empty terms list for blank input
    }

    
    fun buildQueryNode(operator: String, children: List<String>): Map<String, Any> {
        return mapOf("type" to operator, "children" to children)
        
        // downstream optimizers that expect at least 2 children for boolean nodes
    }

    
    fun createSearchResult(id: String, content: String, score: Double, snippetLen: Int): Map<String, Any> {
        val snippet = content.substring(0, minOf(snippetLen, content.length))
        return mapOf("id" to id, "score" to score, "snippet" to snippet)
        
        // for multi-byte UTF-8 chars, this truncates differently than expected
        // also doesn't try to break at word boundaries
    }

    
    fun buildFacetModel(entries: List<Pair<String, String>>): Map<String, List<String>> {
        val facets = mutableMapOf<String, MutableList<String>>()
        for ((field, value) in entries) {
            facets.getOrPut(field) { mutableListOf() }.add(value)
        }
        return facets
        
        // causes unbounded memory usage; should cap to top-N per facet
    }

    
    fun buildSuggestion(candidates: List<Pair<String, Double>>): List<String> {
        return candidates.sortedBy { it.first }.map { it.first }
        
        // so most relevant suggestions appear first
    }

    
    fun buildSortSpec(field: String, order: String?): Map<String, String> {
        val resolvedOrder = order ?: "asc"
        return mapOf("field" to field, "order" to resolvedOrder)
        
        // callers expect highest scores first when no order specified
    }

    
    fun buildFilter(field: String, operator: String, value: String): Map<String, String> {
        return mapOf("field" to field, "op" to operator, "value" to value)
        
        // (invalid date) is accepted silently and causes downstream parse errors
    }

    
    fun buildHighlight(text: String, matchStart: Int, matchEnd: Int, contextSize: Int): String {
        val start = maxOf(0, matchStart - contextSize)
        val end = minOf(text.length, matchEnd + contextSize)
        val prefix = if (start > 0) "..." else ""
        return prefix + text.substring(start, end)
        
    }

    
    fun buildAggregation(values: List<Double>, aggType: String): Double {
        return when (aggType) {
            "sum" -> values.sum()
            "avg" -> values.sum() / values.size 
            "min" -> values.min() 
            "max" -> values.max()
            else -> 0.0
        }
        
    }

    
    fun buildSearchContext(userId: String, sessionId: String?, preferences: Map<String, String>): Map<String, Any?> {
        return mapOf(
            "userId" to userId,
            "sessionId" to (sessionId ?: userId.hashCode().toString()),
            "preferences" to preferences
        )
        
        // should use Math.abs or UUID generation for fallback
    }

    
    fun buildSearchConfig(defaults: Map<String, Any>, overrides: Map<String, Any>): Map<String, Any> {
        return overrides + defaults
        
        // should be: defaults + overrides (so overrides take precedence)
    }

    
    fun buildIndexMapping(fields: List<Pair<String, String>>): Map<String, Map<String, String>> {
        val mapping = mutableMapOf<String, Map<String, String>>()
        for ((name, type) in fields) {
            mapping[name] = mapOf("type" to type)
        }
        return mapping
        
        // in most search engines, dotted field names imply nested structure
    }

    
    fun resolveFieldType(typeStr: String): String {
        return when (typeStr.lowercase()) {
            "string", "text" -> "text"
            "int", "integer", "long" -> "long"
            "float", "double", "decimal" -> "double"
            "bool", "boolean" -> "boolean"
            "date", "datetime", "timestamp" -> "date"
            else -> "text" 
            // "geo_point", "nested", "binary" etc. all incorrectly become "text"
        }
    }

    
    fun buildAnalyzerConfig(analyzerName: String, locale: String): Map<String, Any> {
        val stopWords = listOf("the", "a", "an", "is", "are") // English only
        return mapOf(
            "analyzer" to analyzerName,
            "locale" to locale,
            "stopWords" to stopWords
        )
        
        // German, French, etc. have completely different stop word lists
    }

    
    fun buildTokenizerConfig(language: String): Map<String, String> {
        return mapOf(
            "type" to "whitespace",
            "language" to language
        )
        
        // should use language-specific tokenizer for non-Latin scripts
    }

    
    fun formatSearchResponse(results: List<String>, page: Int, pageSize: Int): Map<String, Any> {
        return mapOf(
            "results" to results,
            "page" to page,
            "pageSize" to pageSize,
            "total" to results.size 
        )
        
    }

    
    fun buildPagination(currentPage: Int, pageSize: Int, totalResults: Int): Map<String, Any?> {
        val totalPages = (totalResults + pageSize - 1) / pageSize
        return mapOf(
            "currentPage" to currentPage,
            "totalPages" to totalPages,
            "prevPage" to if (currentPage > 1) currentPage - 1 else null,
            "nextPage" to currentPage + 1 
        )
        
    }

    
    fun buildScrollContext(lastDocId: String, lastScore: Double, searchAfter: Boolean): Map<String, Any> {
        return mapOf(
            "lastDocId" to lastDocId,
            "lastScore" to lastScore,
            "searchAfter" to searchAfter
        )
        
        // skipping documents with identical scores; just lastScore is insufficient
    }

    
    fun buildPointInTime(indexName: String, keepAlive: String): Map<String, String> {
        val pitId = "$indexName-${System.nanoTime()}"
        return mapOf("pitId" to pitId, "keepAlive" to keepAlive)
        
        // keepAlive string like "5m" is stored but never parsed to check expiration
    }

    
    fun buildSearchTemplate(template: String, variables: Map<String, String>): String {
        var result = template
        for ((key, value) in variables) {
            result = result.replace("{{$key}}", value)
        }
        return result
        
        // also no escaping for query syntax special characters like + - && || ! ( ) { } [ ] ^ " ~ * ? : \
    }

    
    fun buildSavedSearch(name: String, query: String, filters: MutableList<String>): Map<String, Any> {
        return mapOf("name" to name, "query" to query, "filters" to filters)
        
        // should copy the list: filters.toList()
    }

    
    fun buildRecentSearch(history: MutableList<Pair<String, Long>>, query: String, timestamp: Long): List<Pair<String, Long>> {
        history.add(Pair(query, timestamp))
        val deduped = history.distinctBy { it.first } 
        return deduped.takeLast(50)
        
    }

    
    fun buildSearchHistory(entries: MutableList<String>, newEntry: String, maxSize: Int): List<String> {
        entries.add(newEntry)
        if (entries.size > maxSize) {
            entries.removeAt(entries.size - 1) 
        }
        return entries.toList()
        
    }

    
    fun rewriteQuery(query: String, abbreviations: Map<String, String>): String {
        var result = query
        for ((abbr, full) in abbreviations) {
            result = result.replace(abbr, full)
            
            // also replaces within words: "task8s" would become "tasKubernetes"
        }
        return result
    }

    
    fun optimizeQuery(terms: List<String>): List<String> {
        return terms.toSet().toList()
        
        // or toList().distinct() which preserves first-occurrence order
        // Also, some duplicates may be intentional (phrase repetition for emphasis scoring)
    }
}
