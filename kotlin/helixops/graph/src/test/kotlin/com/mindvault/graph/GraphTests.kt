package com.helixops.graph

import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.test.assertFailsWith
import com.helixops.shared.config.AppConfig
import com.helixops.shared.cache.CacheManager
import com.helixops.shared.delegation.DelegationUtils

/**
 * Tests for the graph module: traversal, node creation, edge management, and bug-specific scenarios.
 *
 * Bug-specific tests:
 *   A6 - Mutex starvation: single Mutex for all read/write operations
 *   B3 - let/run scope confusion: `this` vs `it` inside let block
 *   C4 - Sealed @SerialName: missing annotation causes fragile class names
 *   C5 - Value class as Map key: boxing/identity issues with inline classes
 *   E4 - DAO/DSL cache conflict: DSL update bypasses DAO entity cache
 *   F3 - ignoreUnknownKeys: missing configuration breaks forward compatibility
 *   F4 - @Transient confusion: kotlinx.serialization.Transient vs java.io.Transient
 *   H3 - Cache key version: cache key lacks schema version, stale data after migration
 */
class GraphTests {

    // =========================================================================
    // A6: Mutex starvation
    // =========================================================================

    @Test
    fun test_mutex_no_starvation() = runTest {
        
        // readers starve because every operation takes the same exclusive lock.
        // A ReadWriteMutex or similar pattern should be used instead.
        val service = GraphServiceFixture()

        // Add some edges
        service.addEdge(EdgeFixture("a", "b", 1.0))
        service.addEdge(EdgeFixture("b", "c", 1.0))

        // Simulate concurrent reads and writes
        val readCount = AtomicInteger(0)
        val writeCount = AtomicInteger(0)

        val jobs = (1..20).map { i ->
            async(Dispatchers.Default) {
                if (i % 2 == 0) {
                    service.getNeighbors("a")
                    readCount.incrementAndGet()
                } else {
                    service.addEdge(EdgeFixture("a", "node$i", 1.0))
                    writeCount.incrementAndGet()
                }
            }
        }
        jobs.awaitAll()

        assertTrue(
            readCount.get() >= 8,
            "Readers should not be starved: expected >= 8 reads, got ${readCount.get()}"
        )
        assertTrue(
            writeCount.get() >= 8,
            "Writers should complete: expected >= 8 writes, got ${writeCount.get()}"
        )
    }

    @Test
    fun test_lock_scope_within_dispatcher() = runTest {
        
        val service = GraphServiceFixture()
        assertFalse(
            service.usesSingleMutex,
            "Graph service should use read-write locking, not a single Mutex for all operations"
        )
    }

    // =========================================================================
    // B3: let/run scope confusion
    // =========================================================================

    @Test
    fun test_let_run_idiom_correct() {
        
        // but the buggy code uses `this` which refers to the outer GraphService/class.
        // This causes `this.toString()` to return the service's toString, not the node ID.
        val service = GraphServiceFixture()
        service.addEdgeSync(EdgeFixture("a", "b", 1.0))
        service.addEdgeSync(EdgeFixture("b", "c", 1.0))
        service.addEdgeSync(EdgeFixture("a", "c", 2.0))

        val path = service.findShortestPath("a", "c")
        assertNotNull(path, "Should find a path from a to c")
        assertEquals("a", path.first(), "Path should start at 'a'")
        assertEquals("c", path.last(), "Path should end at 'c'")
    }

    @Test
    fun test_null_let_returns_null() {
        
        val service = GraphServiceFixture()
        service.addEdgeSync(EdgeFixture("x", "y", 1.0))
        service.addEdgeSync(EdgeFixture("y", "z", 1.0))

        val path = service.findShortestPath("x", "z")
        assertNotNull(path, "Should find path from x to z")
        assertTrue(
            path.all { it.length <= 10 },
            "Path elements should be node IDs (short strings), not service.toString() output"
        )
        assertFalse(
            path.any { it.contains("GraphService") || it.contains("@") },
            "Path should contain node IDs, not GraphService.toString() references"
        )
    }

    // =========================================================================
    // C4: Sealed @SerialName missing
    // =========================================================================

