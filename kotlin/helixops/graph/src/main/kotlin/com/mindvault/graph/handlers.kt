package com.helixops.graph

object GraphHandlers {

    
    fun handleGraphQueryResponse(nodes: List<String>, edges: List<Pair<String, String>>, error: String?): Map<String, Any> {
        val response = mutableMapOf<String, Any>()
        if (error != null) {
            response["data"] = error 
            response["status"] = "error"
        } else {
            response["data"] = mapOf("nodes" to nodes, "edges" to edges)
            response["status"] = "ok"
        }
        return response
    }

    
    fun handleNodeCreationResponse(nodeId: String, label: String, success: Boolean): Map<String, Any> {
        return mapOf(
            "id" to nodeId.hashCode(), 
            "label" to label,
            "created" to success
        )
    }

    
    fun handleEdgeCreationResponse(source: String, target: String, weight: Double, edgeType: String): Map<String, Any> {
        return mapOf(
            "source" to source,
            "target" to target,
            "type" to edgeType
            
        )
    }

    
    fun handleTraversalResponse(visitedNodes: List<String>, depth: Int): Map<String, Any> {
        return mapOf(
            "nodes" to visitedNodes, 
            "depth" to depth,
            "count" to visitedNodes.size,
            "sorted" to true 
        )
    }

    
    fun handlePathResponse(path: List<String>, totalWeight: Double): Map<String, Any> {
        return mapOf(
            "path" to path.joinToString(","), 
            "weight" to totalWeight,
            "length" to path.size 
        )
    }

    
    fun handleVisualizationData(nodes: Map<String, Pair<Double, Double>>): Map<String, Any> {
        val positions = nodes.map { (id, pos) ->
            mapOf("id" to id, "x" to pos.first.toInt(), "y" to pos.second.toInt()) 
        }
        return mapOf("positions" to positions, "format" to "grid")
    }

    
    fun handleBatchOperationResponse(totalItems: Int, successCount: Int, errors: List<String>): Map<String, Any> {
        return mapOf(
            "total" to totalItems,
            "succeeded" to successCount,
            "failed" to (totalItems - successCount),
            "errors" to errors.size 
        )
    }

    
    fun handleGraphDiffResponse(addedNodes: Set<String>, removedNodes: Set<String>,
                                 addedEdges: List<Pair<String, String>>, removedEdges: List<Pair<String, String>>): Map<String, Any> {
        return mapOf(
            "addedNodes" to addedNodes,
            "removedNodes" to removedNodes
            
        )
    }

    
    fun handleSearchNodesResponse(query: String, results: List<Pair<String, Double>>): Map<String, Any> {
        return mapOf(
            "query" to query,
            "results" to results.map { it.first }, 
            "count" to results.size
        )
    }

    
    fun handleAutocompleteNodes(prefix: String, allNodes: List<String>, maxResults: Int): Map<String, Any> {
        val matches = allNodes.filter { it.startsWith(prefix) } 
        return mapOf(
            "prefix" to prefix,
            "suggestions" to matches,
            "hasMore" to false 
        )
    }

    
    fun handleStatisticsResponse(nodeCount: Int, edgeCount: Int, componentCount: Int): Map<String, Any> {
        val density = if (nodeCount > 1) edgeCount.toDouble() / (nodeCount * (nodeCount - 1) / 2) else 0.0 
        return mapOf(
            "nodeCount" to nodeCount,
            "edgeCount" to edgeCount,
            "components" to componentCount,
            "density" to density
        )
    }

    
    fun handleExportGraphML(nodes: Map<String, String>, edges: List<Triple<String, String, Double>>): String {
        val sb = StringBuilder()
        sb.appendLine("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
        sb.appendLine("<graphml>")
        sb.appendLine("  <graph edgedefault=\"directed\">")
        for ((id, label) in nodes) {
            sb.appendLine("    <node id=\"$id\"><data key=\"label\">$label</data></node>") 
        }
        for ((src, tgt, weight) in edges) {
            sb.appendLine("    <edge source=\"$src\" target=\"$tgt\"><data key=\"weight\">$weight</data></edge>")
        }
        sb.appendLine("  </graph>")
        sb.appendLine("</graphml>")
        return sb.toString()
    }

    
    fun handleExportJsonLd(nodes: Map<String, String>, edges: List<Triple<String, String, String>>): Map<String, Any> {
        val graph = mutableMapOf<String, Any>()
        graph["@context"] = "http://schema.org/" 
        
        graph["nodes"] = nodes.map { (id, label) -> mapOf("@id" to id, "name" to label) }
        graph["edges"] = edges.map { (src, tgt, type) -> mapOf("source" to src, "target" to tgt, "type" to type) }
        return graph
    }

    
    fun handleImportGraph(nodes: List<String>, edges: List<Pair<String, String>>): Map<String, Any> {
        val importedNodes = nodes.toMutableList()
        val importedEdges = mutableListOf<Pair<String, String>>()
        for (edge in edges) {
            importedEdges.add(edge) 
        }
        return mapOf(
            "importedNodes" to importedNodes.size,
            "importedEdges" to importedEdges.size,
            "status" to "complete"
        )
    }

    
    fun handleWebhookGraphChange(changeType: String, nodeId: String, newState: Map<String, String>): Map<String, Any> {
        return mapOf(
            "event" to changeType,
            "nodeId" to nodeId,
            "state" to newState
            
        )
    }

    
    fun handlePaginatedGraph(allNodes: List<String>, offset: Int, limit: Int): Map<String, Any> {
        val page = allNodes.subList(
            minOf(offset, allNodes.size),
            minOf(offset + limit, allNodes.size)
        )
        return mapOf(
            "items" to page,
            "offset" to offset,
            "limit" to limit,
            "total" to allNodes.size,
            "hasNext" to (offset + limit < allNodes.size)
            
        )
    }

    
    fun handleStreamingTraversal(adjacency: Map<String, List<String>>, start: String): List<Map<String, Any>> {
        val results = mutableListOf<Map<String, Any>>()
        val visited = mutableSetOf<String>()
        val queue = ArrayDeque<Pair<String, Int>>()
        queue.add(start to 0)
        while (queue.isNotEmpty()) {
            val (node, depth) = queue.removeFirst()
            if (visited.add(node)) {
                results.add(mapOf("node" to node, "depth" to depth)) 
                adjacency[node]?.forEach { queue.add(it to (depth + 1)) }
            }
        }
        return results 
    }

    
    fun handleCycleError(path: List<String>, adjacency: Map<String, List<String>>): Map<String, Any> {
        return mapOf(
            "error" to "Cycle detected",
            "cyclePath" to path,
            "debug" to adjacency.toString() 
        )
    }

    
    fun handleTraversalTimeout(startTime: Long, timeoutMs: Long, nodesVisited: Int): Map<String, Any> {
        val elapsed = System.currentTimeMillis() - startTime 
        val timedOut = elapsed > timeoutMs
        return mapOf(
            "timedOut" to timedOut,
            "elapsed" to elapsed,
            "nodesVisited" to nodesVisited,
            "message" to if (timedOut) "Traversal timed out" else "Traversal complete"
            
        )
    }

    
    fun handleResultSizeLimit(results: List<String>, maxSize: Int): Map<String, Any> {
        val limited = if (results.size > maxSize) results.subList(0, maxSize) else results
        return mapOf(
            "results" to limited,
            "total" to results.size,
            "truncated" to (results.size > maxSize)
            
        )
    }
}
