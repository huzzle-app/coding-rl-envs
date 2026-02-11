package com.helixops.search

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.produce
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue
import kotlin.test.assertFailsWith

/**
 * Tests for the search module: indexing, querying, ranking, and bug-specific scenarios.
 *
 * Bug-specific tests:
 *   A5 - produce Channel leak: DB resources not closed when consumer cancels
 *   B2 - JDBC platform types: getString() returns String!, NPE on NULL columns
 *   C3 - Sealed class discriminator collision: two subclasses share same @SerialName
 *   E3 - Op.build precedence: AND/OR without explicit grouping yields wrong SQL
 *   F2 - Discriminator collision: polymorphic serialization fails on ambiguous type
 *   H1 - toString() used as cache key: not stable or unique
 *   H2 - Cache stampede: no locking on concurrent cache misses
 *   K1 - @DslMarker scope leak: inner lambda can access outer receiver
 */
class SearchTests {

    // =========================================================================
    // A5: produce Channel leak
    // =========================================================================

    @Test
    fun test_produce_channel_consumed() = runTest {
        
        // are not cleaned up when the channel is closed or consumer cancels.
        val service = SearchStreamService()
        val results = mutableListOf<String>()

        val channel = service.searchStream(this, "test query")
        // Consume only first result, then cancel
        results.add(channel.receive())
        channel.cancel()

        assertTrue(
            service.resourcesClosed,
            "Database resources should be closed when channel is cancelled"
        )
    }

    @Test
    fun test_no_producer_leak() = runTest {
        
        val service = SearchStreamService()
        val channel = service.searchStream(this, "full query")
        val results = mutableListOf<String>()
        for (item in channel) {
            results.add(item)
        }

        assertTrue(
            service.resourcesClosed,
            "JDBC connection should be closed after produce completes"
        )
        assertTrue(results.isNotEmpty(), "Should have received search results")
    }

    // =========================================================================
    // B2: JDBC platform types
    // =========================================================================

    @Test
    fun test_jdbc_result_null_safe() {
        
        // is NULL, assigning to String (non-null) causes NPE.
        val executor = JdbcSearchExecutor()
        val results = executor.executeSearch(nullableContent = true)
        // Should handle null gracefully
        assertNotNull(results, "Search should not crash on NULL column values")
        assertTrue(
            results.all { it.snippet.isNotEmpty() || it.snippet == "" },
            "Null JDBC content should be handled, not cause NPE"
        )
    }

    @Test
    fun test_platform_type_cast_safe() {
        
        val executor = JdbcSearchExecutor()
        val results = executor.executeSearch(nullableId = true)
        assertNotNull(results, "Should handle null ID from JDBC without NPE")
        assertTrue(
            results.all { it.docId.isNotEmpty() },
            "Null IDs from JDBC should be filtered or given defaults"
        )
    }

    // =========================================================================
    // C3: Sealed discriminator collision
    // =========================================================================

    @Test
    fun test_query_node_all_branches() {
        
        // This causes serialization to fail or produce ambiguous output.
        val serializer = SearchResultSerializer()
        val docResult = SearchResultFixture.DocumentResult("d1", 0.95, "snippet here")
        val graphResult = SearchResultFixture.GraphNodeResult("n1", 0.80, "label here")

        val docJson = serializer.serialize(docResult)
        val graphJson = serializer.serialize(graphResult)

        assertNotEquals(
            docJson,
            graphJson,
            "DocumentResult and GraphNodeResult should have different serialized discriminators"
        )
    }

    @Test
    fun test_phrase_query_handled() {
        
        val serializer = SearchResultSerializer()
        val results = listOf(
            SearchResultFixture.DocumentResult("d1", 0.9, "doc snippet"),
            SearchResultFixture.GraphNodeResult("n1", 0.8, "graph label")
        )
        for (result in results) {
            val json = serializer.serialize(result)
            val restored = serializer.deserialize(json)
            assertEquals(
                result::class,
                restored::class,
                "Deserialized type should match original for ${result::class.simpleName}"
            )
        }
    }

    // =========================================================================
    // E3: Op.build precedence
    // =========================================================================

    @Test
    fun test_op_build_precedence() {
        
        // causes wrong SQL: (A OR B AND C) instead of intended ((A OR B) AND C)
        val builder = SearchFilterBuilder()
        val sql = builder.buildFilter(query = "kotlin", ownerId = "owner1")

        // The generated SQL should have correct grouping
        assertTrue(
            sql.contains("(") && sql.contains(")"),
            "Filter should use explicit parentheses to ensure correct AND/OR precedence"
        )
    }