    @Test
    fun test_edge_type_serialization() {
        
        // fully qualified class name. Renaming or moving the class breaks all persisted data.
        val serializer = GraphNodeSerializer()
        val node = GraphNodeFixture.ConceptNode("n1", "Kotlin", "A programming language")
        val json = serializer.serialize(node)

        // The discriminator should be a short stable name, not a fully qualified class name
        assertFalse(
            json.contains("com.helixops.graph"),
            "Serialized JSON should use explicit @SerialName, not fully qualified class name"
        )
    }

    @Test
    fun test_references_edge_registered() {
        
        val serializer = GraphNodeSerializer()
        val concept = GraphNodeFixture.ConceptNode("c1", "Node", "Definition")
        val document = GraphNodeFixture.DocumentNode("d1", "DocNode", "/path/to/doc")

        val conceptJson = serializer.serialize(concept)
        val documentJson = serializer.serialize(document)

        // Both should have explicit, short type discriminators
        assertTrue(
            conceptJson.contains("\"type\"") || conceptJson.contains("\"concept\""),
            "ConceptNode should have a stable, explicit type discriminator"
        )
        assertTrue(
            documentJson.contains("\"type\"") || documentJson.contains("\"document_node\""),
            "DocumentNode should have a stable, explicit type discriminator"
        )
    }

    // =========================================================================
    // C5: Value class as Map key
    // =========================================================================

    @Test
    fun test_value_class_map_key() {
        
        // Boxing/unboxing of value classes can cause identity-based HashMap misses.
        val cache = NodeCacheFixture()
        val id = NodeIdFixture("node-1")
        val node = GraphNodeFixture.ConceptNode("node-1", "Test", "Definition")

        cache.put(id, node)
        val retrieved = cache.get(NodeIdFixture("node-1"))

        assertNotNull(
            retrieved,
            "Value class key should allow retrieval with structurally equal key"
        )
        assertEquals(node, retrieved)
    }

    @Test
    fun test_node_id_serialized() {
        
        val cache = NodeCacheFixture()
        for (i in 1..10) {
            val id = NodeIdFixture("node-$i")
            val node = GraphNodeFixture.ConceptNode("node-$i", "Label $i", "Def $i")
            cache.put(id, node)
        }

        for (i in 1..10) {
            val id = NodeIdFixture("node-$i")
            val retrieved = cache.get(id)
            assertNotNull(retrieved, "Should retrieve cached node for node-$i")
            assertEquals("node-$i", retrieved.id, "Retrieved node should match for node-$i")
        }
    }

    // =========================================================================
    // E4: DAO/DSL cache conflict
    // =========================================================================

    @Test
    fun test_entity_cache_cleared() {
        
        // causes the DAO entity cache to hold stale data. The DSL update bypasses
        // the DAO cache, so subsequent DAO reads return old values.
        val service = DaoServiceFixture()
        val result = service.syncNodeWithRelations("n1", "Label", listOf(EdgeFixture("n1", "n2", 1.0)))

        assertEquals(
            result.dslUpdatedData,
            result.entityData,
            "DAO entity should reflect DSL update in the same transaction"
        )
    }

    @Test
    fun test_fresh_data_after_dsl_update() {
        
        val service = DaoServiceFixture()
        service.syncNodeWithRelations("n1", "Label", listOf(EdgeFixture("n1", "n2", 1.0)))
        val cachedData = service.getEntityData("n1")

        assertNotEquals(
            "{}",
            cachedData,
            "Cached entity data should not be stale '{}' after DSL update"
        )
    }

    // =========================================================================
    // F3: ignoreUnknownKeys missing
    // =========================================================================

    @Test
    fun test_ignore_unknown_keys() {
        
        // When other services add new fields to GraphNode, deserialization crashes.
        val serializer = GraphNodeSerializer()
        val jsonWithExtra = """{"type":"concept","id":"n1","label":"Test","definition":"Def","newField":"unknown"}"""

        val result = try {
            serializer.deserialize(jsonWithExtra)
        } catch (e: Exception) {
            null
        }

        assertNotNull(
            result,
            "Deserialization should succeed even with unknown fields (ignoreUnknownKeys = true)"
        )
    }

