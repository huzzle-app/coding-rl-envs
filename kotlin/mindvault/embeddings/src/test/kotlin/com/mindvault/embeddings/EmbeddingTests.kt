package com.mindvault.embeddings

import kotlinx.coroutines.*
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertFailsWith

/**
 * Tests for EmbeddingService: vector computation, similarity, batch processing.
 *
 * Bug-specific tests:
 *   A7 - awaitAll cancellation: partial failure leaves side effects unrolled
 *   B4 - lateinit: accessing uninitialized property throws UninitializedPropertyAccessException
 *   F5 - mixed-type list: JSON root is object wrapping array, not bare array
 *   K3 - suspend recursion: unbounded recursive suspend causes StackOverflow
 */
class EmbeddingTests {

    // =========================================================================
    // A7: awaitAll cancellation -- partial failures not cleaned up
    // =========================================================================

    @Test
    fun test_await_all_partial_failure() = runTest {
        
        // not clean up side effects (e.g., partial embeddings written to cache).
        val service = BatchEmbedServiceStub()
        val requests = listOf("doc1", "doc2", "FAIL", "doc4")

        val result = service.batchEmbedSafe(requests)
        // After partial failure, previously-written side effects should be rolled back
        assertTrue(
            result.cleanedUp,
            "Partial results should be cleaned up after awaitAll cancellation"
        )
    }

    @Test
    fun test_supervisor_scope_independent() = runTest {
        
        // the caller should handle partial failure gracefully, not lose data silently.
        val service = BatchEmbedServiceStub()
        val requests = listOf("doc1", "FAIL", "doc3")

        val result = service.batchEmbedSafe(requests)
        assertTrue(
            result.partialResultsAvailable,
            "Successfully computed embeddings before the failure should be recoverable"
        )
    }

    // =========================================================================
    // B4: lateinit not initialized before access
    // =========================================================================

    @Test
    fun test_lateinit_initialized() {
        
        // be called, or config may lack the required keys.
        val service = EmbeddingServiceStub()
        // Service used without calling init() -- should fail gracefully, not crash
        val initialized = service.isFullyInitialized()
        assertTrue(
            initialized,
            "Service should validate that all lateinit properties are initialized before use"
        )
    }

    @Test
    fun test_meaningful_init_error() {
        
        val service = EmbeddingServiceStub()
        
        val safe = service.canComputeWithoutInit()
        assertTrue(
            safe,
            "Service should not throw UninitializedPropertyAccessException when init() is skipped"
        )
    }

    // =========================================================================
    // F5: mixed-type list -- JSON response structure mismatch
    // =========================================================================

    @Test
    fun test_mixed_type_serialization() {
        
        // but parseEmbeddingResponse calls element.jsonArray on the root object.
        val json = """{"data": [0.1, 0.2, 0.3]}"""
        val parser = EmbeddingParserStub()

        val values = parser.parseEmbedding(json)
        assertNotNull(values, "Should successfully parse wrapped JSON response")
        assertEquals(3, values.size, "Should extract 3 embedding values from data array")
    }

    @Test
    fun test_heterogeneous_list() {
        
        // calling jsonArray on a JsonObject throws.
        val json = """{"data": [0.5, -0.3, 0.8], "model": "ada-002", "usage": {"tokens": 10}}"""
        val parser = EmbeddingParserStub()

        val values = parser.parseEmbedding(json)
        assertNotNull(values, "Should handle mixed-type JSON without crashing")
        assertEquals(3, values.size, "Should parse exactly the embedding values from 'data' field")
    }

    // =========================================================================
    // K3: suspend recursion -- no depth limit causes StackOverflow
    // =========================================================================

    @Test
    fun test_retry_iterative() = runTest {
        
        // Deep document hierarchies cause StackOverflowError.
        val service = RecursiveEmbedStub()
        val maxDepth = service.getMaxRecursionDepth()

        assertTrue(
            maxDepth in 1..100,
            "Recursion should be bounded to a reasonable depth, but was $maxDepth"
        )
    }

