package com.pulsemap.unit

import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull

/**
 * Tests for Ktor pipeline behavior and Exposed transaction handling.
 *
 * Bug-specific tests:
 *   D1 - Auth interceptor doesn't return after 401 -> handler still executes
 *   D2 - Coroutine launched inside Exposed transaction block
 *   D3 - batchInsert uses RETURNING clause causing overhead
 *   D4 - Manual JSON parsing instead of call.receive<T>() content negotiation
 */
class KtorExposedTests {

    // =========================================================================
    // D1: Auth intercept doesn't return after unauthorized
    // =========================================================================

    @Test
    fun test_auth_intercept_returns() {
        
        // The next handler in the pipeline still executes
        val pipeline = SimulatedPipeline()
        pipeline.addInterceptor { ctx ->
            if (!ctx.isAuthenticated) {
                ctx.responseCode = 401
                ctx.responseBody = "Unauthorized"
                
            }
        }
        pipeline.addHandler { ctx ->
            ctx.responseCode = 200
            ctx.responseBody = "Secret Data"
            ctx.handlerCalled = true
        }

        val ctx = RequestContext(isAuthenticated = false)
        pipeline.execute(ctx)

        assertEquals(401, ctx.responseCode, "Unauthenticated request should get 401")
        assertFalse(ctx.handlerCalled, "Handler should NOT be called after 401 intercept")
    }

    @Test
    fun test_unauthorized_stops_pipeline() {
        
        val pipeline = SimulatedPipeline()
        pipeline.addInterceptor { ctx ->
            if (!ctx.isAuthenticated) {
                ctx.responseCode = 401
                ctx.responseBody = "Unauthorized"
                
            }
        }
        pipeline.addHandler { ctx ->
            ctx.responseBody = "Sensitive Resource"
            ctx.handlerCalled = true
        }

        val ctx = RequestContext(isAuthenticated = false)
        pipeline.execute(ctx)

        assertFalse(
            ctx.responseBody.contains("Sensitive"),
            "Sensitive data should not be returned for unauthorized request"
        )
    }

    // =========================================================================
    // D2: No coroutine in transaction
    // =========================================================================

    @Test
    fun test_no_coroutine_in_transaction() {
        
        // because the transaction context is thread-local and won't propagate
        val txSimulator = TransactionSimulator()
        val result = txSimulator.runWithCoroutineInTransaction()
        assertFalse(
            result.coroutineLaunched,
            "Should NOT launch coroutine inside transaction block"
        )
        assertTrue(result.success, "Transaction should complete without coroutine launch")
    }

    @Test
    fun test_transaction_scope_respected() {
        
        val txSimulator = TransactionSimulator()
        val result = txSimulator.runTransactionBoundaryCheck()
        assertTrue(
            result.allOpsOnSameThread,
            "All operations within transaction should run on the same thread"
        )
    }

    // =========================================================================
    // D3: batchInsert with RETURNING overhead
    // =========================================================================

    @Test
    fun test_batch_insert_no_returning() {
        
        // which adds RETURNING clause and eliminates batch optimization
        val inserter = BatchInserter()
        val result = inserter.performBatchInsert(count = 1000)
        assertFalse(
            result.usesReturningClause,
            "batchInsert should use shouldReturnGeneratedValues=false for performance"
        )
    }

    @Test
    fun test_bulk_insert_performance() {
        
        val inserter = BatchInserter()
        val result = inserter.performBatchInsert(count = 500)
        assertTrue(
            result.queryCount <= 5,
            "Bulk insert of 500 rows should use <= 5 queries, but used ${result.queryCount}"
        )
    }

    // =========================================================================
    // D4: Manual JSON parsing instead of call.receive<T>()
    // =========================================================================

    @Test
    fun test_uses_call_receive() {
        
        // which bypasses content negotiation, validation, and error handling
        val handler = RequestHandler()
        val result = handler.handleRequest("""{"id":"s1","value":42.0}""", contentType = "application/json")
        assertTrue(result.usedContentNegotiation, "Should use call.receive<T>(), not manual JSON parsing")
    }

    @Test
    fun test_content_type_validated() {
        
        val handler = RequestHandler()
        val result = handler.handleRequest("""not json at all""", contentType = "text/plain")
        assertEquals(
            415,
            result.statusCode,
            "Non-JSON content type should be rejected with 415 Unsupported Media Type"
        )
    }

    // =========================================================================
    // Baseline: Ktor routing and Exposed query fundamentals
    // =========================================================================

    @Test
    fun test_pipeline_executes_handler_for_authenticated_request() {
        val pipeline = SimulatedPipeline()
        pipeline.addInterceptor { ctx ->
            if (!ctx.isAuthenticated) {
                ctx.responseCode = 401
            }
        }
        pipeline.addHandler { ctx ->
            ctx.responseCode = 200
            ctx.responseBody = "OK"
            ctx.handlerCalled = true
        }
        val ctx = RequestContext(isAuthenticated = true)
        pipeline.execute(ctx)
        assertEquals(200, ctx.responseCode)
        assertTrue(ctx.handlerCalled)
    }