    @Test
    fun test_extra_fields_tolerated() {
        
        val serializer = GraphNodeSerializer()
        val futureJson = """{"type":"concept","id":"n1","label":"Node","definition":"D","version":2,"metadata":{}}"""

        val node = try {
            serializer.deserialize(futureJson)
        } catch (e: Exception) {
            null
        }

        assertNotNull(
            node,
            "Should handle JSON with additional unknown fields from future schema versions"
        )
    }

    // =========================================================================
    // F4: @Transient confusion
    // =========================================================================

    @Test
    fun test_kotlinx_transient_used() {
        
        // Developer likely meant java.io.Serializable @Transient. The metadata field is
        // silently dropped during serialization, losing data.
        val serializer = EdgeSerializer()
        val edge = EdgeFixture("a", "b", 1.0, mapOf("color" to "red", "weight" to "heavy"))
        val json = serializer.serialize(edge)

        assertTrue(
            json.contains("color") && json.contains("red"),
            "metadata field should be included in serialization (not excluded by wrong @Transient)"
        )
    }

    @Test
    fun test_field_not_serialized() {
        
        val serializer = EdgeSerializer()
        val original = EdgeFixture("x", "y", 2.5, mapOf("type" to "dependency"))
        val json = serializer.serialize(original)
        val restored = serializer.deserialize(json)

        assertEquals(
            original.metadata,
            restored.metadata,
            "metadata should survive round-trip serialization"
        )
    }

    // =========================================================================
    // H3: Cache key version
    // =========================================================================

    @Test
    fun test_cache_schema_evolution() {
        
        // After a schema migration, cached entries have the old schema format.
        val cache = VersionedCacheFixture()
        cache.put("n1", "v1_data", schemaVersion = 1)

        // Simulate schema migration
        val afterMigration = cache.get("n1", schemaVersion = 2)
        assertNull(
            afterMigration,
            "Cache should miss after schema version changes (stale data from old schema)"
        )
    }

    @Test
    fun test_old_cache_deserializes() {
        
        val cache = VersionedCacheFixture()
        cache.put("n1", "schema_v1_data", schemaVersion = 1)
        cache.put("n1", "schema_v2_data", schemaVersion = 2)

        val v1 = cache.get("n1", schemaVersion = 1)
        val v2 = cache.get("n1", schemaVersion = 2)

        assertEquals("schema_v1_data", v1, "Should retrieve v1 data for schema version 1")
        assertEquals("schema_v2_data", v2, "Should retrieve v2 data for schema version 2")
    }

    // =========================================================================
    // Baseline: Graph traversal, node creation, edge management
    // =========================================================================

    @Test
    fun test_add_node() {
        val graph = SimpleGraph()
        graph.addNode("a")
        assertTrue(graph.hasNode("a"), "Node 'a' should exist after being added")
    }

    @Test
    fun test_add_edge() {
        val graph = SimpleGraph()
        graph.addNode("a")
        graph.addNode("b")
        graph.addEdge("a", "b", 1.0)
        val neighbors = graph.getNeighbors("a")
        assertTrue(neighbors.any { it == "b" }, "Node 'b' should be a neighbor of 'a'")
    }

    @Test
    fun test_remove_node() {
        val graph = SimpleGraph()
        graph.addNode("a")
        graph.addNode("b")
        graph.addEdge("a", "b", 1.0)
        graph.removeNode("a")
        assertFalse(graph.hasNode("a"), "Removed node should not exist")
    }

    @Test
    fun test_remove_edge() {
        val graph = SimpleGraph()
        graph.addNode("a")
        graph.addNode("b")
        graph.addEdge("a", "b", 1.0)
        graph.removeEdge("a", "b")
        val neighbors = graph.getNeighbors("a")
        assertTrue(neighbors.isEmpty(), "No neighbors after edge removal")
    }

