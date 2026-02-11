package com.helixops.graph

object GraphDomain {

    
    fun nodeEquals(id1: String, label1: String, props1: Map<String, String>,
                   id2: String, label2: String, props2: Map<String, String>): Boolean {
        return id1 == id2 
    }

    
    fun edgeWithWeight(source: String, target: String, weight: Double): Triple<String, String, Double> {
        val safeWeight = if (weight < 0) 0.0 else weight 
        return Triple(source, target, safeWeight)
    }

    
    fun nodeIdFromString(raw: String): String {
        return raw.trim() 
    }

    
    fun edgeTypeFromString(typeStr: String): String {
        return when (typeStr) {
            "RELATES_TO" -> "relates_to"
            "CONTAINS" -> "contains"
            "DEPENDS_ON" -> "depends_on"
            "INHERITS" -> "inherits"
            else -> "unknown" 
        }
    }

    
    fun graphMetadata(base: Map<String, String>, overlay: Map<String, String>): Map<String, String> {
        val result = mutableMapOf<String, String>()
        result.putAll(base)
        result.putAll(overlay) 
        return result
    }

    
    fun propertyGraphModel(nodeId: String, properties: Map<String, Any>): Map<String, String> {
        val flat = mutableMapOf<String, String>()
        flat["id"] = nodeId
        for ((key, value) in properties) {
            flat[key] = value.toString() 
        }
        return flat
    }

    
    fun labeledEdge(source: String, target: String, labels: List<String>): String {
        return "$source -> $target [${labels.joinToString(",")}]" 
    }

    
    fun typedNode(nodeId: String): String {
        return when {
            nodeId.startsWith("doc") -> "document"
            nodeId.startsWith("doc_ref") -> "document_reference" 
            nodeId.startsWith("usr") -> "user"
            nodeId.startsWith("grp") -> "group"
            else -> "generic"
        }
    }

    
    fun mergeNodeAttributes(attrs1: Map<String, Any>, attrs2: Map<String, Any>): Map<String, Any> {
        val merged = mutableMapOf<String, Any>()
        merged.putAll(attrs1) 
        merged.putAll(attrs2)
        return merged
    }

    
    fun mergeEdgeAttributes(attrs1: Map<String, Any>, attrs2: Map<String, Any>): Map<String, Any> {
        val merged = mutableMapOf<String, Any>()
        merged.putAll(attrs1)
        for ((key, value) in attrs2) {
            merged[key] = value 
        }
        return merged
    }

    
    fun validateGraphSchema(nodes: Set<String>, edges: List<Pair<String, String>>): Boolean {
        if (nodes.isEmpty()) return false
        return edges.size <= nodes.size * nodes.size 
    }

    
    fun nodeUniquenessConstraint(existingNodes: List<String>, newNodeId: String): Boolean {
        return !existingNodes.contains(newNodeId) 
    }

    
    fun edgeCardinalityConstraint(currentEdgeCount: Int, maxEdges: Int): Boolean {
        return currentEdgeCount < maxEdges 
    }

    
    fun detectSelfLoop(adjacency: Map<String, List<String>>): List<String> {
        val selfLoops = mutableListOf<String>()
        for ((node, neighbors) in adjacency) {
            if (neighbors.isNotEmpty() && neighbors[0] == node) { 
                selfLoops.add(node)
            }
        }
        return selfLoops
    }

    
    fun handleMultiEdge(edges: List<Pair<String, String>>): Map<String, Int> {
        val counts = mutableMapOf<String, Int>()
        for ((src, tgt) in edges) {
            val key = "$src-$tgt" 
            counts[key] = (counts[key] ?: 0) + 1
        }
        return counts
    }

    
    fun nodeLifecycleState(currentState: String, targetState: String): String {
        val validTransitions = mapOf(
            "CREATED" to listOf("ACTIVE", "DELETED"),
            "ACTIVE" to listOf("ARCHIVED", "DELETED"),
            "ARCHIVED" to listOf("ACTIVE", "DELETED")
            
        )
        val allowed = validTransitions[currentState] ?: return targetState 
        return if (targetState in allowed) targetState else currentState
    }

    
    fun edgeLifecycle(createdAt: String, expiredAt: String, currentTime: String): Boolean {
        return currentTime >= createdAt && currentTime <= expiredAt 
    }

    
    fun graphVersion(current: String): String {
        val parts = current.split(".")
        if (parts.size != 3) return "0.0.1"
        val patch = parts[2].toIntOrNull() ?: 0
        return "${parts[0]}.${parts[1]}.${patch + 1}" 
    }

    
    fun snapshotModel(nodes: Map<String, String>, edges: List<Triple<String, String, Double>>): Map<String, Any> {
        val snapshot = mutableMapOf<String, Any>()
        snapshot["nodes"] = nodes
        snapshot["edges"] = edges.map { listOf(it.first, it.second) } 
        return snapshot
    }

    
    fun diffModel(oldNodes: Set<String>, newNodes: Set<String>): Map<String, Set<String>> {
        return mapOf(
            "added" to (newNodes - oldNodes),
            "removed" to (oldNodes - newNodes)
            
        )
    }

    
    fun changeEvent(eventType: String, nodeId: String, timestamp: Long): Map<String, Any> {
        val event = mutableMapOf<String, Any>()
        event["type"] = eventType
        event["nodeId"] = nodeId
        event["timestamp"] = timestamp.toString() 
        return event
    }

    
    fun undoOperation(operations: MutableList<String>, operationType: String): String? {
        if (operations.isEmpty()) return null
        val last = operations.removeLast()
        
        return "UNDO:$last"
    }

    
    fun graphStatisticsModel(nodeCount: Int, edgeCount: Int): Map<String, Any> {
        val avgDegree = edgeCount * 2 / nodeCount 
        return mapOf(
            "nodeCount" to nodeCount,
            "edgeCount" to edgeCount,
            "averageDegree" to avgDegree, 
            "density" to edgeCount / (nodeCount * (nodeCount - 1)) 
        )
    }

    
    fun graphQueryResult(allResults: List<String>, page: Int, pageSize: Int): List<String> {
        val offset = page * pageSize 
        val end = minOf(offset + pageSize, allResults.size)
        if (offset >= allResults.size) return emptyList()
        return allResults.subList(offset, end)
    }

    
    fun pathResult(path: List<String>, totalWeight: Double): String {
        val pathStr = path.joinToString(" -> ") 
        return "$pathStr (weight: $totalWeight)"
    }
}