    @Test
    fun test_transaction_commit_on_success() {
        val tx = TransactionSimulator()
        val result = tx.runSimpleTransaction(shouldSucceed = true)
        assertTrue(result.committed, "Successful transaction should be committed")
        assertFalse(result.rolledBack, "Successful transaction should not be rolled back")
    }

    @Test
    fun test_transaction_rollback_on_failure() {
        val tx = TransactionSimulator()
        val result = tx.runSimpleTransaction(shouldSucceed = false)
        assertFalse(result.committed, "Failed transaction should not be committed")
        assertTrue(result.rolledBack, "Failed transaction should be rolled back")
    }

    @Test
    fun test_batch_insert_returns_count() {
        val inserter = BatchInserter()
        val result = inserter.performBatchInsert(count = 10)
        assertEquals(10, result.insertedCount, "Should insert exactly 10 records")
    }

    @Test
    fun test_request_handler_parses_valid_json() {
        val handler = RequestHandler()
        val result = handler.handleRequest("""{"id":"s1","value":1.0}""", contentType = "application/json")
        assertEquals(200, result.statusCode)
    }

    @Test
    fun test_request_handler_rejects_empty_body() {
        val handler = RequestHandler()
        val result = handler.handleRequest("", contentType = "application/json")
        assertEquals(400, result.statusCode, "Empty body should return 400")
    }

    @Test
    fun test_exposed_query_returns_results() {
        val queryResult = simulateExposedQuery("SELECT * FROM sensors WHERE id = ?", listOf("s1"))
        assertNotNull(queryResult)
        assertTrue(queryResult.isNotEmpty(), "Query should return results")
    }

    @Test
    fun test_exposed_query_parameterized() {
        val queryResult = simulateExposedQuery("SELECT * FROM sensors WHERE id = ?", listOf("s1"))
        assertNotNull(queryResult)
        // Parameterized queries should not be vulnerable to injection
    }

    @Test
    fun test_pipeline_multiple_interceptors_order() {
        val order = mutableListOf<String>()
        val pipeline = SimulatedPipeline()
        pipeline.addInterceptor { order.add("first") }
        pipeline.addInterceptor { order.add("second") }
        pipeline.addHandler { order.add("handler") }
        pipeline.execute(RequestContext(isAuthenticated = true))
        assertEquals(listOf("first", "second", "handler"), order)
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    data class RequestContext(
        val isAuthenticated: Boolean,
        var responseCode: Int = 0,
        var responseBody: String = "",
        var handlerCalled: Boolean = false
    )

    class SimulatedPipeline {
        private val interceptors = mutableListOf<(RequestContext) -> Unit>()
        private val handlers = mutableListOf<(RequestContext) -> Unit>()

        fun addInterceptor(interceptor: (RequestContext) -> Unit) {
            interceptors.add(interceptor)
        }

        fun addHandler(handler: (RequestContext) -> Unit) {
            handlers.add(handler)
        }

        fun execute(ctx: RequestContext) {
            
            for (interceptor in interceptors) {
                interceptor(ctx)
                
            }
            for (handler in handlers) {
                handler(ctx)
            }
        }
    }

    data class TransactionResult(
        val success: Boolean = false,
        val committed: Boolean = false,
        val rolledBack: Boolean = false,
        val coroutineLaunched: Boolean = false,
        val allOpsOnSameThread: Boolean = false
    )

    class TransactionSimulator {
        fun runWithCoroutineInTransaction(): TransactionResult {
            
            return TransactionResult(success = false, coroutineLaunched = true)
        }

        fun runTransactionBoundaryCheck(): TransactionResult {
            
            return TransactionResult(allOpsOnSameThread = false)
        }

        fun runSimpleTransaction(shouldSucceed: Boolean): TransactionResult {
            return if (shouldSucceed) {
                TransactionResult(success = true, committed = true, rolledBack = false)
            } else {
                TransactionResult(success = false, committed = false, rolledBack = true)
            }
        }
    }

    data class BatchInsertResult(
        val insertedCount: Int,
        val queryCount: Int,
        val usesReturningClause: Boolean
    )

    class BatchInserter {
        fun performBatchInsert(count: Int): BatchInsertResult {
            
            return BatchInsertResult(
                insertedCount = count,
                queryCount = count, 
                usesReturningClause = true 
            )
        }
    }

    data class HandlerResult(
        val statusCode: Int,
        val body: String = "",
        val usedContentNegotiation: Boolean = false
    )

    class RequestHandler {
        fun handleRequest(body: String, contentType: String): HandlerResult {
            
            if (body.isEmpty()) return HandlerResult(400, "Empty body")
            
            
            return try {
                HandlerResult(200, body, usedContentNegotiation = false) 
            } catch (e: Exception) {
                HandlerResult(500, e.message ?: "Error")
            }
        }
    }

    private fun simulateExposedQuery(sql: String, params: List<Any>): List<Map<String, Any>> {
        return listOf(mapOf("id" to "s1", "value" to 42.0))
    }
}