    @Test
    fun test_no_stack_overflow_on_retry() = runTest {
        
        val service = RecursiveEmbedStub()
        val result = service.embedDeepTree(depth = 500)

        assertTrue(
            result.completed,
            "Deep tree embedding should complete without StackOverflowError"
        )
        assertFalse(
            result.stackOverflow,
            "Should not throw StackOverflowError on deep hierarchies"
        )
    }

    // =========================================================================
    // Baseline: embedding computation
    // =========================================================================

    @Test
    fun test_cosine_similarity_identical() {
        val a = listOf(1.0f, 0.0f, 0.0f)
        val b = listOf(1.0f, 0.0f, 0.0f)
        val sim = cosineSimilarity(a, b)
        assertEquals(1.0f, sim, 0.001f, "Identical vectors should have similarity 1.0")
    }

    @Test
    fun test_cosine_similarity_orthogonal() {
        val a = listOf(1.0f, 0.0f, 0.0f)
        val b = listOf(0.0f, 1.0f, 0.0f)
        val sim = cosineSimilarity(a, b)
        assertEquals(0.0f, sim, 0.001f, "Orthogonal vectors should have similarity 0.0")
    }

    @Test
    fun test_cosine_similarity_opposite() {
        val a = listOf(1.0f, 0.0f)
        val b = listOf(-1.0f, 0.0f)
        val sim = cosineSimilarity(a, b)
        assertEquals(-1.0f, sim, 0.001f, "Opposite vectors should have similarity -1.0")
    }

    @Test
    fun test_embedding_vector_dimensions() {
        val vec = EmbeddingVectorLocal(dimensions = 384, values = List(384) { 0.1f })
        assertEquals(384, vec.dimensions)
        assertEquals(384, vec.values.size)
    }

    @Test
    fun test_embedding_cache_stores_results() = runTest {
        val cache = EmbeddingCacheStub()
        cache.store("doc1", listOf(0.1f, 0.2f, 0.3f))
        val retrieved = cache.get("doc1")
        assertNotNull(retrieved, "Cached embedding should be retrievable")
        assertEquals(3, retrieved.size)
    }

    @Test
    fun test_embedding_cache_miss() = runTest {
        val cache = EmbeddingCacheStub()
        val result = cache.get("nonexistent")
        assertEquals(null, result, "Cache miss should return null")
    }

    @Test
    fun test_find_similar_top_k() {
        val cache = EmbeddingCacheStub()
        cache.store("a", listOf(1.0f, 0.0f, 0.0f))
        cache.store("b", listOf(0.9f, 0.1f, 0.0f))
        cache.store("c", listOf(0.0f, 1.0f, 0.0f))
        val query = listOf(1.0f, 0.0f, 0.0f)
        val results = cache.findSimilar(query, topK = 2)
        assertEquals(2, results.size, "Should return top 2 results")
        assertEquals("a", results[0].first, "Most similar should be 'a'")
    }

    @Test
    fun test_batch_embed_all_succeed() = runTest {
        val service = BatchEmbedServiceStub()
        val requests = listOf("doc1", "doc2", "doc3")
        val result = service.batchEmbedSafe(requests)
        assertEquals(3, result.successCount, "All 3 embeddings should succeed")
    }

    @Test
    fun test_embedding_request_default_model() {
        val req = EmbeddingRequestLocal("doc1", "hello world")
        assertEquals("text-embedding-ada-002", req.model, "Default model should be ada-002")
    }

    @Test
    fun test_embedding_vector_values_in_range() {
        val values = List(128) { ((it % 20) / 10.0f) - 1.0f }
        val vec = EmbeddingVectorLocal(128, values)
        assertTrue(vec.values.all { it in -1.0f..1.0f }, "Embedding values should be in [-1, 1]")
    }

    @Test
    fun test_cosine_similarity_dimension_mismatch() {
        val a = listOf(1.0f, 0.0f)
        val b = listOf(1.0f, 0.0f, 0.0f)
        assertFailsWith<IllegalArgumentException> {
            cosineSimilarity(a, b)
        }
    }

    @Test
    fun test_find_similar_empty_cache() {
        val cache = EmbeddingCacheStub()
        val results = cache.findSimilar(listOf(1.0f, 0.0f), topK = 5)
        assertTrue(results.isEmpty(), "Empty cache should return empty results")
    }