    @Test
    fun test_query_correct_parentheses() {
        
        // resulting in unexpected query behavior
        val builder = SearchFilterBuilder()
        val sql = builder.buildFilter(query = "test", ownerId = "user1")

        // Correct: (content LIKE '%test%' OR document_id = 'user1') AND score > 0.5
        
        val orIndex = sql.indexOf("OR")
        val andIndex = sql.indexOf("AND")
        if (orIndex >= 0 && andIndex >= 0) {
            // Check that the OR clause is properly grouped
            val beforeOr = sql.substring(0, orIndex)
            assertTrue(
                beforeOr.contains("("),
                "OR clause should be inside parentheses for correct precedence"
            )
        }
    }

    // =========================================================================
    // F2: Discriminator collision (related to C3)
    // =========================================================================

    @Test
    fun test_discriminator_no_collision() {
        
        val serializer = SearchResultSerializer()
        val docResult = SearchResultFixture.DocumentResult("d1", 0.9, "snippet")
        val graphResult = SearchResultFixture.GraphNodeResult("n1", 0.8, "label")

        val docDiscriminator = serializer.getDiscriminator(docResult)
        val graphDiscriminator = serializer.getDiscriminator(graphResult)

        assertNotEquals(
            docDiscriminator,
            graphDiscriminator,
            "Each sealed subclass must have a unique discriminator, but both are: '$docDiscriminator'"
        )
    }

    @Test
    fun test_type_field_distinct() {
        
        val serializer = SearchResultSerializer()
        val allTypes = listOf(
            SearchResultFixture.DocumentResult("d1", 0.9, "s"),
            SearchResultFixture.GraphNodeResult("n1", 0.8, "l")
        )
        val discriminators = allTypes.map { serializer.getDiscriminator(it) }.toSet()
        assertEquals(
            allTypes.size,
            discriminators.size,
            "All sealed subclass discriminators must be unique"
        )
    }

    // =========================================================================
    // H1: toString() used as cache key
    // =========================================================================

    @Test
    fun test_cache_key_stable() {
        
        // but logically equivalent, different keys are produced.
        val query1 = SearchQueryFixture("kotlin", 20, 0, listOf("type=doc", "lang=kt"))
        val query2 = SearchQueryFixture("kotlin", 20, 0, listOf("lang=kt", "type=doc"))

        val cache = CacheService()
        val key1 = cache.computeCacheKey(query1)
        val key2 = cache.computeCacheKey(query2)

        assertEquals(
            key1,
            key2,
            "Logically equivalent queries with reordered filters should produce the same cache key"
        )
    }

    @Test
    fun test_no_timestamp_in_key() {
        
        val cache = CacheService()
        assertFalse(
            cache.usesToStringForKey,
            "Cache key strategy should NOT rely on toString() which is unstable and order-dependent"
        )
    }

    // =========================================================================
    // H2: Cache stampede
    // =========================================================================

    @Test
    fun test_cache_stampede_prevented() = runTest {
        
        // execute the expensive query. Only one should compute; others should wait.
        val cache = StampedeCache()
        val concurrentRequests = 10
        val jobs = (1..concurrentRequests).map {
            async(Dispatchers.Default) {
                cache.searchWithCache("stampede-query")
            }
        }
        jobs.awaitAll()

        assertTrue(
            cache.computeCount.get() <= 2,
            "Only 1 (or at most 2 due to races) query should execute for concurrent misses, but got ${cache.computeCount.get()}"
        )
    }

    @Test
    fun test_single_flight_pattern() = runTest {
        
        val cache = StampedeCache()
        // First call: miss -> compute
        cache.searchWithCache("query1")
        val afterFirst = cache.computeCount.get()
        assertEquals(1, afterFirst, "First miss should trigger exactly 1 computation")

        // Second call: hit -> no compute
        cache.searchWithCache("query1")
        val afterSecond = cache.computeCount.get()
        assertEquals(1, afterSecond, "Second call should be a cache hit with 0 additional computes")
    }

    // =========================================================================
    // K1: @DslMarker scope leak
    // =========================================================================

    @Test
    fun test_dsl_scope_restricted() {
        
        // the inner filter {} lambda can access outer SearchQueryBuilder members
        val builder = SearchQueryBuilderFixture()
        builder.query = "initial"
        builder.filter {
            field("type", "document")
            
            // query = "overwritten from inner scope"  <-- scope leak
        }
        val result = builder.build()

        assertEquals(
            "initial",
            result.query,
            "Inner filter block should not be able to modify outer builder's query field"
        )
    }

