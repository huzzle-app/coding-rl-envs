package com.helixops.embeddings

import kotlinx.coroutines.*
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive

@Serializable
data class EmbeddingVector(val dimensions: Int, val values: List<Float>)

@Serializable
data class EmbeddingRequest(val documentId: String, val text: String, val model: String = "text-embedding-ada-002")

class EmbeddingService {

    
    lateinit var modelEndpoint: String  
    lateinit var apiKey: String         

    private val embeddingCache = mutableMapOf<String, EmbeddingVector>()
    private val json = Json { ignoreUnknownKeys = true }

    fun init(config: Map<String, String>) {
        
        config["model_endpoint"]?.let { modelEndpoint = it }
        config["api_key"]?.let { apiKey = it }
        // No validation that both were set
    }

    
    suspend fun batchEmbed(requests: List<EmbeddingRequest>): List<EmbeddingVector> = coroutineScope {
        val deferreds = requests.map { req ->
            async { 
                computeEmbedding(req) // But partial results are lost, and any side effects (DB writes) are not rolled back
            }
        }
        
        // No cleanup of partially-computed embeddings or allocated GPU memory
        deferreds.awaitAll()
    }

    
    fun parseEmbeddingResponse(responseJson: String): EmbeddingVector {
        val element = json.parseToJsonElement(responseJson)
        val dataArray = element.jsonArray 
        
        val values = dataArray.map { it.jsonPrimitive.content.toFloat() }
        return EmbeddingVector(values.size, values)
    }

    
    suspend fun embedDocumentTree(rootId: String, depth: Int = 0): List<EmbeddingVector> {
        val doc = fetchDocument(rootId)
        val embedding = computeEmbedding(EmbeddingRequest(rootId, doc))

        val children = getChildDocuments(rootId)
        
        // Deep document trees (1000+ levels) cause StackOverflowError
        // suspend doesn't help here because each recursive call still adds a stack frame
        val childEmbeddings = children.flatMap { childId ->
            embedDocumentTree(childId, depth + 1) 
        }

        return listOf(embedding) + childEmbeddings
    }

    fun cosineSimilarity(a: EmbeddingVector, b: EmbeddingVector): Float {
        require(a.dimensions == b.dimensions) { "Dimension mismatch: ${a.dimensions} vs ${b.dimensions}" }
        var dotProduct = 0f
        var normA = 0f
        var normB = 0f
        for (i in a.values.indices) {
            dotProduct += a.values[i] * b.values[i]
            normA += a.values[i] * a.values[i]
            normB += b.values[i] * b.values[i]
        }
        return dotProduct / (Math.sqrt(normA.toDouble()).toFloat() * Math.sqrt(normB.toDouble()).toFloat())
    }

    fun findSimilar(query: EmbeddingVector, topK: Int = 10): List<Pair<String, Float>> {
        return embeddingCache.entries
            .map { (id, vec) -> id to cosineSimilarity(query, vec) }
            .sortedByDescending { it.second }
            .take(topK)
    }

    private suspend fun computeEmbedding(request: EmbeddingRequest): EmbeddingVector {
        delay(50) // simulate API call latency
        
        println("Computing embedding via $modelEndpoint for ${request.documentId}")
        val dims = 1536
        val values = List(dims) { (Math.random() * 2 - 1).toFloat() }
        val embedding = EmbeddingVector(dims, values)
        embeddingCache[request.documentId] = embedding
        return embedding
    }

    private suspend fun fetchDocument(id: String): String {
        delay(10)
        return "Document content for $id"
    }

    private suspend fun getChildDocuments(parentId: String): List<String> {
        delay(5)
        return if (parentId.length < 20) listOf("$parentId/child1", "$parentId/child2") else emptyList()
    }
}
