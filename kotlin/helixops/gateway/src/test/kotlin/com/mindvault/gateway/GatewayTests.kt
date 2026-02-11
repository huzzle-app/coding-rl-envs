package com.helixops.gateway

import kotlinx.coroutines.*
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import java.io.File
import java.net.URL
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertFailsWith

/**
 * Tests for the Gateway service: request handling, error handling, security.
 *
 * Bug-specific tests:
 *   A1 - runBlocking inside Ktor handler deadlocks the event loop
 *   A2 - GlobalScope.launch not tied to application lifecycle
 *   D1 - StatusPages catches CancellationException, breaking structured concurrency
 *   D2 - Double respond (call.respondText called twice)
 *   I1 - SQL injection via string interpolation in search query
 *   I2 - Path traversal in file serving endpoint (no canonicalization)
 *   I3 - SSRF: webhook URL not validated, allows internal network access
 */
class GatewayTests {

    // =========================================================================
    // A1: runBlocking in handler
    // =========================================================================

    @Test
    fun test_no_run_blocking_in_handler() = runTest {
        
        // that the outer coroutine needs to resume on
        val gateway = GatewayServiceFixture()
        assertFalse(
            gateway.handlerUsesRunBlocking(),
            "Handler should NOT use runBlocking inside coroutine context; use suspend functions"
        )
    }

    @Test
    fun test_concurrent_requests_no_deadlock() = runTest {
        
        val gateway = GatewayServiceFixture()
        val results = (1..10).map { i ->
            async {
                gateway.handleDocumentRequest("doc-$i")
            }
        }
        val responses = results.map { it.await() }
        assertEquals(10, responses.size, "All 10 concurrent requests should complete without deadlock")
        assertTrue(responses.all { it.success }, "All requests should succeed")
    }

    // =========================================================================
    // A2: GlobalScope usage
    // =========================================================================

    @Test
    fun test_no_global_scope() {
        
        // Coroutines are not tied to application lifecycle
        val gateway = GatewayServiceFixture()
        assertFalse(
            gateway.usesGlobalScope(),
            "Background tasks should use structured concurrency, not GlobalScope"
        )
    }

    @Test
    fun test_coroutine_tied_to_lifecycle() = runTest {
        
        val gateway = GatewayServiceFixture()
        val scope = CoroutineScope(Dispatchers.Default + Job())
        var backgroundCancelled = false

        val job = scope.launch {
            try {
                gateway.startBackgroundTasks()
            } catch (e: CancellationException) {
                backgroundCancelled = true
                throw e
            }
        }

        delay(50)
        scope.cancel()
        job.join()

        assertTrue(
            backgroundCancelled,
            "Background tasks should be cancelled when application scope is cancelled"
        )
    }

    // =========================================================================
    // D1: StatusPages catches CancellationException
    // =========================================================================

    @Test
    fun test_cancellation_not_caught() {
        
        // This breaks structured concurrency
        val gateway = GatewayServiceFixture()
        val config = gateway.getStatusPagesConfig()
        assertTrue(
            config.rethrowsCancellation,
            "StatusPages should rethrow CancellationException, not handle it"
        )
    }

    @Test
    fun test_status_pages_rethrows_cancel() = runTest {
        
        val gateway = GatewayServiceFixture()
        assertFailsWith<CancellationException> {
            gateway.simulateStatusPagesHandler(CancellationException("cancelled"))
        }
    }

    // =========================================================================
    // D2: Double respond
    // =========================================================================

    @Test
    fun test_single_respond_per_call() {
        
        val gateway = GatewayServiceFixture()
        val result = gateway.handleHealthCheck()
        assertEquals(
            1,
            result.respondCount,
            "Handler should call respond exactly once, not ${result.respondCount} times"
        )
    }

    @Test
    fun test_no_double_respond() {
        
        val gateway = GatewayServiceFixture()
        val result = gateway.handleHealthCheck()
        assertFalse(
            result.threwDoubleRespond,
            "Handler should not attempt to respond twice"
        )
        assertTrue(
            result.success,
            "Health check should succeed with a single response"
        )
    }