    @Test
    fun test_no_outer_scope_access() {
        
        val builder = SearchQueryBuilderFixture()
        builder.query = "search term"
        builder.limit = 50

        builder.filter {
            field("category", "books")
            
        }

        val result = builder.build()
        assertEquals(50, result.limit, "Inner filter should not be able to change outer builder's limit")
    }

    // =========================================================================
    // Baseline: Search indexing, querying, ranking
    // =========================================================================

    @Test
    fun test_index_document() {
        val index = SearchIndex()
        index.addDocument("d1", "Kotlin coroutines guide")
        val results = index.search("kotlin")
        assertTrue(results.isNotEmpty(), "Should find indexed document by keyword")
    }

    @Test
    fun test_search_empty_index() {
        val index = SearchIndex()
        val results = index.search("anything")
        assertTrue(results.isEmpty(), "Empty index should return no results")
    }

    @Test
    fun test_search_case_insensitive() {
        val index = SearchIndex()
        index.addDocument("d1", "Kotlin Programming")
        val results = index.search("kotlin")
        assertTrue(results.isNotEmpty(), "Search should be case-insensitive")
    }

    @Test
    fun test_search_returns_scored_results() {
        val index = SearchIndex()
        index.addDocument("d1", "Kotlin coroutines")
        index.addDocument("d2", "Java streams")
        val results = index.search("kotlin")
        assertTrue(results.all { it.score > 0.0 }, "All results should have a positive score")
    }

    @Test
    fun test_search_respects_limit() {
        val index = SearchIndex()
        for (i in 1..20) {
            index.addDocument("d$i", "Kotlin document number $i")
        }
        val results = index.search("kotlin", limit = 5)
        assertEquals(5, results.size, "Search should respect the limit parameter")
    }

    @Test
    fun test_search_results_sorted_by_score() {
        val index = SearchIndex()
        index.addDocument("d1", "kotlin")
        index.addDocument("d2", "kotlin kotlin kotlin") // more relevant
        index.addDocument("d3", "kotlin kotlin")
        val results = index.search("kotlin")
        for (i in 0 until results.size - 1) {
            assertTrue(
                results[i].score >= results[i + 1].score,
                "Results should be sorted by descending score"
            )
        }
    }

    @Test
    fun test_remove_document_from_index() {
        val index = SearchIndex()
        index.addDocument("d1", "Kotlin guide")
        index.removeDocument("d1")
        val results = index.search("kotlin")
        assertTrue(results.isEmpty(), "Removed document should not appear in search results")
    }

    @Test
    fun test_update_indexed_document() {
        val index = SearchIndex()
        index.addDocument("d1", "Old content about Java")
        index.addDocument("d1", "New content about Kotlin")
        val javaResults = index.search("java")
        val kotlinResults = index.search("kotlin")
        assertTrue(javaResults.isEmpty(), "Old content should not be searchable after update")
        assertTrue(kotlinResults.isNotEmpty(), "New content should be searchable after update")
    }

    @Test
    fun test_multi_word_search() {
        val index = SearchIndex()
        index.addDocument("d1", "Kotlin coroutines are powerful for async programming")
        val results = index.search("coroutines async")
        assertTrue(results.isNotEmpty(), "Multi-word search should return matching documents")
    }

    @Test
    fun test_search_no_match() {
        val index = SearchIndex()
        index.addDocument("d1", "Kotlin programming")
        val results = index.search("python")
        assertTrue(results.isEmpty(), "Search should return empty for non-matching query")
    }

    @Test
    fun test_search_multiple_documents() {
        val index = SearchIndex()
        index.addDocument("d1", "Kotlin coroutines")
        index.addDocument("d2", "Kotlin flows")
        index.addDocument("d3", "Kotlin channels")
        val results = index.search("kotlin")
        assertEquals(3, results.size, "All three documents should match 'kotlin'")
    }

    @Test
    fun test_index_overwrite_document() {
        val index = SearchIndex()
        index.addDocument("d1", "First version")
        index.addDocument("d1", "Second version")
        val results = index.search("first")
        assertTrue(results.isEmpty(), "Overwritten content should not match old keywords")
    }

    @Test
    fun test_search_partial_word() {
        val index = SearchIndex()
        index.addDocument("d1", "Kotlin programming language")
        val results = index.search("program")
        assertTrue(results.isNotEmpty(), "Partial word match should return results")
    }

