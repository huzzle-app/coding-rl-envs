package com.mindvault.shared

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import java.math.BigDecimal
import java.math.RoundingMode
import java.time.Instant
import java.util.*
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Cross-service integration tests that verify consistency across multiple
 * services. These simulate realistic bug dependency chains where fixing
 * one service's bugs impacts others.
 *
 * Patterns tested:
 *   - Auth → Gateway: JWT validation flows through to request handling
 *   - Documents → Search: Document CRUD triggers search index updates
 *   - Billing → Notifications: Payment events trigger notification delivery
 *   - Auth → Collab: Token-based session management for collaborative editing
 *   - Gateway → Analytics: Request handling generates analytics events with MDC
 *   - Graph → Embeddings: Knowledge graph traversal feeds embedding computation
 *   - Config → All: Configuration propagation affects all services
 */
class CrossServiceTests {

    // =========================================================================
    // Auth → Gateway: JWT flow
    // =========================================================================

    @Test
    fun test_auth_gateway_jwt_validated_before_request() {
        // Simulates: Gateway receives request → validates JWT via Auth → processes
        val auth = AuthStub()
        val gateway = GatewayStub(auth)

        val token = auth.issueToken("user1")
        val result = gateway.handleAuthenticatedRequest(token, "/api/documents")

        assertTrue(result.authenticated, "Valid token should authenticate the request")
        assertEquals(200, result.statusCode, "Authenticated request should succeed")
    }

    @Test
    fun test_auth_gateway_expired_token_returns_401() {
        // D3: null payload → NPE in gateway
        val auth = AuthStub()
        val gateway = GatewayStub(auth)

        val result = gateway.handleAuthenticatedRequest("invalid-token", "/api/documents")

        assertFalse(result.threwNpe, "Invalid token should return 401, not throw NPE in gateway")
        assertEquals(401, result.statusCode, "Invalid token should produce 401")
    }

    @Test
    fun test_auth_gateway_none_alg_blocked() {
        // I4 + A1: JWT none bypass reaching gateway handler
        val auth = AuthStub()
        val gateway = GatewayStub(auth)

        val header = Base64.getUrlEncoder().withoutPadding().encodeToString(
            """{"alg":"none","typ":"JWT"}""".toByteArray()
        )
        val payload = Base64.getUrlEncoder().withoutPadding().encodeToString(
            """{"sub":"admin","exp":${System.currentTimeMillis() / 1000 + 3600}}""".toByteArray()
        )
        val noneToken = "$header.$payload."

        val result = gateway.handleAuthenticatedRequest(noneToken, "/api/admin")
        assertEquals(401, result.statusCode, "JWT with alg=none must not pass gateway authentication")
    }

    // =========================================================================
    // Documents → Search: CRUD triggers search updates
    // =========================================================================

    @Test
    fun test_document_create_triggers_search_index() {
        // Creating a document should add it to the search index
        val docService = DocumentServiceStub()
        val searchIndex = SearchIndexStub()
        val coordinator = DocSearchCoordinator(docService, searchIndex)

        coordinator.createDocument("d1", "Kotlin Coroutines Guide", "Learn about structured concurrency")
        val results = searchIndex.search("kotlin")

        assertTrue(results.isNotEmpty(), "New document should be searchable immediately after creation")
        assertEquals("d1", results[0].docId, "Search result should match created document ID")
    }

    @Test
    fun test_document_delete_removes_from_search() {
        val docService = DocumentServiceStub()
        val searchIndex = SearchIndexStub()
        val coordinator = DocSearchCoordinator(docService, searchIndex)

        coordinator.createDocument("d1", "Kotlin Guide", "Content")
        coordinator.deleteDocument("d1")
        val results = searchIndex.search("kotlin")

        assertTrue(results.isEmpty(), "Deleted document should be removed from search index")
    }

    @Test
    fun test_document_update_refreshes_search() {
        val docService = DocumentServiceStub()
        val searchIndex = SearchIndexStub()
        val coordinator = DocSearchCoordinator(docService, searchIndex)

        coordinator.createDocument("d1", "Java Guide", "Java content")
        coordinator.updateDocument("d1", "Kotlin Guide", "Kotlin content")
        val javaResults = searchIndex.search("java")
        val kotlinResults = searchIndex.search("kotlin")

        assertTrue(javaResults.isEmpty(), "Old content should not be searchable after update")
        assertTrue(kotlinResults.isNotEmpty(), "Updated content should be searchable")
    }