    // =========================================================================
    // I1: SQL injection
    // =========================================================================

    @Test
    fun test_sql_injection_prevented() {
        
        val gateway = GatewayServiceFixture()
        val maliciousQuery = "'; DROP TABLE documents; --"
        val result = gateway.search(maliciousQuery)
        assertFalse(
            result.queryExecuted.contains("DROP TABLE"),
            "SQL injection should be prevented by parameterized queries"
        )
    }

    @Test
    fun test_exposed_dsl_parameterized() {
        
        val gateway = GatewayServiceFixture()
        val result = gateway.search("normal query")
        assertTrue(
            result.usedParameterized,
            "Search should use parameterized query via Exposed DSL"
        )
    }

    // =========================================================================
    // I2: Path traversal
    // =========================================================================

    @Test
    fun test_path_traversal_blocked() {
        
        val gateway = GatewayServiceFixture()
        val maliciousPaths = listOf(
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config",
            "uploads/../../../etc/shadow",
            "..%2F..%2Fetc%2Fpasswd"
        )
        for (path in maliciousPaths) {
            val result = gateway.getFile(path)
            assertFalse(
                result.served,
                "Path traversal should be blocked for: $path"
            )
        }
    }

    @Test
    fun test_canonical_path_checked() {
        
        val gateway = GatewayServiceFixture()
        val result = gateway.getFile("../secret.txt")
        assertTrue(
            result.pathCanonicalized,
            "File path should be canonicalized and checked against allowed base directory"
        )
    }

    // =========================================================================
    // I3: SSRF
    // =========================================================================

    @Test
    fun test_ssrf_internal_blocked() {
        
        val gateway = GatewayServiceFixture()
        val internalUrls = listOf(
            "http://localhost:8500/v1/kv/secret",
            "http://127.0.0.1:5432/",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1:6379/",
            "http://192.168.1.1/"
        )
        for (url in internalUrls) {
            val result = gateway.testWebhook(url)
            assertFalse(
                result.requestSent,
                "SSRF should block internal URL: $url"
            )
        }
    }

    @Test
    fun test_webhook_url_validated() {
        
        val gateway = GatewayServiceFixture()
        val result = gateway.testWebhook("http://example.com/webhook")
        assertTrue(
            result.urlValidated,
            "Webhook URL should be validated before sending request"
        )
    }

    // =========================================================================
    // Baseline: Gateway fundamentals
    // =========================================================================

    @Test
    fun test_health_check_returns_ok() {
        val gateway = GatewayServiceFixture()
        val result = gateway.handleHealthCheck()
        assertEquals("OK", result.body, "Health check should return 'OK'")
    }

    @Test
    fun test_document_request_returns_data() = runTest {
        val gateway = GatewayServiceFixture()
        val result = gateway.handleDocumentRequest("doc-1")
        assertTrue(result.success, "Document request should succeed")
        assertTrue(result.body.contains("doc-1"), "Response should contain document ID")
    }

    @Test
    fun test_search_normal_query() {
        val gateway = GatewayServiceFixture()
        val result = gateway.search("kotlin coroutines")
        assertTrue(result.results.isNotEmpty(), "Normal search should return results")
    }

    @Test
    fun test_get_valid_file() {
        val gateway = GatewayServiceFixture()
        val result = gateway.getFile("readme.txt")
        assertTrue(result.served, "Valid file path should be served")
    }

    @Test
    fun test_webhook_external_url() {
        val gateway = GatewayServiceFixture()
        val result = gateway.testWebhook("https://hooks.slack.com/services/xxx")
        assertTrue(result.requestSent, "External webhook URL should be allowed")
    }

    @Test
    fun test_missing_document_returns_error() = runTest {
        val gateway = GatewayServiceFixture()
        val result = gateway.handleDocumentRequest("")
        assertFalse(result.success, "Empty document ID should fail")
    }

    @Test
    fun test_search_empty_query() {
        val gateway = GatewayServiceFixture()
        val result = gateway.search("")
        assertNotNull(result, "Empty search query should return a result (possibly empty)")
    }

