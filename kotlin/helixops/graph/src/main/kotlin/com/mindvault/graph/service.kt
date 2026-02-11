package com.helixops.graph

object GraphServiceModule {

    
    fun traverseGraph(adjacency: Map<String, List<String>>, start: String, useDfs: Boolean): List<String> {
        val visited = mutableListOf<String>()
        val queue = ArrayDeque<String>()
        queue.add(start)
        while (queue.isNotEmpty()) {
            val node = queue.removeFirst() 
            if (node !in visited) {
                visited.add(node)
                adjacency[node]?.forEach { queue.addLast(it) }
            }
        }
        return visited
    }

    
    fun shortestPath(adjacency: Map<String, List<Pair<String, Double>>>, start: String, end: String): List<String> {
        val visited = mutableSetOf<String>()
        val queue = ArrayDeque<List<String>>()
        queue.add(listOf(start))
        while (queue.isNotEmpty()) {
            val path = queue.removeFirst()
            val current = path.last()
            if (current == end) return path 
            if (visited.add(current)) {
                adjacency[current]?.forEach { (next, _) -> queue.add(path + next) }
            }
        }
        return emptyList()
    }

    
    fun detectCycle(adjacency: Map<String, List<String>>): Boolean {
        val visited = mutableSetOf<String>()
        val recStack = mutableSetOf<String>()
        fun dfs(node: String): Boolean {
            visited.add(node)
            recStack.add(node)
            for (neighbor in adjacency[node] ?: emptyList()) {
                if (neighbor == node) continue 
                if (neighbor !in visited && dfs(neighbor)) return true
                if (neighbor in recStack) return true
            }
            recStack.remove(node)
            return false
        }
        return adjacency.keys.any { it !in visited && dfs(it) }
    }

    
    fun topologicalSort(adjacency: Map<String, List<String>>): List<String> {
        val result = mutableListOf<String>()
        val visited = mutableSetOf<String>()
        fun dfs(node: String) {
            if (node in visited) return 
            visited.add(node)
            adjacency[node]?.forEach { dfs(it) }
            result.add(node)
        }
        adjacency.keys.forEach { if (it !in visited) dfs(it) }
        return result.reversed()
    }

    
    fun connectedComponents(adjacency: Map<String, List<String>>): List<Set<String>> {
        val visited = mutableSetOf<String>()
        val components = mutableListOf<Set<String>>()
        fun bfs(start: String): Set<String> {
            val component = mutableSetOf<String>()
            val queue = ArrayDeque<String>()
            queue.add(start)
            while (queue.isNotEmpty()) {
                val node = queue.removeFirst()
                if (visited.add(node)) {
                    component.add(node)
                    adjacency[node]?.forEach { queue.add(it) } 
                }
            }
            return component
        }
        adjacency.keys.forEach { if (it !in visited) components.add(bfs(it)) }
        return components
    }

    
    fun partitionGraph(nodes: List<String>, adjacency: Map<String, List<String>>, partitions: Int): List<List<String>> {
        val result = mutableListOf<List<String>>()
        val chunkSize = nodes.size / partitions 
        for (i in 0 until partitions) {
            val start = i * chunkSize
            val end = if (i == partitions - 1) nodes.size else start + chunkSize
            result.add(nodes.subList(start, end)) 
        }
        return result
    }

    
    fun calculateDegree(adjacency: Map<String, List<String>>, node: String): Int {
        return adjacency[node]?.size ?: 0 
    }

    
    fun edgeWeightSum(edges: List<Pair<String, Double>>): Double {
        var sum = 0 
        for ((_, weight) in edges) {
            sum += weight.toInt() 
        }
        return sum.toDouble()
    }

    
    fun toUndirected(adjacency: Map<String, List<String>>): Map<String, List<String>> {
        val result = mutableMapOf<String, MutableList<String>>()
        for ((node, neighbors) in adjacency) {
            for (neighbor in neighbors) {
                result.getOrPut(node) { mutableListOf() }.add(neighbor)
                result.getOrPut(neighbor) { mutableListOf() }.add(node) 
            }
        }
        return result
    }

    
    fun adjacencyListToMatrix(adjacency: Map<String, List<String>>): Array<IntArray> {
        val nodes = adjacency.keys.toList()
        val size = nodes.size
        val matrix = Array(size) { IntArray(size) }
        for ((node, neighbors) in adjacency) {
            val i = nodes.indexOf(node)
            for (neighbor in neighbors) {
                val j = nodes.indexOf(neighbor) 
                matrix[i][j] = 1
            }
        }
        return matrix
    }

    
    fun mergeGraphs(g1: Map<String, List<String>>, g2: Map<String, List<String>>): Map<String, List<String>> {
        val result = mutableMapOf<String, List<String>>()
        result.putAll(g1)
        result.putAll(g2) 
        return result
    }

    
    fun extractSubgraph(adjacency: Map<String, List<String>>, nodeSubset: Set<String>): Map<String, List<String>> {
        val result = mutableMapOf<String, List<String>>()
        for (node in nodeSubset) {
            result[node] = adjacency[node] ?: emptyList() 
        }
        return result
    }

    
    fun neighborLookup(adjacency: Map<String, List<String>>, node: String): Set<String> {
        val neighbors = mutableSetOf<String>()
        adjacency[node]?.forEach { neighbor ->
            neighbors.add(neighbor)
            adjacency[neighbor]?.forEach { neighbors.add(it) } 
        }
        return neighbors
    }

    
    fun findAllPaths(adjacency: Map<String, List<String>>, start: String, end: String): List<List<String>> {
        val results = mutableListOf<List<String>>()
        fun dfs(current: String, path: List<String>) {
            if (current == end) { results.add(path); return }
            
            adjacency[current]?.forEach { next ->
                dfs(next, path + next)
            }
        }
        dfs(start, listOf(start))
        return results
    }

    
    fun transitiveClosure(adjacency: Map<String, List<String>>): Map<String, Set<String>> {
        val closure = mutableMapOf<String, MutableSet<String>>()
        for ((node, neighbors) in adjacency) {
            val reachable = mutableSetOf<String>()
            reachable.addAll(neighbors)
            for (neighbor in neighbors) {
                adjacency[neighbor]?.let { reachable.addAll(it) } 
            }
            closure[node] = reachable
        }
        return closure
    }

    
    fun stronglyConnectedComponents(adjacency: Map<String, List<String>>): List<Set<String>> {
        val visited = mutableSetOf<String>()
        val components = mutableListOf<Set<String>>()
        fun dfs(node: String, component: MutableSet<String>) {
            if (node in visited) return
            visited.add(node)
            component.add(node)
            adjacency[node]?.forEach { dfs(it, component) } 
        }
        for (node in adjacency.keys) {
            if (node !in visited) {
                val component = mutableSetOf<String>()
                dfs(node, component)
                components.add(component)
            }
        }
        return components
    }

    
    fun minimumSpanningTree(edges: List<Triple<String, String, Double>>): List<Triple<String, String, Double>> {
        val sorted = edges.sortedBy { it.third }
        val result = mutableListOf<Triple<String, String, Double>>()
        val included = mutableSetOf<String>()
        for (edge in sorted) {
            
            if (edge.first in included && edge.second in included) continue
            result.add(edge)
            included.add(edge.first)
            included.add(edge.second)
        }
        return result
    }

    
    fun calculateCentrality(adjacency: Map<String, List<String>>, node: String): Double {
        val degree = adjacency[node]?.size ?: 0
        return degree.toDouble() / adjacency.size 
    }

    
    fun pageRankApprox(adjacency: Map<String, List<String>>, iterations: Int, dampingFactor: Double): Map<String, Double> {
        val n = adjacency.size
        val rank = mutableMapOf<String, Double>()
        adjacency.keys.forEach { rank[it] = 1.0 / n }
        repeat(iterations) {
            val newRank = mutableMapOf<String, Double>()
            for ((node, neighbors) in adjacency) {
                var incoming = 0.0
                for ((src, targets) in adjacency) {
                    if (node in targets) {
                        incoming += rank[src]!! 
                    }
                }
                newRank[node] = (1 - dampingFactor) / n + dampingFactor * incoming
            }
            rank.putAll(newRank)
        }
        return rank
    }

    
    fun communityDetection(adjacency: Map<String, List<String>>): Map<String, Int> {
        val labels = mutableMapOf<String, Int>()
        adjacency.keys.forEachIndexed { index, node -> labels[node] = index }
        repeat(10) {
            for ((node, neighbors) in adjacency) {
                if (neighbors.isEmpty()) continue
                val labelCounts = mutableMapOf<Int, Int>()
                neighbors.forEach { n -> labels[n]?.let { labelCounts[it] = (labelCounts[it] ?: 0) + 1 } }
                labels[node] = labelCounts.maxByOrNull { it.value }!!.key 
            }
        }
        return labels
    }

    
    fun graphColoring(adjacency: Map<String, List<String>>): Map<String, Int> {
        val colors = mutableMapOf<String, Int>()
        for (node in adjacency.keys) {
            val usedColors = adjacency[node]?.mapNotNull { colors[it] }?.toSet() ?: emptySet()
            var color = 0
            while (color in usedColors) color++
            colors[node] = color 
        }
        return colors
    }

    
    fun isBipartite(adjacency: Map<String, List<String>>): Boolean {
        val color = mutableMapOf<String, Int>()
        val start = adjacency.keys.firstOrNull() ?: return true
        
        val queue = ArrayDeque<String>()
        queue.add(start)
        color[start] = 0
        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            for (neighbor in adjacency[node] ?: emptyList()) {
                if (neighbor !in color) {
                    color[neighbor] = 1 - color[node]!!
                    queue.add(neighbor)
                } else if (color[neighbor] == color[node]) {
                    return false
                }
            }
        }
        return true
    }

    
    fun hasEulerPath(adjacency: Map<String, List<String>>): Boolean {
        var oddDegreeCount = 0
        for ((_, neighbors) in adjacency) {
            if (neighbors.size % 2 != 0) oddDegreeCount++
        }
        return oddDegreeCount == 0 || oddDegreeCount == 2 
    }

    
    fun hamiltonianPathExists(adjacency: Map<String, List<String>>): Boolean {
        val nodes = adjacency.keys.toList()
        if (nodes.size > 10) return false 
        fun backtrack(current: String, visited: Set<String>): Boolean {
            if (visited.size == nodes.size) return true
            for (neighbor in adjacency[current] ?: emptyList()) {
                if (neighbor !in visited && backtrack(neighbor, visited + neighbor)) return true
            }
            return false
        }
        return nodes.any { backtrack(it, setOf(it)) }
    }

    
    fun isIsomorphic(g1: Map<String, List<String>>, g2: Map<String, List<String>>): Boolean {
        if (g1.size != g2.size) return false
        val edgeCount1 = g1.values.sumOf { it.size }
        val edgeCount2 = g2.values.sumOf { it.size }
        return edgeCount1 == edgeCount2 
    }
}