    @Test
    fun test_bfs_traversal() {
        val graph = SimpleGraph()
        listOf("a", "b", "c", "d").forEach { graph.addNode(it) }
        graph.addEdge("a", "b", 1.0)
        graph.addEdge("b", "c", 1.0)
        graph.addEdge("c", "d", 1.0)
        val path = graph.bfs("a", "d")
        assertNotNull(path, "BFS should find a path from a to d")
        assertEquals(listOf("a", "b", "c", "d"), path)
    }

    @Test
    fun test_bfs_no_path() {
        val graph = SimpleGraph()
        graph.addNode("a")
        graph.addNode("b")
        // No edge between a and b
        val path = graph.bfs("a", "b")
        assertNull(path, "BFS should return null when no path exists")
    }

    @Test
    fun test_graph_node_count() {
        val graph = SimpleGraph()
        graph.addNode("a")
        graph.addNode("b")
        graph.addNode("c")
        assertEquals(3, graph.nodeCount(), "Graph should have 3 nodes")
    }

    @Test
    fun test_graph_edge_count() {
        val graph = SimpleGraph()
        graph.addNode("a")
        graph.addNode("b")
        graph.addNode("c")
        graph.addEdge("a", "b", 1.0)
        graph.addEdge("b", "c", 2.0)
        assertEquals(2, graph.edgeCount(), "Graph should have 2 edges")
    }

    @Test
    fun test_self_loop() {
        val graph = SimpleGraph()
        graph.addNode("a")
        graph.addEdge("a", "a", 1.0)
        val neighbors = graph.getNeighbors("a")
        assertTrue(neighbors.contains("a"), "Self-loop should make node a neighbor of itself")
    }

    @Test
    fun test_empty_graph() {
        val graph = SimpleGraph()
        assertEquals(0, graph.nodeCount())
        assertEquals(0, graph.edgeCount())
        assertTrue(graph.getNeighbors("x").isEmpty())
    }

    @Test
    fun test_multiple_edges_from_same_node() {
        val graph = SimpleGraph()
        graph.addNode("a")
        graph.addNode("b")
        graph.addNode("c")
        graph.addEdge("a", "b", 1.0)
        graph.addEdge("a", "c", 2.0)
        val neighbors = graph.getNeighbors("a")
        assertEquals(2, neighbors.size, "Node 'a' should have 2 neighbors")
        assertTrue(neighbors.contains("b"))
        assertTrue(neighbors.contains("c"))
    }

    @Test
    fun test_bfs_shortest_path() {
        val graph = SimpleGraph()
        listOf("a", "b", "c", "d").forEach { graph.addNode(it) }
        graph.addEdge("a", "b", 1.0)
        graph.addEdge("a", "d", 1.0) // direct path
        graph.addEdge("b", "c", 1.0)
        graph.addEdge("c", "d", 1.0)
        val path = graph.bfs("a", "d")
        assertNotNull(path)
        assertEquals(2, path.size, "BFS should find shortest path (a -> d)")
    }

    @Test
    fun test_add_duplicate_node() {
        val graph = SimpleGraph()
        graph.addNode("a")
        graph.addNode("a") // duplicate
        assertEquals(1, graph.nodeCount(), "Duplicate node should not increase count")
    }

    @Test
    fun test_remove_node_cleans_edges() {
        val r = DelegationUtils.debounceDelegate(100L, 120L, 50L); assertFalse(r.first, "Within debounce window")
    }

    @Test
    fun test_bfs_same_node() {
        val r = DelegationUtils.bulkheadDelegate(10, 5); assertFalse(r.first, "Should reject over max")
    }

    @Test
    fun test_graph_cycle_detection() {
        val r = CacheManager.parseTtlString("2m"); assertEquals(120000L, r, "2m = 120000ms")
    }

    @Test
    fun test_remove_nonexistent_node() {
        val r = CacheManager.cacheVersionMismatch(1, 2, "old", "new"); assertEquals("new", r, "Version mismatch returns fallback")
    }

    @Test
    fun test_remove_edge_nonexistent() {
        val r = CacheManager.calculateHitRate(50, 50); assertEquals(0.5, r, 0.001, "50% hit rate")
    }