    @Test
    fun test_empty_query_returns_nothing() {
        val index = SearchIndex()
        index.addDocument("d1", "Some content")
        val results = index.search("")
        // Empty query should match or return empty depending on implementation
        // We test that it doesn't throw
        assertNotNull(results, "Empty query should not throw")
    }

    @Test
    fun test_search_default_limit() {
        val index = SearchIndex()
        for (i in 1..25) {
            index.addDocument("d$i", "common keyword document $i")
        }
        val results = index.search("common")
        assertTrue(results.size <= 10, "Default search limit should be 10 or less, got ${results.size}")
    }

    @Test
    fun test_remove_nonexistent_document() {
        val index = SearchIndex()
        index.addDocument("d1", "Existing document")
        index.removeDocument("nonexistent")
        val results = index.search("existing")
        assertTrue(results.isNotEmpty(), "Removing nonexistent doc should not affect existing docs")
    }

    @Test
    fun test_search_special_characters() {
        val index = SearchIndex()
        index.addDocument("d1", "C++ programming language")
        val results = index.search("c++")
        assertNotNull(results, "Search with special characters should not throw")
    }

    @Test
    fun test_search_result_contains_doc_id() {
        val index = SearchIndex()
        index.addDocument("my-doc-123", "Kotlin programming")
        val results = index.search("kotlin")
        assertTrue(results.isNotEmpty())
        assertEquals("my-doc-123", results[0].docId, "Result should contain the correct document ID")
    }

    @Test
    fun test_search_limit_zero() {
        val index = SearchIndex()
        index.addDocument("d1", "Test content")
        val results = index.search("test", limit = 0)
        assertTrue(results.isEmpty(), "Limit 0 should return empty results")
    }

    @Test
    fun test_search_after_multiple_updates() {
        val index = SearchIndex()
        index.addDocument("d1", "alpha")
        index.addDocument("d1", "beta")
        index.addDocument("d1", "gamma")
        val alphaResults = index.search("alpha")
        val gammaResults = index.search("gamma")
        assertTrue(alphaResults.isEmpty(), "Old content after multiple updates should not be found")
        assertTrue(gammaResults.isNotEmpty(), "Latest content should be searchable")
    }

    @Test
    fun test_search_score_positive() {
        val index = SearchIndex()
        index.addDocument("d1", "kotlin coroutines")
        val results = index.search("kotlin")
        assertTrue(results.isNotEmpty())
        assertTrue(results[0].score > 0.0, "Score should be positive for matching documents")
    }

    @Test
    fun test_search_multiple_words_all_match() {
        val index = SearchIndex()
        index.addDocument("d1", "Kotlin is a modern programming language for the JVM")
        index.addDocument("d2", "Java is also a JVM language")
        val results = index.search("kotlin modern")
        assertTrue(results.isNotEmpty(), "Multi-word search should match documents with any word")
        assertEquals("d1", results[0].docId, "Document with both words should rank first")
    }

    @Test
    fun test_search_single_character_query() {
        val index = SearchIndex()
        index.addDocument("d1", "A brief note")
        val results = index.search("a")
        assertNotNull(results, "Single character search should not throw")
    }

