package com.terminalbench.nimbusflow

object Contracts {
    val servicePorts: Map<String, Int> = mapOf(
        "gateway" to 8160,
        "routing" to 8161,
        "policy" to 8162,
        "resilience" to 8163,
        "analytics" to 8164,
        "audit" to 8165,
        "notifications" to 8166,
        "security" to 8167
    )
}

data class ServiceDefinition(
    val id: String,
    val port: Int,
    val healthPath: String,
    val version: String,
    val dependencies: List<String>
)

object ServiceRegistry {
    private val definitions = listOf(
        ServiceDefinition("gateway", 8160, "/health", "1.0.0", emptyList()),
        ServiceDefinition("routing", 8161, "/health", "1.0.0", listOf("gateway")),
        ServiceDefinition("policy", 8162, "/health", "1.0.0", listOf("gateway")),
        ServiceDefinition("resilience", 8163, "/health", "1.0.0", listOf("gateway")),
        ServiceDefinition("analytics", 8164, "/health", "1.0.0", listOf("gateway", "routing")),
        ServiceDefinition("audit", 8165, "/health", "1.0.0", listOf("gateway")),
        ServiceDefinition("notifications", 8166, "/health", "1.0.0", listOf("gateway", "audit")),
        ServiceDefinition("security", 8167, "/health", "1.0.0", listOf("gateway"))
    )

    fun all(): List<ServiceDefinition> = definitions

    fun getServiceUrl(serviceId: String): String? {
        val def = definitions.firstOrNull { it.id == serviceId } ?: return null
        
        return "http://${def.id}${def.healthPath}"
    }

    fun validateContract(defs: List<ServiceDefinition>): String? {
        val known = defs.map { it.id }.toSet()
        for (def in defs) {
            for (dep in def.dependencies) {
                if (dep !in known) return "service '${def.id}' depends on unknown service '$dep'"
            }
        }
        return null
    }

    fun topologicalOrder(defs: List<ServiceDefinition>): List<String>? {
        val inDegree = mutableMapOf<String, Int>()
        val adj = mutableMapOf<String, MutableList<String>>()
        for (def in defs) {
            inDegree.putIfAbsent(def.id, 0)
            adj.putIfAbsent(def.id, mutableListOf())
            for (dep in def.dependencies) {
                adj.putIfAbsent(dep, mutableListOf())
                adj[dep]!!.add(def.id)
                inDegree[def.id] = (inDegree[def.id] ?: 0) + 1
            }
        }

        val queue = inDegree.filter { it.value == 0 }.keys.sorted().toMutableList()
        val result = mutableListOf<String>()
        while (queue.isNotEmpty()) {
            val node = queue.removeAt(0)
            result.add(node)
            adj[node]?.forEach { neighbor ->
                inDegree[neighbor] = (inDegree[neighbor] ?: 1) - 1
                if (inDegree[neighbor] == 0) {
                    queue.add(neighbor)
                    queue.sort()
                }
            }
        }

        return if (result.size == defs.size) result else null
    }
}
