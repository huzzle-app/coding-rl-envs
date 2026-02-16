package com.pulsemap.core

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.*

// =============================================================================
// Coroutine stubs: These simulate real buggy patterns from the PulseMap codebase.
// Bugs: A1 (runBlocking), A2 (GlobalScope), A3 (flowOn placement),
//        A4 (unbounded channel), A5 (async error swallowed)
// =============================================================================

data class RequestResult(val success: Boolean, val data: String = "")

/**
 * Handles incoming sensor data requests.
 *
 * BUG A1: Uses runBlocking inside a suspend function. In production, this blocks
 * the Ktor thread pool and can deadlock the event loop when all threads are blocked.
 */
class SensorHandler {
    suspend fun handleRequest(requestId: String): RequestResult {
        // BUG A1: runBlocking inside a suspend function blocks the calling thread.
        // In Ktor, the handler is already a coroutine; wrapping in runBlocking
        // creates a nested event loop that competes for the same thread.
        return runBlocking {
            delay(10)
            RequestResult(success = true, data = "processed $requestId")
        }
    }
}

/**
 * Background processing service for sensor data ingestion.
 *
 * BUG A2: Uses GlobalScope instead of structured concurrency. Coroutines launched
 * in GlobalScope are not cancelled when the parent scope is cancelled, leading to
 * resource leaks on shutdown.
 */
class IngestionServiceCoroutine {
    /** Tracks the background job so tests can verify cancellation behavior. */
    var backgroundJob: Job? = null

    /**
     * Start background processing. Should be cancellable via structured concurrency,
     * but GlobalScope prevents cancellation propagation.
     */
    suspend fun startBackgroundProcessing() {
        // BUG A2: GlobalScope escapes structured concurrency.
        // When the parent scope is cancelled, this coroutine keeps running.
        backgroundJob = GlobalScope.launch {
            while (true) {
                delay(100)
            }
        }
        // Simulate work that should be cancellable
        delay(5000)
    }
}

data class DispatcherInfo(val flowOnBeforeCollect: Boolean, val dispatcherName: String = "")

/**
 * Processes sensor data using Kotlin Flows.
 *
 * BUG A3: flowOn is placed after collect, which has no effect. The flowOn operator
 * only affects upstream operators (those before it in the chain).
 */
class SensorFlowProcessor {
    /**
     * Compute heatmap from sensor IDs using Flow.
     * The flow should run on Dispatchers.IO but due to incorrect flowOn placement,
     * it runs on the calling dispatcher.
     */
    suspend fun computeHeatmap(sensorIds: List<String>): List<Double> {
        val results = mutableListOf<Double>()

        flow {
            for (id in sensorIds) {
                emit(fetchSensorValue(id))
                delay(10)
            }
        }
        .collect { value ->
            results.add(value)
        }
        // BUG A3: flowOn placed AFTER collect has no effect.
        // It should be: .flowOn(Dispatchers.IO).collect { ... }
        // .flowOn(Dispatchers.Default) // commented out, wrong placement

        return results
    }

    /**
     * Get thread name where flow emissions happen.
     * Should be IO/Default dispatcher but is actually the calling thread.
     */
    suspend fun getEmissionThreadName(): String {
        var threadName = ""
        flow {
            threadName = Thread.currentThread().name
            emit(1)
        }
        .collect { }
        // BUG A3: flowOn after collect doesn't change emission dispatcher
        // .flowOn(Dispatchers.IO)
        return threadName
    }

    private suspend fun fetchSensorValue(sensorId: String): Double {
        delay(5)
        return Math.random() * 100
    }
}

data class BurstResult(val peakBuffered: Int, val allProcessed: Boolean)

/**
 * Processes sensor data through a channel.
 *
 * BUG A4: Uses Channel.UNLIMITED capacity, which means under burst load
 * the channel buffer grows without bound, potentially causing OOM.
 */
class ChannelProcessor {
    // BUG A4: Channel.UNLIMITED means no backpressure - buffer grows without bound
    private val channel = Channel<Int>(Channel.UNLIMITED)

    fun getChannelCapacity(): Int = Channel.UNLIMITED

    suspend fun simulateBurst(messageCount: Int): BurstResult {
        var peakBuffered = 0
        var processed = 0
        val sendJob = CoroutineScope(Dispatchers.Default).launch {
            for (i in 1..messageCount) {
                channel.send(i)
            }
        }
        // Under UNLIMITED capacity, all messages are buffered immediately
        // With bounded capacity, the sender would suspend when buffer is full
        sendJob.join()
        peakBuffered = messageCount // All buffered at once with UNLIMITED

        val receiveJob = CoroutineScope(Dispatchers.Default).launch {
            repeat(messageCount) {
                channel.receive()
                processed++
            }
        }
        receiveJob.join()

        return BurstResult(
            peakBuffered = peakBuffered,
            allProcessed = processed == messageCount
        )
    }
}

data class AsyncResult(val errorPropagated: Boolean, val awaitCalled: Boolean)

/**
 * Handles async operations with error propagation.
 *
 * BUG A5: async { } launches a deferred computation, but if await() is never called,
 * the exception from the async block is silently lost (in structured concurrency
 * with SupervisorJob) or causes unexpected crashes.
 */
class AsyncErrorHandler {
    /**
     * Run an async computation that throws an error.
     * The error should propagate to the caller, but it doesn't because
     * await() is never called on the Deferred result.
     */
    suspend fun runAsyncWithError(): AsyncResult {
        var errorPropagated = false
        try {
            coroutineScope {
                val deferred = async {
                    throw IllegalStateException("geocoding failed")
                }
                // BUG A5: Never calling await() means the exception is silently lost
                // The deferred result is discarded
                "Unknown Location" // Returns fallback instead of awaiting result
            }
        } catch (e: Exception) {
            // With structured concurrency (coroutineScope), the exception actually
            // does propagate even without await. But with SupervisorJob it wouldn't.
            errorPropagated = true
        }
        // BUG: In the production code (GeocodingService), the error is swallowed
        // because the Deferred is never awaited
        return AsyncResult(errorPropagated = false, awaitCalled = false)
    }

    /**
     * Check whether await() is properly called on deferred results.
     */
    suspend fun checkAwaitCalled(): AsyncResult {
        var awaitWasCalled = false
        coroutineScope {
            val deferred = async {
                delay(10)
                42
            }
            // BUG A5: Should call deferred.await() but doesn't
            // val result = deferred.await()
            // awaitWasCalled = true
        }
        return AsyncResult(errorPropagated = false, awaitCalled = awaitWasCalled)
    }
}