    @Test
    fun test_index_large_content() {
        val index = SearchIndex()
        val largeContent = "word ".repeat(10000)
        index.addDocument("d1", largeContent)
        val results = index.search("word")
        assertTrue(results.isNotEmpty(), "Should find documents with large content")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    // A5: produce channel with resource leak
    class SearchStreamService {
        var resourcesClosed = false

        @OptIn(ExperimentalCoroutinesApi::class)
        fun searchStream(scope: CoroutineScope, query: String) = scope.produce<String> {
            
            val connection = openJdbcConnection()
            try {
                val results = listOf("result1", "result2", "result3")
                for (r in results) {
                    send(r)
                }
            } finally {
                
                // Resource leak: connection is never properly closed
                // connection.close() // missing!
                resourcesClosed = false 
            }
        }

        private fun openJdbcConnection(): Any = Object()
    }

    // B2: JDBC platform type stubs
    data class SearchResultDto(val docId: String, val score: Double, val snippet: String)

    class JdbcSearchExecutor {
        fun executeSearch(nullableContent: Boolean = false, nullableId: Boolean = false): List<SearchResultDto> {
            
            if (nullableId) {
                val id: String = null as String 
                return listOf(SearchResultDto(id, 0.5, "snippet"))
            }
            if (nullableContent) {
                val content: String = null as String 
                return listOf(SearchResultDto("d1", 0.5, content))
            }
            return listOf(SearchResultDto("d1", 0.9, "valid snippet"))
        }
    }

    // C3 / F2: Sealed class with discriminator collision
    sealed class SearchResultFixture {
        abstract val score: Double

        data class DocumentResult(val docId: String, override val score: Double, val snippet: String) : SearchResultFixture()
        data class GraphNodeResult(val nodeId: String, override val score: Double, val label: String) : SearchResultFixture()
    }

    class SearchResultSerializer {
        
        private val discriminatorMap = mapOf(
            SearchResultFixture.DocumentResult::class to "document",
            SearchResultFixture.GraphNodeResult::class to "document" 
        )

        fun getDiscriminator(result: SearchResultFixture): String {
            return discriminatorMap[result::class] ?: "unknown"
        }

        fun serialize(result: SearchResultFixture): String {
            val discriminator = getDiscriminator(result)
            return when (result) {
                is SearchResultFixture.DocumentResult ->
                    """{"type":"$discriminator","docId":"${result.docId}","score":${result.score},"snippet":"${result.snippet}"}"""
                is SearchResultFixture.GraphNodeResult ->
                    """{"type":"$discriminator","nodeId":"${result.nodeId}","score":${result.score},"label":"${result.label}"}"""
            }
        }

        fun deserialize(json: String): SearchResultFixture {
            
            return if (json.contains("docId")) {
                SearchResultFixture.DocumentResult("d1", 0.0, "stub")
            } else {
                SearchResultFixture.GraphNodeResult("n1", 0.0, "stub")
            }
        }
    }

    // E3: Op.build precedence
    class SearchFilterBuilder {
        fun buildFilter(query: String, ownerId: String?): String {
            
            // SQL: content LIKE '%query%' OR document_id = 'ownerId' AND score > 0.5
            // Should be: (content LIKE '%query%' OR document_id = 'ownerId') AND score > 0.5
            return "content LIKE '%$query%' OR document_id = '${ownerId ?: ""}' AND score > 0.5"
            
        }
    }

    // H1: toString cache key
    data class SearchQueryFixture(val query: String, val limit: Int, val offset: Int, val filters: List<String>)

    class CacheService {
        var usesToStringForKey = true 

        fun computeCacheKey(query: SearchQueryFixture): String {
            
            return query.toString() 
        }
    }

    // H2: Cache stampede
    class StampedeCache {
        val computeCount = AtomicInteger(0)
        private val cache = ConcurrentHashMap<String, List<String>>()

        fun searchWithCache(query: String): List<String> {
            val cached = cache[query]
            if (cached != null) return cached

            
            computeCount.incrementAndGet()
            Thread.sleep(50) // simulate expensive query
            val results = listOf("result1", "result2")
            cache[query] = results
            return results
        }
    }

    // K1: DSL marker scope leak
    class SearchQueryBuilderFixture {
        var query: String = ""
        var limit: Int = 20
        var offset: Int = 0
        private val filters = mutableListOf<String>()

        
        // can access `query` and `limit` from outer SearchQueryBuilderFixture
        fun filter(block: FilterBuilderFixture.() -> Unit) {
            val builder = FilterBuilderFixture()
            builder.block()
            filters.addAll(builder.build())
        }

        fun build(): SearchQueryFixture = SearchQueryFixture(query, limit, offset, filters)
    }

    class FilterBuilderFixture {
        private val conditions = mutableListOf<String>()
        fun field(name: String, value: String) { conditions.add("$name=$value") }
        fun build(): List<String> = conditions
    }

    // Baseline: Search index
    data class ScoredResult(val docId: String, val score: Double)

    class SearchIndex {
        private val documents = mutableMapOf<String, String>()

        fun addDocument(id: String, content: String) {
            documents[id] = content
        }

        fun removeDocument(id: String) {
            documents.remove(id)
        }

        fun search(query: String, limit: Int = 10): List<ScoredResult> {
            val queryWords = query.lowercase().split(" ")
            return documents
                .filter { (_, content) ->
                    queryWords.any { word -> content.lowercase().contains(word) }
                }
                .map { (id, content) ->
                    val matchCount = queryWords.count { word -> content.lowercase().contains(word) }
                    val wordFrequency = queryWords.sumOf { word ->
                        content.lowercase().split(word).size - 1
                    }
                    ScoredResult(id, matchCount.toDouble() + wordFrequency * 0.1)
                }
                .sortedByDescending { it.score }
                .take(limit)
        }
    }
}