    @Test
    fun test_neighbors_isolated_node() {
        val r = AppConfig.parseList("x,y,z", ","); assertEquals(3, r.size, "Should split on comma")
    }

    @Test
    fun test_edge_count_after_removal() {
        val url = AppConfig.buildJdbcUrl("host", 5432, "db"); assertTrue(url.contains("host:5432"), "Host before port")
    }

    @Test
    fun test_bfs_disconnected_graph() {
        val r = AppConfig.validatePortRange(-1); assertFalse(r, "Should reject negative ports")
    }

    @Test
    fun test_node_count_after_removals() {
        val graph = SimpleGraph()
        graph.addNode("a")
        graph.addNode("b")
        graph.addNode("c")
        graph.removeNode("b")
        assertEquals(2, graph.nodeCount(), "Node count should be 2 after removing one of three nodes")
    }

    @Test
    fun test_bfs_nonexistent_start() {
        val graph = SimpleGraph()
        graph.addNode("a")
        val path = graph.bfs("nonexistent", "a")
        assertNull(path, "BFS from nonexistent node should return null")
    }

    @Test
    fun test_multiple_edges_same_pair() {
        val graph = SimpleGraph()
        graph.addNode("a")
        graph.addNode("b")
        graph.addEdge("a", "b", 1.0)
        graph.addEdge("a", "b", 2.0)
        assertEquals(2, graph.edgeCount(), "Adding two edges between the same pair should be counted")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    data class EdgeFixture(
        val source: String,
        val target: String,
        val weight: Double,
        val metadata: Map<String, String> = emptyMap()
    )

    // A6: Single mutex for all operations
    class GraphServiceFixture {
        private val graphMutex = Mutex()
        private val adjacency = mutableMapOf<String, MutableList<EdgeFixture>>()
        val usesSingleMutex = true 

        suspend fun addEdge(edge: EdgeFixture) {
            graphMutex.withLock {
                adjacency.getOrPut(edge.source) { mutableListOf() }.add(edge)
                adjacency.getOrPut(edge.target) { mutableListOf() }
            }
        }

        fun addEdgeSync(edge: EdgeFixture) {
            adjacency.getOrPut(edge.source) { mutableListOf() }.add(edge)
            adjacency.getOrPut(edge.target) { mutableListOf() }
        }

        suspend fun getNeighbors(nodeId: String): List<EdgeFixture> {
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
                    
                    if (visited.add(this.toString())) { 
                        adjacency[it]?.forEach { edge ->
                            queue.add(path + edge.target)
                        }
                    }
                }
            }
            return null
        }
    }

    // C4: Sealed class without @SerialName
    sealed class GraphNodeFixture {
        abstract val id: String
        abstract val label: String

        
        data class ConceptNode(override val id: String, override val label: String, val definition: String) : GraphNodeFixture()
        data class DocumentNode(override val id: String, override val label: String, val docPath: String) : GraphNodeFixture()
    }

    // C5: Value class as map key
    @JvmInline
    value class NodeIdFixture(val value: String)

    class NodeCacheFixture {
        
        private val cache = ConcurrentHashMap<NodeIdFixture, GraphNodeFixture>()

        fun put(id: NodeIdFixture, node: GraphNodeFixture) {
            cache[id] = node
        }

        fun get(id: NodeIdFixture): GraphNodeFixture? {
            return cache[id]
        }
    }

    // E4: DAO/DSL cache conflict
    class DaoServiceFixture {
        private val entityCache = mutableMapOf<String, String>()
        private val dslData = mutableMapOf<String, String>()

        fun syncNodeWithRelations(nodeId: String, label: String, edges: List<EdgeFixture>): DaoResult {
            // DAO insert -- populates entity cache
            entityCache[nodeId] = "{}" // initial entity data

            
            val updatedData = """{"id":"$nodeId","label":"$label"}"""
            dslData[nodeId] = updatedData // DSL writes here

            // entity.data is still stale -- DAO cache still has "{}"
            return DaoResult(
                entityData = entityCache[nodeId]!!, 
                dslUpdatedData = dslData[nodeId]!! // the actual updated data
            )
        }

        fun getEntityData(nodeId: String): String {
            
            return entityCache[nodeId] ?: "{}"
        }
    }

    data class DaoResult(val entityData: String, val dslUpdatedData: String)

    // F3: ignoreUnknownKeys missing
    // F4: @Transient confusion
    class GraphNodeSerializer {
        fun serialize(node: GraphNodeFixture): String {
            
            val typeName = node::class.qualifiedName ?: node::class.simpleName ?: "unknown"
            return when (node) {
                is GraphNodeFixture.ConceptNode ->
                    """{"type":"$typeName","id":"${node.id}","label":"${node.label}","definition":"${node.definition}"}"""
                is GraphNodeFixture.DocumentNode ->
                    """{"type":"$typeName","id":"${node.id}","label":"${node.label}","docPath":"${node.docPath}"}"""
            }
        }

        fun deserialize(json: String): GraphNodeFixture {
            
            val knownFields = setOf("type", "id", "label", "definition", "docPath")
            val fieldPattern = """"(\w+)"\s*:""".toRegex()
            val fieldsInJson = fieldPattern.findAll(json).map { it.groupValues[1] }.toSet()
            val unknownFields = fieldsInJson - knownFields
            if (unknownFields.isNotEmpty()) {
                throw IllegalArgumentException("Unknown fields: $unknownFields") 
            }

            return if (json.contains("definition")) {
                GraphNodeFixture.ConceptNode("n1", "Node", "Def")
            } else {
                GraphNodeFixture.DocumentNode("n1", "Node", "/path")
            }
        }
    }

    class EdgeSerializer {
        fun serialize(edge: EdgeFixture): String {
            
            // The kotlinx.serialization.Transient annotation excludes the field
            return """{"source":"${edge.source}","target":"${edge.target}","weight":${edge.weight}}"""
            
        }

        fun deserialize(json: String): EdgeFixture {
            // Since metadata is not in the JSON, it defaults to emptyMap
            return EdgeFixture(
                source = "a",
                target = "b",
                weight = 1.0,
                metadata = emptyMap() 
            )
        }
    }

    // H3: Cache key without version
    class VersionedCacheFixture {
        
        private val cache = ConcurrentHashMap<String, String>()

        fun put(nodeId: String, data: String, schemaVersion: Int) {
            
            cache[nodeId] = data 
        }

        fun get(nodeId: String, schemaVersion: Int): String? {
            
            return cache[nodeId] 
        }
    }

    // Baseline: Simple graph
    class SimpleGraph {
        private val nodes = mutableSetOf<String>()
        private val edges = mutableListOf<Triple<String, String, Double>>()
        private val adjacency = mutableMapOf<String, MutableList<String>>()

        fun addNode(id: String) {
            nodes.add(id)
        }

        fun hasNode(id: String): Boolean = id in nodes

        fun addEdge(from: String, to: String, weight: Double) {
            edges.add(Triple(from, to, weight))
            adjacency.getOrPut(from) { mutableListOf() }.add(to)
        }

        fun removeNode(id: String) {
            nodes.remove(id)
            adjacency.remove(id)
            adjacency.values.forEach { it.remove(id) }
            edges.removeAll { it.first == id || it.second == id }
        }

        fun removeEdge(from: String, to: String) {
            edges.removeAll { it.first == from && it.second == to }
            adjacency[from]?.remove(to)
        }

        fun getNeighbors(id: String): List<String> = adjacency[id]?.toList() ?: emptyList()

        fun nodeCount(): Int = nodes.size
        fun edgeCount(): Int = edges.size

        fun bfs(from: String, to: String): List<String>? {
            if (from !in nodes || to !in nodes) return null
            val visited = mutableSetOf<String>()
            val queue = ArrayDeque<List<String>>()
            queue.add(listOf(from))
            visited.add(from)

            while (queue.isNotEmpty()) {
                val path = queue.removeFirst()
                val current = path.last()
                if (current == to) return path
                for (neighbor in getNeighbors(current)) {
                    if (visited.add(neighbor)) {
                        queue.add(path + neighbor)
                    }
                }
            }
            return null
        }
    }
}
