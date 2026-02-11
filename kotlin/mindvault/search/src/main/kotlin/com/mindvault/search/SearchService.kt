package com.mindvault.search

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.produce
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.jetbrains.exposed.sql.*
import org.jetbrains.exposed.sql.SqlExpressionBuilder.eq
import org.jetbrains.exposed.sql.SqlExpressionBuilder.like
import org.jetbrains.exposed.sql.transactions.transaction
import java.sql.DriverManager
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong



//   1. This file (SearchService.kt): Change @SerialName("document") on GraphNodeResult to @SerialName("graph_node")
//   2. GraphService.kt: Update formatResult() to handle the new discriminator in deserialization
//   3. Any persisted JSON data with type="document" for GraphNodeResult must be migrated
// Fixing only one location will cause deserialization failures at runtime.
@Serializable
sealed class SearchResult {
    abstract val score: Double

    @Serializable
    @SerialName("document") 
    data class DocumentResult(val docId: String, override val score: Double, val snippet: String) : SearchResult()

    @Serializable
    @SerialName("document") 
    data class GraphNodeResult(val nodeId: String, override val score: Double, val label: String) : SearchResult()
}


@DslMarker
annotation class SearchDsl

class SearchQueryBuilder {
    var query: String = ""
    var limit: Int = 20
    var offset: Int = 0
    private val filters = mutableListOf<String>()

    
    fun filter(block: FilterBuilder.() -> Unit) {
        val builder = FilterBuilder()
        builder.block()
        filters.addAll(builder.build())
    }

    fun build(): SearchQuery = SearchQuery(query, limit, offset, filters)
}

class FilterBuilder {
    private val conditions = mutableListOf<String>()
    fun field(name: String, value: String) { conditions.add("$name=$value") }
    
    // because there is no @DslMarker to restrict scope
    fun build(): List<String> = conditions
}

data class SearchQuery(val query: String, val limit: Int, val offset: Int, val filters: List<String>)

object SearchIndex : Table("search_index") {
    val id = varchar("id", 64)
    val content = text("content")
    val documentId = varchar("document_id", 64)
    val score = double("score")
    override val primaryKey = PrimaryKey(id)
}

class SearchService {

    private val cache = ConcurrentHashMap<String, List<SearchResult>>()
    private val cacheHits = AtomicLong(0)
    private val json = Json { classDiscriminator = "type" }

    
    @OptIn(ExperimentalCoroutinesApi::class)
    fun CoroutineScope.searchStream(query: String) = produce<SearchResult> {
        val results = executeSearch(query)
        for (result in results) {
            send(result)
            
            // produce does handle cancellation, but the underlying DB resources opened
            // in executeSearch are not cleaned up because they're outside the produce block
        }
        // Channel is auto-closed, but executeSearch opened a JDBC connection that isn't closed
    }

    
    fun executeSearch(query: String): List<SearchResult> {
        val conn = DriverManager.getConnection("jdbc:postgresql://localhost:5432/mindvault")
        val stmt = conn.prepareStatement("SELECT id, content, score FROM search_index WHERE content ILIKE ?")
        stmt.setString(1, "%$query%")
        val rs = stmt.executeQuery()
        val results = mutableListOf<SearchResult>()
        while (rs.next()) {
            val id: String = rs.getString("id")           
            val content: String = rs.getString("content") 
            val score: Double = rs.getDouble("score")
            results.add(SearchResult.DocumentResult(id, score, content.take(200)))
        }
        
        return results
    }

    
    fun formatResult(result: SearchResult): String {
        
        // Kotlin compiler won't warn because this returns String, not used as expression
        // But logically it should handle all cases
        return when (result) {
            is SearchResult.DocumentResult -> "Doc[${result.docId}]: ${result.snippet}"
            
            else -> throw IllegalStateException("Unknown result type") // crashes instead of graceful handling
        }
    }

    
    fun buildSearchFilter(query: String, ownerId: String?): Op<Boolean> {
        return Op.build {
            
            // This evaluates as: (content LIKE query) OR (documentId = ownerId AND score > 0.5)
            // But intent is: (content LIKE query OR documentId = ownerId) AND score > 0.5
            SearchIndex.content like "%$query%" or
                    (SearchIndex.documentId eq (ownerId ?: "")) and
                    (SearchIndex.score greater 0.5)
        }
    }

    
    fun cachedSearch(query: SearchQuery): List<SearchResult> {
        val key = query.toString() 
        // If filters are reordered, same logical query gets different cache keys
        // Also: toString() output is not stable across Kotlin versions
        return cache.getOrPut(key) {
            executeSearch(query.query)
        }
    }

    
    
    // When A5 is active, the connection pool exhausts quickly, so only a few
    // concurrent requests complete. Fixing A5 (proper connection closing) allows
    // many more concurrent requests to succeed, revealing the stampede as N requests
    // all hit the database simultaneously instead of being blocked by pool exhaustion.
    fun searchWithCache(query: String): List<SearchResult> {
        val cached = cache[query]
        if (cached != null) {
            cacheHits.incrementAndGet()
            return cached
        }
        
        // Should use a lock or single-flight pattern to deduplicate
        val results = executeSearch(query)
        cache[query] = results
        return results
    }

    fun buildQuery(block: SearchQueryBuilder.() -> Unit): SearchQuery {
        val builder = SearchQueryBuilder()
        builder.block()
        return builder.build()
    }
}