    @Test
    fun test_embedding_cache_overwrite() {
        val cache = EmbeddingCacheStub()
        cache.store("doc1", listOf(1.0f, 0.0f))
        cache.store("doc1", listOf(0.0f, 1.0f))
        val retrieved = cache.get("doc1")
        assertNotNull(retrieved)
        assertEquals(0.0f, retrieved[0], 0.001f, "Overwritten cache entry should reflect new value")
    }

    @Test
    fun test_cosine_similarity_range() {
        val a = listOf(0.5f, 0.3f, -0.2f)
        val b = listOf(0.1f, -0.4f, 0.7f)
        val sim = cosineSimilarity(a, b)
        assertTrue(sim >= -1.0f && sim <= 1.0f, "Cosine similarity must be in [-1, 1]")
    }

    @Test
    fun test_cosine_similarity_normalized_vectors() {
        val a = listOf(0.6f, 0.8f)
        val b = listOf(0.8f, 0.6f)
        val sim = cosineSimilarity(a, b)
        assertTrue(sim > 0.9f, "Nearly aligned normalized vectors should have high similarity")
    }

    @Test
    fun test_embedding_vector_zero_dimensions() {
        val vec = EmbeddingVectorLocal(dimensions = 0, values = emptyList())
        assertEquals(0, vec.dimensions)
        assertTrue(vec.values.isEmpty(), "Zero-dimension vector should have empty values")
    }

    @Test
    fun test_embedding_cache_multiple_entries() {
        val cache = EmbeddingCacheStub()
        cache.store("doc1", listOf(1.0f, 0.0f))
        cache.store("doc2", listOf(0.0f, 1.0f))
        cache.store("doc3", listOf(0.5f, 0.5f))
        val d1 = cache.get("doc1")
        val d2 = cache.get("doc2")
        val d3 = cache.get("doc3")
        assertNotNull(d1)
        assertNotNull(d2)
        assertNotNull(d3)
        assertEquals(2, d1.size)
    }

    @Test
    fun test_find_similar_returns_sorted() {
        val cache = EmbeddingCacheStub()
        cache.store("a", listOf(1.0f, 0.0f, 0.0f))
        cache.store("b", listOf(0.5f, 0.5f, 0.0f))
        cache.store("c", listOf(0.0f, 0.0f, 1.0f))
        val query = listOf(1.0f, 0.0f, 0.0f)
        val results = cache.findSimilar(query, topK = 3)
        assertEquals(3, results.size)
        assertTrue(results[0].second >= results[1].second, "Results should be sorted by descending similarity")
        assertTrue(results[1].second >= results[2].second, "Results should be sorted by descending similarity")
    }

    @Test
    fun test_find_similar_top_k_exceeds_cache_size() {
        val cache = EmbeddingCacheStub()
        cache.store("only", listOf(1.0f, 0.0f))
        val results = cache.findSimilar(listOf(1.0f, 0.0f), topK = 10)
        assertEquals(1, results.size, "When topK exceeds cache size, return all available results")
    }

    @Test
    fun test_embedding_request_custom_model() {
        val req = EmbeddingRequestLocal("doc1", "text", model = "custom-model-v2")
        assertEquals("custom-model-v2", req.model, "Custom model name should be preserved")
    }

    @Test
    fun test_cosine_similarity_zero_vector() {
        val a = listOf(0.0f, 0.0f, 0.0f)
        val b = listOf(1.0f, 0.0f, 0.0f)
        val sim = cosineSimilarity(a, b)
        assertEquals(0.0f, sim, 0.001f, "Zero vector should have similarity 0 with any vector")
    }

    @Test
    fun test_batch_embed_empty_list() = runTest {
        val service = BatchEmbedServiceStub()
        val result = service.batchEmbedSafe(emptyList())
        assertEquals(0, result.successCount, "Empty request list should yield 0 successes")
    }

    @Test
    fun test_embedding_vector_large_dimension() {
        val values = List(1536) { 0.01f * it }
        val vec = EmbeddingVectorLocal(1536, values)
        assertEquals(1536, vec.dimensions)
        assertEquals(1536, vec.values.size)
    }