    @Test
    fun test_status_pages_handles_runtime_exception() {
        val gateway = GatewayServiceFixture()
        val result = gateway.simulateStatusPagesHandlerSafe(RuntimeException("test error"))
        assertEquals(500, result.statusCode, "RuntimeException should map to 500")
    }

    @Test
    fun test_status_pages_handles_not_found() {
        val gateway = GatewayServiceFixture()
        val result = gateway.simulateStatusPagesHandlerSafe(NoSuchElementException("not found"))
        assertEquals(404, result.statusCode, "NoSuchElementException should map to 404")
    }

    @Test
    fun test_get_file_returns_not_found() {
        val gateway = GatewayServiceFixture()
        val result = gateway.getFile("nonexistent-file.txt")
        // Non-traversal but nonexistent file should return a clear not-found
        assertNotNull(result, "Should return a result even for missing files")
    }

    @Test
    fun test_search_with_special_characters() {
        val gateway = GatewayServiceFixture()
        val result = gateway.search("test & query <script>")
        assertNotNull(result, "Search with special characters should return a result")
    }

    @Test
    fun test_file_path_with_subdirectory() {
        val gateway = GatewayServiceFixture()
        val result = gateway.getFile("subdir/file.txt")
        assertTrue(result.served, "File in subdirectory should be accessible")
    }

    @Test
    fun test_webhook_https_url() {
        val gateway = GatewayServiceFixture()
        val result = gateway.testWebhook("https://api.example.com/callback")
        assertTrue(result.requestSent, "HTTPS external URLs should be allowed")
    }

    @Test
    fun test_concurrent_search_requests() = runTest {
        val gateway = GatewayServiceFixture()
        val results = (1..5).map { i ->
            async { gateway.search("query_$i") }
        }.map { it.await() }
        assertEquals(5, results.size, "All concurrent search requests should complete")
    }

    @Test
    fun test_path_with_encoded_slashes() {
        val gateway = GatewayServiceFixture()
        val result = gateway.getFile("dir%2Ffile.txt")
        // URL-encoded slashes should be treated carefully
        assertNotNull(result, "Encoded path should return a result")
    }

    @Test
    fun test_health_check_body_not_empty() {
        val gateway = GatewayServiceFixture()
        val result = gateway.handleHealthCheck()
        assertTrue(result.body.isNotEmpty(), "Health check body should not be empty")
    }

    @Test
    fun test_search_returns_list() {
        val gateway = GatewayServiceFixture()
        val result = gateway.search("test query")
        assertNotNull(result.results, "Search should return a non-null results list")
        assertTrue(result.results is List, "Search results should be a list")
    }

    @Test
    fun test_webhook_empty_url_handled() {
        val gateway = GatewayServiceFixture()
        val result = gateway.testWebhook("")
        assertNotNull(result, "Webhook with empty URL should return a result, not throw")
    }

    @Test
    fun test_document_request_with_special_id() = runTest {
        val gateway = GatewayServiceFixture()
        val result = gateway.handleDocumentRequest("doc-with-dashes-123")
        assertTrue(result.success, "Document request with dashes in ID should succeed")
    }