    // =========================================================================
    // Billing → Notifications: Payment triggers notification
    // =========================================================================

    @Test
    fun test_billing_notification_on_payment() {
        // Payment event should trigger email notification
        val billing = BillingStub()
        val notifications = NotificationStub()
        val coordinator = BillingNotificationCoordinator(billing, notifications)

        coordinator.processPayment("user1", BigDecimal("99.99"))

        assertEquals(1, notifications.sentCount, "Payment should trigger exactly one notification")
        assertEquals("user1", notifications.lastRecipient, "Notification should be sent to paying user")
    }

    @Test
    fun test_billing_notification_tax_correct() {
        // K5: tax computation feeds into notification amount
        val billing = BillingStub()
        val notifications = NotificationStub()
        val coordinator = BillingNotificationCoordinator(billing, notifications)

        coordinator.processPaymentWithTax("user1", BigDecimal("100.00"), taxRate = BigDecimal("0.10"))

        // BUG: billing adds rate instead of multiplying
        assertEquals(
            BigDecimal("110.00"),
            notifications.lastAmount,
            "Notification should show correct taxed amount (100 * 1.10 = 110.00)"
        )
    }

    @Test
    fun test_billing_notification_null_safe() {
        // B5: null discount → NPE in billing → no notification sent
        val billing = BillingStub()
        val notifications = NotificationStub()
        val coordinator = BillingNotificationCoordinator(billing, notifications)

        val sent = coordinator.processMonthlyBilling("customer-null")
        assertTrue(sent, "Monthly billing with null discount should still send notification")
    }

    // =========================================================================
    // Auth → Collab: Token-based session management
    // =========================================================================

    @Test
    fun test_auth_collab_session_requires_valid_token() {
        // Valid token should create a collab session
        val auth = AuthStub()
        val collab = CollabStub()
        val coordinator = AuthCollabCoordinator(auth, collab)

        val token = auth.issueToken("editor1")
        val session = coordinator.joinDocument(token, "doc-123")

        assertNotNull(session, "Valid token should create collab session")
        assertEquals("doc-123", session.documentId)
    }

    @Test
    fun test_auth_collab_revoked_token_no_session() {
        // G1: stale delegation token allows session after revocation
        val auth = AuthStub()
        val collab = CollabStub()
        val coordinator = AuthCollabCoordinator(auth, collab)

        val token = auth.issueToken("editor1")
        coordinator.joinDocument(token, "doc-123") // first join cached
        auth.revokeToken(token)

        val session = coordinator.joinDocument(token, "doc-123")
        assertNull(session, "Revoked token should not allow collab session creation")
    }

    // =========================================================================
    // Gateway → Analytics: Request handling generates analytics
    // =========================================================================

    @Test
    fun test_gateway_analytics_request_tracked() = runTest {
        // Gateway request should generate analytics event
        val analytics = AnalyticsStub()
        val gateway = GatewayAnalyticsStub(analytics)

        gateway.handleRequest("/api/documents", "user1")
        gateway.handleRequest("/api/search", "user2")

        assertEquals(2, analytics.eventCount, "Each request should generate an analytics event")
    }

    @Test
    fun test_gateway_analytics_mdc_propagated() = runTest {
        // J1: MDC (traceId) should propagate through async analytics recording
        val analytics = AnalyticsStub()
        val gateway = GatewayAnalyticsStub(analytics)

        org.slf4j.MDC.put("traceId", "trace-999")
        gateway.handleRequestWithTrace("/api/docs", "user1")

        // BUG: MDC not propagated to async analytics recording
        assertEquals(
            "trace-999",
            analytics.lastTraceId,
            "Analytics event should carry the traceId from MDC"
        )
        org.slf4j.MDC.clear()
    }

    // =========================================================================
    // Graph → Embeddings: Knowledge graph feeds embedding computation
    // =========================================================================

