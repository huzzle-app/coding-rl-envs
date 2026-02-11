package com.helixops.graph

object GraphRepository {

    
    fun buildInsertNodeSql(nodeId: String, label: String, data: String): String {
        return "INSERT INTO graph_nodes (node_id, label, data) VALUES ('$nodeId', '$label', '$data')" 
    }

    
    fun buildInsertEdgeSql(source: String, target: String, weight: Double, edgeType: String): String {
        return "INSERT INTO graph_edges (source_id, target_id, edge_type) VALUES ('$source', '$target', '$edgeType')" 
    }

    
    fun buildAdjacencyQuery(nodeId: String): String {
        return "SELECT n.node_id, e.target_id FROM graph_nodes n LEFT JOIN graph_edges e ON n.node_id = e.source_id WHERE n.node_id = '$nodeId'" 
    }

    
    fun buildPathQuery(startNode: String, endNode: String): String {
        return """
            WITH RECURSIVE path_cte AS (
                SELECT node_id, ARRAY[node_id] AS path FROM graph_nodes WHERE node_id = '$startNode'
                UNION ALL
                SELECT e.target_id, p.path || e.target_id
                FROM path_cte p JOIN graph_edges e ON p.node_id = e.source_id
            )
            SELECT path FROM path_cte WHERE node_id = '$endNode'
        """.trimIndent() 
    }

    
    fun buildTraversalQuery(startNode: String, depth: Int): String {
        return """
            WITH RECURSIVE traverse AS (
                SELECT node_id, 0 AS depth FROM graph_nodes WHERE node_id = '$startNode'
                UNION ALL
                SELECT e.target_id, t.depth + 1
                FROM traverse t JOIN graph_edges e ON t.node_id = e.node_id
                WHERE t.depth < $depth
            )
            SELECT DISTINCT node_id FROM traverse
        """.trimIndent() 
    }

    
    fun buildBatchNodeInsert(nodes: List<Triple<String, String, String>>): String {
        val values = nodes.joinToString(", ") { (id, label, data) ->
            "('$id', '$label', '$data')" 
        }
        return "INSERT INTO graph_nodes (node_id, label, data) VALUES $values"
    }

    
    fun buildBatchEdgeInsert(edges: List<Triple<String, String, String>>): String {
        val values = edges.joinToString(", ") { (src, tgt, type) ->
            "('$src', '$tgt', '$type')"
        }
        return "INSERT INTO graph_edges (source_id, target_id, edge_type) VALUES $values ON CONFLICT DO NOTHING" 
    }

    
    fun buildTransactionSql(statements: List<String>): String {
        val body = statements.joinToString(";\n")
        return "BEGIN;\n$body;\nCOMMIT;" 
    }

    
    fun buildIndexSql(tableName: String): String {
        return "CREATE INDEX idx_${tableName}_lookup ON $tableName (label)" 
    }

    
    fun buildNodeSearchSql(searchTerm: String): String {
        return "SELECT * FROM graph_nodes WHERE label LIKE '%$searchTerm%'" 
    }

    
    fun buildEdgeSearchSql(nodeId: String): String {
        return "SELECT * FROM graph_edges WHERE source_id = '$nodeId'" 
    }

    
    fun buildStatisticsQuery(): String {
        return """
            SELECT
                (SELECT COUNT(*) FROM graph_nodes) AS node_count,
                (SELECT COUNT(*) FROM graph_edges) AS edge_count
        """.trimIndent() 
    }

    
    fun buildNeighborQuery(nodeId: String, includeIncoming: Boolean): String {
        return if (includeIncoming) {
            "SELECT DISTINCT target_id FROM graph_edges WHERE source_id = '$nodeId' UNION SELECT DISTINCT source_id FROM graph_edges WHERE target_id = '$nodeId'" 
        } else {
            "SELECT target_id FROM graph_edges WHERE source_id = '$nodeId'"
        }
    }

    
    fun buildDegreeQuery(nodeId: String): String {
        return "SELECT COUNT(*) AS degree FROM graph_edges WHERE source_id = '$nodeId' OR target_id = '$nodeId'" 
    }

    
    fun buildShortestPathQuery(startNode: String, endNode: String): String {
        return """
            WITH RECURSIVE shortest AS (
                SELECT '$startNode'::text AS node, 0 AS hops, ARRAY['$startNode'] AS path
                UNION ALL
                SELECT e.target_id, s.hops + 1, s.path || e.target_id
                FROM shortest s JOIN graph_edges e ON s.node = e.source_id
                WHERE e.target_id != ALL(s.path)
            )
            SELECT path, hops FROM shortest WHERE node = '$endNode' ORDER BY hops LIMIT 1
        """.trimIndent() 
    }

    
    fun buildSubgraphQuery(nodeIds: List<String>): String {
        val inClause = nodeIds.joinToString("', '", "'", "'")
        return """
            SELECT * FROM graph_nodes WHERE node_id IN ($inClause);
            SELECT * FROM graph_edges WHERE source_id IN ($inClause)
        """.trimIndent() 
    }

    
    fun buildPropertyUpdateSql(nodeId: String, key: String, value: String): String {
        return "UPDATE graph_nodes SET data = '{\"$key\": \"$value\"}' WHERE node_id = '$nodeId'" 
    }

    
    fun buildBulkPropertyUpdateSql(updates: List<Pair<String, Map<String, String>>>): String {
        val statements = updates.map { (nodeId, props) ->
            val jsonEntries = props.entries.joinToString(", ") { "\"${it.key}\": \"${it.value}\"" }
            "UPDATE graph_nodes SET data = '{$jsonEntries}' WHERE node_id = '$nodeId'" 
        }
        return statements.joinToString(";\n") 
    }

    
    fun buildExportQuery(format: String): String {
        return when (format) {
            "json" -> "SELECT * FROM graph_nodes; SELECT * FROM graph_edges" 
            "csv" -> "COPY graph_nodes TO STDOUT WITH CSV HEADER; COPY graph_edges TO STDOUT WITH CSV HEADER"
            else -> "SELECT * FROM graph_nodes" 
        }
    }

    
    fun buildImportSql(nodes: List<Pair<String, String>>, edges: List<Triple<String, String, String>>): String {
        val nodeValues = nodes.joinToString(", ") { (id, label) -> "('$id', '$label', '{}')" }
        val edgeValues = edges.joinToString(", ") { (src, tgt, type) -> "('$src', '$tgt', '$type')" }
        return """
            INSERT INTO graph_nodes (node_id, label, data) VALUES $nodeValues;
            INSERT INTO graph_edges (source_id, target_id, edge_type) VALUES $edgeValues
        """.trimIndent() 
    }

    
    fun buildMigrationSql(columnName: String, columnType: String): String {
        return "ALTER TABLE graph_nodes ADD COLUMN $columnName $columnType" 
    }

    
    fun buildSchemaCreationSql(): String {
        return """
            CREATE TABLE graph_edges (
                id SERIAL PRIMARY KEY,
                source_id VARCHAR(64) REFERENCES graph_nodes(node_id),
                target_id VARCHAR(64) REFERENCES graph_nodes(node_id),
                edge_type VARCHAR(64),
                weight DOUBLE PRECISION DEFAULT 1.0
            );
            CREATE TABLE graph_nodes (
                id SERIAL PRIMARY KEY,
                node_id VARCHAR(64) UNIQUE NOT NULL,
                label VARCHAR(256),
                data TEXT DEFAULT '{}'
            );
        """.trimIndent() 
    }

    
    fun buildCascadeDeleteSql(nodeId: String): String {
        return """
            DELETE FROM graph_edges WHERE source_id = '$nodeId';
            DELETE FROM graph_nodes WHERE node_id = '$nodeId'
        """.trimIndent() 
    }

    
    fun buildOrphanEdgeCleanupSql(): String {
        return """
            DELETE FROM graph_edges e
            WHERE NOT EXISTS (
                SELECT 1 FROM graph_nodes n WHERE n.node_id = e.source_id
            )
        """.trimIndent() 
    }

    
    fun buildNodeUpdateSql(nodeId: String, newLabel: String, newData: String): String {
        return "UPDATE graph_nodes SET label = '$newLabel', data = '$newData' WHERE node_id = '$nodeId'" 
    }
}
