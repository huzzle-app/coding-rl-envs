package com.pulsemap.core

// =============================================================================
// Ktor/Exposed framework stubs: Simulate pipeline and transaction bugs.
// Bugs: D1 (auth intercept doesn't return), D2 (coroutine in transaction),
//        D3 (batchInsert RETURNING overhead), D4 (manual JSON parsing)
// =============================================================================

data class RequestContext(
    val isAuthenticated: Boolean,
    var responseCode: Int = 0,
    var responseBody: String = "",
    var handlerCalled: Boolean = false
)

/**
 * Simulates Ktor's pipeline interceptor chain.
 *
 * BUG D1: When an interceptor responds with 401, it does NOT stop the pipeline.
 * The subsequent handlers still execute, potentially leaking sensitive data
 * to unauthenticated requests.
 */
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
        // BUG D1: Interceptors don't stop the pipeline even when they set a response.
        // After an interceptor sends 401, processing should stop.
        // But here, ALL interceptors AND handlers run regardless.
        for (interceptor in interceptors) {
            interceptor(ctx)
            // BUG: Missing check for ctx.responseCode != 0 to short-circuit
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

/**
 * Simulates Exposed transaction behavior.
 *
 * BUG D2: A coroutine is launched inside the transaction block. The coroutine
 * runs asynchronously and outlives the transaction scope. By the time it executes,
 * TransactionManager.current() is null, causing the coroutine to fail.
 */
class TransactionSimulator {
    /**
     * BUG D2: Launching a coroutine inside transaction{} is problematic because
     * the transaction context is thread-local and won't propagate to the coroutine.
     */
    fun runWithCoroutineInTransaction(): TransactionResult {
        // BUG D2: Simulates launching GlobalScope.launch inside transaction{}
        return TransactionResult(success = false, coroutineLaunched = true)
    }

    /**
     * BUG D2: Operations within a transaction should all run on the same thread.
     * When coroutines are launched, they switch threads and lose the transaction context.
     */
    fun runTransactionBoundaryCheck(): TransactionResult {
        // BUG D2: Not all ops on same thread due to coroutine dispatch
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

/**
 * Simulates Exposed batchInsert behavior.
 *
 * BUG D3: batchInsert defaults to shouldReturnGeneratedValues=true, which adds
 * RETURNING * to every INSERT statement. This forces each row to be inserted
 * individually (one query per row) instead of batching.
 */
class BatchInserter {
    fun performBatchInsert(count: Int): BatchInsertResult {
        // BUG D3: Without shouldReturnGeneratedValues=false, each row gets its own
        // INSERT with RETURNING *, losing the batch optimization entirely.
        return BatchInsertResult(
            insertedCount = count,
            queryCount = count,    // BUG: One query per row instead of batched
            usesReturningClause = true  // BUG: Should be false for performance
        )
    }
}

data class HandlerResult(
    val statusCode: Int,
    val body: String = "",
    val usedContentNegotiation: Boolean = false
)

/**
 * Simulates Ktor request handling.
 *
 * BUG D4: Uses manual JSON parsing (call.receiveText() + Json.decodeFromString)
 * instead of call.receive<T>() which uses Ktor's content negotiation pipeline.
 * This bypasses content type validation, error handling, and serialization config.
 */
class RequestHandler {
    fun handleRequest(body: String, contentType: String): HandlerResult {
        if (body.isEmpty()) return HandlerResult(400, "Empty body")
        // BUG D4: Doesn't check content type. With call.receive<T>(), Ktor would
        // automatically reject non-JSON content types with 415.
        // Also doesn't use content negotiation pipeline.
        return try {
            HandlerResult(200, body, usedContentNegotiation = false)
        } catch (e: Exception) {
            HandlerResult(500, e.message ?: "Error")
        }
    }
}