    @Test
    fun test_graph_traversal_feeds_embeddings() = runTest {
        // Graph traversal finds related docs → embeddings computed for each
        val graph = GraphStub()
        val embeddings = EmbeddingStub()
        val coordinator = GraphEmbeddingCoordinator(graph, embeddings)

        graph.addEdge("doc1", "doc2")
        graph.addEdge("doc2", "doc3")

        val results = coordinator.computeRelatedEmbeddings("doc1")
        assertEquals(3, results.size, "Should compute embeddings for all reachable nodes")
    }

    @Test
    fun test_graph_deep_tree_embedding_bounded() = runTest {
        // K3: deep recursion in graph traversal → embedding computation
        val graph = GraphStub()
        val embeddings = EmbeddingStub()
        val coordinator = GraphEmbeddingCoordinator(graph, embeddings)

        // Create a deep chain
        for (i in 0..199) {
            graph.addEdge("node-$i", "node-${i + 1}")
        }

        val result = coordinator.computeRelatedEmbeddings("node-0")
        // BUG: unbounded recursion causes StackOverflow
        assertTrue(result.size <= 100, "Traversal should be bounded to prevent StackOverflow, got ${result.size}")
    }

    // =========================================================================
    // Config → Multiple Services: Configuration propagation
    // =========================================================================

    @Test
    fun test_config_missing_env_var_graceful() {
        // L2: missing DATABASE_URL should not crash
        val config = ConfigStub(envVars = emptyMap())
        val result = try {
            config.getDatabaseUrl()
            true
        } catch (e: Exception) {
            false
        }
        assertTrue(result, "Missing DATABASE_URL should use fallback, not crash")
    }

    @Test
    fun test_config_consul_retry_on_failure() {
        // L-category: consul failure should retry, not cache permanently
        val config = ConfigStub(consulAvailable = false)
        assertFalse(config.consulConfigLoaded, "Consul config should not be loaded when unavailable")
        config.consulAvailable = true
        config.retryConsulLoad()
        assertTrue(config.consulConfigLoaded, "Consul config should be loaded after retry")
    }

    // =========================================================================
    // Serialization consistency across services
    // =========================================================================

    @Test
    fun test_graph_search_serialization_consistent() {
        // C4/F3: Sealed class serialization must be consistent between graph and search
        val graphSerializer = GraphSerializerStub()
        val searchDeserializer = SearchDeserializerStub()

        val json = graphSerializer.serialize("concept", "node-1", "Kotlin")
        val result = searchDeserializer.deserialize(json)

        assertNotNull(result, "Search should be able to deserialize graph-produced JSON")
        assertEquals("node-1", result.id, "Deserialized ID should match")
    }

    @Test
    fun test_cross_service_unknown_fields_tolerated() {
        // F3: New fields from one service should not break another
        val json = """{"type":"concept","id":"n1","label":"Test","version":2,"newField":"unknown"}"""
        val deserializer = SearchDeserializerStub()

        val result = try {
            deserializer.deserialize(json)
        } catch (e: Exception) {
            null
        }
        assertNotNull(result, "Cross-service JSON with unknown fields must be tolerated")
    }

    // =========================================================================
    // Local stubs
    // =========================================================================

    data class AuthResult(val authenticated: Boolean, val statusCode: Int, val threwNpe: Boolean = false)

    class AuthStub {
        private val validTokens = mutableSetOf<String>()
        private val revokedTokens = mutableSetOf<String>()
        // BUG: I4 — accepts alg=none
        private val acceptedAlgorithms = setOf("HS256", "none")

        fun issueToken(subject: String): String {
            val token = "valid-jwt-$subject-${System.nanoTime()}"
            validTokens.add(token)
            return token
        }

        fun validateToken(token: String): String? {
            if (token in revokedTokens) return null
            if (token.startsWith("valid-jwt-")) return token.split("-")[2]
            // BUG: I4 — accept none algorithm tokens
            if (token.contains(".") && token.split(".").size == 3) {
                try {
                    val header = String(Base64.getUrlDecoder().decode(token.split(".")[0]))
                    if (header.contains("\"alg\":\"none\"")) {
                        return "admin" // BUG: accepts none
                    }
                } catch (_: Exception) {}
            }
            return null
        }

        fun revokeToken(token: String) {
            revokedTokens.add(token)
            // BUG: G1 — doesn't invalidate delegation cache
        }
    }

