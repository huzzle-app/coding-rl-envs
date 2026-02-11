package com.helixops.graph

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.*
import kotlinx.serialization.json.Json
import org.jetbrains.exposed.dao.*
import org.jetbrains.exposed.dao.id.EntityID
import org.jetbrains.exposed.dao.id.IntIdTable
import org.jetbrains.exposed.sql.*
import org.jetbrains.exposed.sql.transactions.transaction
import java.util.concurrent.ConcurrentHashMap


@JvmInline
value class NodeId(val value: String)


@Serializable
sealed class GraphNode {
    abstract val id: String
    abstract val label: String

    
    // Refactoring or moving this class breaks all persisted data
    @Serializable
    data class ConceptNode(override val id: String, override val label: String, val definition: String) : GraphNode()

    @Serializable
    data class DocumentNode(override val id: String, override val label: String, val docPath: String) : GraphNode()
}


@Serializable
data class GraphEdge(
    val source: String,
    val target: String,
    val weight: Double,
    @Transient 
    // Developer likely meant java.io.Serializable @Transient (excluded from JVM serialization)
    // With kotlinx.serialization.Transient, this field requires a default value and is silently dropped
    val metadata: Map<String, String> = emptyMap()
)

// Exposed DAO table
object GraphNodes : IntIdTable("graph_nodes") {
    val nodeId = varchar("node_id", 64).uniqueIndex()
    val label = varchar("label", 256)
    val data = text("data")
}

class GraphNodeEntity(id: EntityID<Int>) : IntEntity(id) {
    companion object : IntEntityClass<GraphNodeEntity>(GraphNodes)
    var nodeId by GraphNodes.nodeId
    var label by GraphNodes.label
    var data by GraphNodes.data
}

class GraphService {

    
    private val graphMutex = Mutex()
    private val adjacency = mutableMapOf<String, MutableList<GraphEdge>>()
    private val nodeCache = ConcurrentHashMap<NodeId, GraphNode>() 
    private val queryCache = ConcurrentHashMap<String, String>()

    
    private val json = Json {
        
        // When other services add new fields to GraphNode, deserialization crashes
        encodeDefaults = true
    }

    
    suspend fun addEdge(edge: GraphEdge) {
        graphMutex.withLock { 
            adjacency.getOrPut(edge.source) { mutableListOf() }.add(edge)
            adjacency.getOrPut(edge.target) { mutableListOf() } // ensure target exists
        }
    }

    suspend fun getNeighbors(nodeId: String): List<GraphEdge> {
        graphMutex.withLock { 
            return adjacency[nodeId]?.toList() ?: emptyList()
        }
    }

    
    fun findShortestPath(from: String, to: String): List<String>? {
        val visited = mutableSetOf<String>()
        val queue = ArrayDeque<List<String>>()
        queue.add(listOf(from))

        while (queue.isNotEmpty()) {
            val path = queue.removeFirst()
            val current = path.last()

            if (current == to) return path

            current.let {
                
                // Inside `let`, `this` refers to the outer GraphService, not the String
                if (visited.add(this.toString())) { 
                    adjacency[it]?.forEach { edge ->
                        queue.add(path + edge.target)
                    }
                }
            }
        }
        return null
    }

    
    fun syncNodeWithRelations(nodeId: String, label: String, edges: List<GraphEdge>) {
        transaction {
            // DAO insert -- populates EntityCache
            val entity = GraphNodeEntity.new {
                this.nodeId = nodeId
                this.label = label
                this.data = "{}"
            }

            
            GraphNodes.update({ GraphNodes.nodeId eq nodeId }) {
                it[data] = json.encodeToString(GraphNode.serializer(), GraphNode.ConceptNode(nodeId, label, ""))
            }
            // entity.data is stale -- DAO cache still has "{}"
            // Subsequent DAO reads in this transaction return wrong data

            edges.forEach { edge ->
                // Uses the stale entity.data
                println("Node ${entity.data} -> ${edge.target}")
            }
        }
    }

    
    fun getCachedNode(nodeId: String): String {
        return queryCache.getOrPut(nodeId) { 
            // After schema migration (e.g., adding a field), cached entries have old schema
            // No invalidation mechanism when schema changes
            transaction {
                GraphNodeEntity.find { GraphNodes.nodeId eq nodeId }
                    .firstOrNull()?.data ?: "{}"
            }
        }
    }

    
    fun cacheNode(id: NodeId, node: GraphNode) {
        
        // can cause issues with identity-based operations. The JVM boxes the value class
        // when used as a generic type parameter, and two separately boxed instances may
        // not be == even if their underlying values are equal, depending on the context.
        nodeCache[id] = node
    }

    fun getCachedNode(id: NodeId): GraphNode? {
        return nodeCache[id] 
    }
}