    @Test
    fun test_cosine_similarity_high_dimensional() {
        val dim = 512
        val a = List(dim) { 1.0f }
        val b = List(dim) { 1.0f }
        val sim = cosineSimilarity(a, b)
        assertEquals(1.0f, sim, 0.001f, "Identical high-dimensional vectors should have similarity 1.0")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    data class EmbeddingVectorLocal(val dimensions: Int, val values: List<Float>)
    data class EmbeddingRequestLocal(val documentId: String, val text: String, val model: String = "text-embedding-ada-002")

    data class BatchResult(
        val successCount: Int,
        val cleanedUp: Boolean,
        val partialResultsAvailable: Boolean
    )

    class BatchEmbedServiceStub {
        private val computed = mutableListOf<String>()

        suspend fun batchEmbedSafe(requests: List<String>): BatchResult {
            
            var failIndex = -1
            for ((i, req) in requests.withIndex()) {
                if (req == "FAIL") {
                    failIndex = i
                    break
                }
                computed.add(req)
            }
            return if (failIndex >= 0) {
                
                BatchResult(
                    successCount = computed.size,
                    cleanedUp = false,           
                    partialResultsAvailable = false 
                )
            } else {
                BatchResult(
                    successCount = requests.size,
                    cleanedUp = true,
                    partialResultsAvailable = true
                )
            }
        }
    }

    class EmbeddingServiceStub {
        
        private var modelEndpoint: String? = null
        private var apiKey: String? = null
        private var initCalled = false

        fun init(config: Map<String, String>) {
            config["model_endpoint"]?.let { modelEndpoint = it }
            config["api_key"]?.let { apiKey = it }
            initCalled = true
        }

        
        fun isFullyInitialized(): Boolean {
            return initCalled && modelEndpoint != null && apiKey != null
        }

        
        fun canComputeWithoutInit(): Boolean {
            
            return modelEndpoint != null // false when init() not called
        }
    }

    class EmbeddingParserStub {
        private val json = Json { ignoreUnknownKeys = true }

        fun parseEmbedding(responseJson: String): List<Float>? {
            return try {
                val element = json.parseToJsonElement(responseJson)
                
                val dataArray = element.jsonArray 
                dataArray.map { it.jsonPrimitive.float }
            } catch (e: IllegalArgumentException) {
                null 
            }
        }
    }

    data class DeepTreeResult(val completed: Boolean, val stackOverflow: Boolean, val nodesProcessed: Int)

    class RecursiveEmbedStub {
        
        fun getMaxRecursionDepth(): Int = Int.MAX_VALUE 

        suspend fun embedDeepTree(depth: Int): DeepTreeResult {
            
            return try {
                var count = 0
                fun recurse(level: Int) {
                    if (level >= depth) return
                    count++
                    recurse(level + 1) 
                }
                recurse(0)
                DeepTreeResult(completed = true, stackOverflow = false, nodesProcessed = count)
            } catch (e: StackOverflowError) {
                DeepTreeResult(completed = false, stackOverflow = true, nodesProcessed = 0) 
            }
        }
    }

    class EmbeddingCacheStub {
        private val cache = mutableMapOf<String, List<Float>>()

        fun store(id: String, values: List<Float>) {
            cache[id] = values
        }

        fun get(id: String): List<Float>? = cache[id]

        fun findSimilar(query: List<Float>, topK: Int): List<Pair<String, Float>> {
            return cache.entries
                .map { (id, vec) -> id to cosineSimilarity(query, vec) }
                .sortedByDescending { it.second }
                .take(topK)
        }
    }

    private fun cosineSimilarity(a: List<Float>, b: List<Float>): Float {
        require(a.size == b.size) { "Dimension mismatch" }
        var dot = 0f; var normA = 0f; var normB = 0f
        for (i in a.indices) {
            dot += a[i] * b[i]
            normA += a[i] * a[i]
            normB += b[i] * b[i]
        }
        val denom = Math.sqrt(normA.toDouble()).toFloat() * Math.sqrt(normB.toDouble()).toFloat()
        return if (denom == 0f) 0f else dot / denom
    }
}