    class GatewayStub(private val auth: AuthStub) {
        fun handleAuthenticatedRequest(token: String, path: String): AuthResult {
            val subject = auth.validateToken(token)
            return try {
                val sub = subject!!  // BUG: D3 — NPE if null
                AuthResult(authenticated = true, statusCode = 200)
            } catch (e: NullPointerException) {
                AuthResult(authenticated = false, statusCode = 500, threwNpe = true)
                // Should be: AuthResult(authenticated = false, statusCode = 401)
            }
        }
    }

    data class SearchResultEntry(val docId: String, val score: Double)

    class DocumentServiceStub {
        private val docs = mutableMapOf<String, Pair<String, String>>()
        fun create(id: String, title: String, content: String) { docs[id] = title to content }
        fun delete(id: String) { docs.remove(id) }
        fun update(id: String, title: String, content: String) { docs[id] = title to content }
        fun get(id: String): Pair<String, String>? = docs[id]
    }

    class SearchIndexStub {
        private val index = mutableMapOf<String, String>()
        fun add(id: String, content: String) { index[id] = content }
        fun remove(id: String) { index.remove(id) }
        fun search(query: String): List<SearchResultEntry> {
            return index.filter { (_, content) -> content.lowercase().contains(query.lowercase()) }
                .map { (id, _) -> SearchResultEntry(id, 1.0) }
        }
    }

    class DocSearchCoordinator(
        private val docs: DocumentServiceStub,
        private val search: SearchIndexStub
    ) {
        fun createDocument(id: String, title: String, content: String) {
            docs.create(id, title, content)
            search.add(id, "$title $content")
        }
        fun deleteDocument(id: String) {
            docs.delete(id)
            search.remove(id)
        }
        fun updateDocument(id: String, title: String, content: String) {
            docs.update(id, title, content)
            search.remove(id)
            search.add(id, "$title $content")
        }
    }

    class BillingStub {
        fun calculateMonthlyBill(customerId: String): BigDecimal {
            val base = BigDecimal("29.99")
            val overage: BigDecimal? = null
            val discount: BigDecimal? = null
            // BUG: B5 — null.add() throws NPE
            return base.add(overage).subtract(discount).setScale(2, RoundingMode.HALF_UP)
        }

        fun applyTax(amount: BigDecimal, rate: BigDecimal): BigDecimal {
            // BUG: K5 — adds rate instead of multiplying
            return amount.add(rate).setScale(2, RoundingMode.HALF_UP)
        }
    }

    class NotificationStub {
        var sentCount = 0
        var lastRecipient: String? = null
        var lastAmount: BigDecimal? = null

        fun send(userId: String, message: String, amount: BigDecimal? = null) {
            sentCount++
            lastRecipient = userId
            lastAmount = amount
        }
    }

    class BillingNotificationCoordinator(
        private val billing: BillingStub,
        private val notifications: NotificationStub
    ) {
        fun processPayment(userId: String, amount: BigDecimal) {
            notifications.send(userId, "Payment of $amount received", amount)
        }

        fun processPaymentWithTax(userId: String, amount: BigDecimal, taxRate: BigDecimal) {
            val total = billing.applyTax(amount, taxRate)
            notifications.send(userId, "Payment of $total received (incl. tax)", total)
        }

        fun processMonthlyBilling(customerId: String): Boolean {
            return try {
                val bill = billing.calculateMonthlyBill(customerId)
                notifications.send(customerId, "Monthly bill: $bill", bill)
                true
            } catch (e: NullPointerException) {
                false // BUG: B5 NPE prevents notification
            }
        }
    }

    data class CollabSession(val userId: String, val documentId: String)

    class CollabStub {
        private val sessions = mutableListOf<CollabSession>()
        fun createSession(userId: String, docId: String): CollabSession {
            val session = CollabSession(userId, docId)
            sessions.add(session)
            return session
        }
    }

    class AuthCollabCoordinator(
        private val auth: AuthStub,
        private val collab: CollabStub
    ) {
        // BUG: G1 — delegation cache not cleared on revoke
        private val delegationCache = mutableMapOf<String, String>()

        fun joinDocument(token: String, docId: String): CollabSession? {
            // Check delegation cache first (G1 bug: stale after revoke)
            val cached = delegationCache[token]
            if (cached != null) {
                return collab.createSession(cached, docId)
            }

            val userId = auth.validateToken(token) ?: return null
            delegationCache[token] = userId
            return collab.createSession(userId, docId)
        }
    }