    @Test
    fun test_status_pages_handles_illegal_argument() {
        val gateway = GatewayServiceFixture()
        val result = gateway.simulateStatusPagesHandlerSafe(IllegalArgumentException("bad input"))
        assertEquals(500, result.statusCode, "IllegalArgumentException should map to 500")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    data class RequestResult(val success: Boolean, val body: String = "")
    data class HealthResult(val success: Boolean, val body: String, val respondCount: Int, val threwDoubleRespond: Boolean)
    data class SearchResult(val queryExecuted: String, val usedParameterized: Boolean, val results: List<String>)
    data class FileResult(val served: Boolean, val pathCanonicalized: Boolean, val statusCode: Int = 200)
    data class WebhookResult(val requestSent: Boolean, val urlValidated: Boolean)
    data class StatusPagesConfig(val rethrowsCancellation: Boolean)
    data class ErrorResult(val statusCode: Int, val message: String)

    class GatewayServiceFixture {

        
        fun handlerUsesRunBlocking(): Boolean = true 

        suspend fun handleDocumentRequest(id: String): RequestResult {
            if (id.isEmpty()) return RequestResult(success = false, body = "Missing id")
            
            return try {
                runBlocking {
                    delay(10)
                    RequestResult(success = true, body = """{"id":"$id","title":"Document $id"}""")
                }
            } catch (e: Exception) {
                RequestResult(success = false, body = e.message ?: "error")
            }
        }

        
        fun usesGlobalScope(): Boolean = true 

        suspend fun startBackgroundTasks() {
            delay(5000) // Simulates long-running background work
        }

        
        fun getStatusPagesConfig(): StatusPagesConfig {
            return StatusPagesConfig(
                rethrowsCancellation = false 
            )
        }

        fun simulateStatusPagesHandler(exception: Throwable) {
            
            if (exception is CancellationException) {
                
                // Simulating the bug by NOT rethrowing
                // In fixed code, this should: throw exception
            }
            // Handle other exceptions normally
        }

        fun simulateStatusPagesHandlerSafe(exception: Throwable): ErrorResult {
            return when (exception) {
                is NoSuchElementException -> ErrorResult(404, exception.message ?: "Not found")
                else -> ErrorResult(500, exception.message ?: "Internal error")
            }
        }

        
        fun handleHealthCheck(): HealthResult {
            
            return HealthResult(
                success = false, 
                body = "OK",
                respondCount = 2, 
                threwDoubleRespond = true 
            )
        }

        
        fun search(query: String): SearchResult {
            val sql = "SELECT * FROM documents WHERE title LIKE '%$query%'" 
            return SearchResult(
                queryExecuted = sql,
                usedParameterized = false, 
                results = listOf("result1", "result2")
            )
        }

        
        fun getFile(path: String): FileResult {
            val containsTraversal = path.contains("..") || path.contains("%2F") || path.startsWith("/")
            if (containsTraversal) {
                
                return FileResult(
                    served = true, 
                    pathCanonicalized = false, 
                    statusCode = 200 
                )
            }
            return FileResult(served = true, pathCanonicalized = true)
        }

        
        fun testWebhook(url: String): WebhookResult {
            val isInternal = url.contains("localhost") ||
                url.contains("127.0.0.1") ||
                url.contains("169.254.") ||
                url.contains("10.0.") ||
                url.contains("192.168.")

            return if (isInternal) {
                WebhookResult(
                    requestSent = true,
                    urlValidated = false
                )
            } else {
                WebhookResult(requestSent = true, urlValidated = true)
            }
        }
    }

    // =========================================================================
    // Multi-step: Request pipeline rate limit before auth + off-by-one
    // =========================================================================

    @Test
    fun test_pipeline_auth_before_rate_limit() {
        val fixture = RequestPipelineFixture()
        val result = fixture.processRequest(
            path = "/api/data",
            authToken = null,
            requestCount = 5,
            maxRequests = 10
        )
        assertEquals(
            401, result["status"],
            "Unauthenticated requests should get 401, not be rate-limited first"
        )
    }

    @Test
    fun test_pipeline_rate_limit_boundary() {
        val fixture = RequestPipelineFixture()
        val result = fixture.processRequest(
            path = "/api/data",
            authToken = "Bearer valid-token",
            requestCount = 10,
            maxRequests = 10
        )
        assertEquals(
            429, result["status"],
            "Request at exactly max limit should be rate-limited (>= not >)"
        )
    }

    @Test
    fun test_pipeline_under_limit_succeeds() {
        val fixture = RequestPipelineFixture()
        val result = fixture.processRequest(
            path = "/api/data",
            authToken = "Bearer valid-token",
            requestCount = 5,
            maxRequests = 10
        )
        assertEquals(200, result["status"], "Authenticated request under limit should succeed")
    }

    // =========================================================================
    // Concurrency: Sliding window rate limiter poisons window with rejects
    // =========================================================================

    @Test
    fun test_rate_limit_recovers_after_window() {
        val fixture = SlidingWindowRateLimiterFixture()
        assertTrue(fixture.checkRateLimit("client1", 0, 1000, 2))
        assertTrue(fixture.checkRateLimit("client1", 100, 1000, 2))
        assertFalse(fixture.checkRateLimit("client1", 200, 1000, 2))
        assertFalse(fixture.checkRateLimit("client1", 300, 1000, 2))
        assertTrue(fixture.checkRateLimit("client1", 1200, 1000, 2),
            "Rate limiter should recover after rejected requests expire from window")
    }

    @Test
    fun test_rate_limit_allows_up_to_max() {
        val fixture = SlidingWindowRateLimiterFixture()
        assertTrue(fixture.checkRateLimit("client1", 0, 1000, 3))
        assertTrue(fixture.checkRateLimit("client1", 100, 1000, 3))
        assertTrue(fixture.checkRateLimit("client1", 200, 1000, 3))
        assertFalse(fixture.checkRateLimit("client1", 300, 1000, 3),
            "Fourth request within window should be rate limited")
    }

    @Test
    fun test_rate_limit_per_client() {
        val fixture = SlidingWindowRateLimiterFixture()
        assertTrue(fixture.checkRateLimit("client1", 0, 1000, 1))
        assertFalse(fixture.checkRateLimit("client1", 100, 1000, 1))
        assertTrue(fixture.checkRateLimit("client2", 100, 1000, 1),
            "Different clients should have independent rate limits")
    }

    // =========================================================================
    // Integration: Canonical request path encoding
    // =========================================================================

    @Test
    fun test_canonical_request_preserves_path_separators() {
        val fixture = CanonicalRequestFixture()
        val result = fixture.buildCanonical("GET", "/api/v1/users", emptyMap())
        assertTrue(result.contains("/api/v1/users"),
            "Path separators should be preserved in canonical request, not encoded as %2F")
    }

    @Test
    fun test_canonical_request_sorts_params() {
        val fixture = CanonicalRequestFixture()
        val params = mapOf("z" to listOf("1"), "a" to listOf("2"))
        val result = fixture.buildCanonical("POST", "/api", params)
        val paramLine = result.split("\n").last()
        assertEquals("a=2&z=1", paramLine, "Query parameters should be sorted by key")
    }

    @Test
    fun test_canonical_request_encodes_special_chars_in_segments() {
        val fixture = CanonicalRequestFixture()
        val result = fixture.buildCanonical("GET", "/api/my docs/file", emptyMap())
        assertTrue(result.contains("/api/my+docs/file") || result.contains("/api/my%20docs/file"),
            "Path segments should be individually encoded but slashes preserved")
    }

    class RequestPipelineFixture {
        fun processRequest(
            path: String,
            authToken: String?,
            requestCount: Int,
            maxRequests: Int
        ): Map<String, Any> {
            if (requestCount > maxRequests) {
                return mapOf("status" to 429, "error" to "Rate limited")
            }
            val isAuthenticated = authToken != null && authToken.startsWith("Bearer ")
            if (!isAuthenticated) {
                return mapOf("status" to 401, "error" to "Unauthorized")
            }
            return mapOf("status" to 200, "path" to path)
        }
    }

    class SlidingWindowRateLimiterFixture {
        private val requestTimestamps = mutableMapOf<String, MutableList<Long>>()

        fun checkRateLimit(clientId: String, currentTimeMs: Long, windowMs: Long, maxRequests: Int): Boolean {
            val timestamps = requestTimestamps.getOrPut(clientId) { mutableListOf() }
            timestamps.removeIf { it < currentTimeMs - windowMs }
            val allowed = timestamps.size < maxRequests
            timestamps.add(currentTimeMs)
            return allowed
        }
    }

    class CanonicalRequestFixture {
        fun buildCanonical(
            method: String,
            path: String,
            queryParams: Map<String, List<String>>
        ): String {
            val encodedPath = java.net.URLEncoder.encode(path, "UTF-8")
            val sortedParams = queryParams.entries
                .sortedBy { it.key }
                .flatMap { (key, values) -> values.sorted().map { "$key=$it" } }
                .joinToString("&")
            return "$method\n$encodedPath\n$sortedParams"
        }
    }
}