    class AnalyticsStub {
        var eventCount = 0
        var lastTraceId: String? = null

        fun recordEvent(eventType: String, userId: String, traceId: String? = null) {
            eventCount++
            lastTraceId = traceId
        }
    }

    class GatewayAnalyticsStub(private val analytics: AnalyticsStub) {
        fun handleRequest(path: String, userId: String) {
            analytics.recordEvent("request", userId)
        }

        suspend fun handleRequestWithTrace(path: String, userId: String) {
            // BUG: J1 — MDC not propagated to async
            withContext(Dispatchers.IO) {
                val traceId = org.slf4j.MDC.get("traceId") // BUG: null on IO dispatcher
                analytics.recordEvent("request", userId, traceId)
            }
        }
    }

    class GraphStub {
        private val edges = mutableMapOf<String, MutableList<String>>()
        fun addEdge(from: String, to: String) {
            edges.getOrPut(from) { mutableListOf() }.add(to)
        }
        fun getNeighbors(nodeId: String): List<String> = edges[nodeId] ?: emptyList()

        fun bfsAll(start: String): List<String> {
            val visited = mutableSetOf<String>()
            val queue = ArrayDeque<String>()
            queue.add(start)
            visited.add(start)
            while (queue.isNotEmpty()) {
                val current = queue.removeFirst()
                for (n in getNeighbors(current)) {
                    if (visited.add(n)) queue.add(n)
                }
            }
            return visited.toList()
        }
    }

    class EmbeddingStub {
        suspend fun compute(docId: String): List<Float> {
            delay(1)
            return List(10) { (Math.random() * 2 - 1).toFloat() }
        }
    }

    class GraphEmbeddingCoordinator(
        private val graph: GraphStub,
        private val embeddings: EmbeddingStub
    ) {
        suspend fun computeRelatedEmbeddings(startNodeId: String): List<Pair<String, List<Float>>> {
            val reachable = graph.bfsAll(startNodeId)
            // BUG: K3 — no depth bound, could be unbounded
            return reachable.map { nodeId ->
                nodeId to embeddings.compute(nodeId)
            }
        }
    }

    class ConfigStub(
        envVars: Map<String, String> = emptyMap(),
        var consulAvailable: Boolean = false
    ) {
        var consulConfigLoaded = false
        private val env = envVars.toMutableMap()

        init {
            if (consulAvailable) {
                consulConfigLoaded = true
            }
            // BUG: consul failure cached permanently, never retried
        }

        fun getDatabaseUrl(): String {
            return env["DATABASE_URL"]
                ?: throw IllegalStateException("DATABASE_URL not set") // BUG: should use fallback
        }

        fun retryConsulLoad() {
            // BUG: original code never retries — this simulates the fix
            if (consulAvailable) {
                consulConfigLoaded = true
            }
        }
    }

    data class NodeResult(val id: String, val label: String?)

    class GraphSerializerStub {
        fun serialize(type: String, id: String, label: String): String {
            // BUG: C4 — uses qualified name instead of @SerialName
            return """{"type":"$type","id":"$id","label":"$label"}"""
        }
    }

    class SearchDeserializerStub {
        fun deserialize(json: String): NodeResult? {
            // BUG: F3 — doesn't tolerate unknown fields
            val knownFields = setOf("type", "id", "label")
            val fieldPattern = """"(\w+)"\s*:""".toRegex()
            val fields = fieldPattern.findAll(json).map { it.groupValues[1] }.toSet()
            val unknown = fields - knownFields
            if (unknown.isNotEmpty()) {
                throw IllegalArgumentException("Unknown fields: $unknown") // BUG
            }
            val id = """"id"\s*:\s*"([^"]+)"""".toRegex().find(json)?.groupValues?.get(1)
            val label = """"label"\s*:\s*"([^"]+)"""".toRegex().find(json)?.groupValues?.get(1)
            return if (id != null) NodeResult(id, label) else null
        }
    }
}
