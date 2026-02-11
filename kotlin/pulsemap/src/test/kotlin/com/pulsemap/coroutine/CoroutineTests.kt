package com.pulsemap.coroutine

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertFailsWith

/**
 * Tests for coroutine correctness: runBlocking misuse, GlobalScope leaks,
 * flowOn placement, channel backpressure, and async error propagation.
 *
 * Bug-specific tests:
 *   A1 - runBlocking used inside Ktor handler (deadlocks the event loop)
 *   A2 - GlobalScope used instead of structured concurrency
 *   A3 - flowOn placed after collect (has no effect)
 *   A4 - Unbounded channel causes OOM under burst
 *   A5 - async error swallowed when await() is never called
 */
class CoroutineTests {

    // =========================================================================
    // A1: runBlocking in handler
    // =========================================================================

    @Test
    fun test_no_run_blocking_in_handler() = runTest {
        
        // because it blocks the thread the outer coroutine needs
        val handler = SensorHandler()
        val usesRunBlocking = handler.usesRunBlocking()
        assertFalse(
            usesRunBlocking,
            "Handler should NOT use runBlocking inside coroutine context"
        )
    }

    @Test
    fun test_concurrent_requests_no_deadlock() = runTest {
        
        val handler = SensorHandler()
        val results = (1..10).map { i ->
            async {
                handler.handleRequest("request-$i")
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
    fun test_no_global_scope() = runTest {
        
        // and won't be cancelled when the parent scope is cancelled
        val ingestionService = IngestionService()
        assertFalse(
            ingestionService.usesGlobalScope(),
            "Service should use structured concurrency, not GlobalScope"
        )
    }

    @Test
    fun test_coroutine_cancelled_on_shutdown() = runTest {
        
        val scope = CoroutineScope(Dispatchers.Default + Job())
        val ingestionService = IngestionService()
        var jobCompleted = false
        var jobCancelled = false

        val job = scope.launch {
            try {
                ingestionService.startBackgroundProcessing()
                jobCompleted = true
            } catch (e: CancellationException) {
                jobCancelled = true
                throw e
            }
        }

        delay(50)
        scope.cancel()
        job.join()

        assertTrue(
            jobCancelled || !jobCompleted,
            "Background job should be cancelled when scope is cancelled"
        )
    }

    // =========================================================================
    // A3: flowOn placement
    // =========================================================================

    @Test
    fun test_flow_on_before_collect() = runTest {
        
        val processor = SensorFlowProcessor()
        val dispatcherInfo = processor.getFlowDispatcherInfo()
        assertTrue(
            dispatcherInfo.flowOnBeforeCollect,
            "flowOn should be applied BEFORE collect, not after"
        )
    }

    @Test
    fun test_flow_runs_on_correct_dispatcher() = runTest {
        
        val processor = SensorFlowProcessor()
        val threadName = processor.getEmissionThreadName()
        assertTrue(
            threadName.contains("IO") || threadName.contains("DefaultDispatcher"),
            "Flow should emit on IO dispatcher, but was on: $threadName"
        )
    }

    // =========================================================================
    // A4: Channel backpressure
    // =========================================================================

    @Test
    fun test_channel_bounded() = runTest {
        
        val channelProcessor = ChannelProcessor()
        val capacity = channelProcessor.getChannelCapacity()
        assertTrue(
            capacity in 1..1000,
            "Channel should have bounded capacity, but capacity was $capacity (UNLIMITED = ${Channel.UNLIMITED})"
        )
    }

    @Test
    fun test_backpressure_under_burst() = runTest {
        
        val channelProcessor = ChannelProcessor()
        val result = channelProcessor.simulateBurst(messageCount = 10000)
        assertTrue(
            result.peakBuffered <= 1000,
            "Peak buffered should be bounded, but was ${result.peakBuffered}"
        )
        assertTrue(result.allProcessed, "All messages should eventually be processed")
    }

    // =========================================================================
    // A5: Async error propagation
    // =========================================================================

    @Test
    fun test_async_error_propagated() = runTest {
        
        val errorHandler = AsyncErrorHandler()
        val result = errorHandler.runAsyncWithError()
        assertTrue(
            result.errorPropagated,
            "Error from async block should propagate to parent scope"
        )
    }

    @Test
    fun test_deferred_await_called() = runTest {
        
        val errorHandler = AsyncErrorHandler()
        val result = errorHandler.checkAwaitCalled()
        assertTrue(
            result.awaitCalled,
            "Deferred.await() must be called to observe the result/exception"
        )
    }

    // =========================================================================
    // Baseline: Coroutine fundamentals
    // =========================================================================

    @Test
    fun test_coroutine_scope_structured() = runTest {
        var innerCompleted = false
        coroutineScope {
            launch {
                delay(10)
                innerCompleted = true
            }
        }
        assertTrue(innerCompleted, "Structured concurrency should wait for child")
    }

    @Test
    fun test_async_returns_result() = runTest {
        val deferred = async { 42 }
        val result = deferred.await()
        assertEquals(42, result)
    }

    @Test
    fun test_launch_fire_and_forget() = runTest {
        var sideEffect = 0
        val job = launch {
            delay(10)
            sideEffect = 1
        }
        job.join()
        assertEquals(1, sideEffect)
    }

    @Test
    fun test_cancellation_exception_propagates() = runTest {
        val job = launch {
            delay(Long.MAX_VALUE)
        }
        job.cancel()
        job.join()
        assertTrue(job.isCancelled, "Job should be cancelled")
    }

    @Test
    fun test_flow_collect_values() = runTest {
        val values = mutableListOf<Int>()
        flowOf(1, 2, 3).collect { values.add(it) }
        assertEquals(listOf(1, 2, 3), values)
    }

    @Test
    fun test_flow_map_transform() = runTest {
        val result = flowOf(1, 2, 3)
            .map { it * 10 }
            .toList()
        assertEquals(listOf(10, 20, 30), result)
    }

    @Test
    fun test_flow_filter() = runTest {
        val result = flowOf(1, 2, 3, 4, 5)
            .filter { it % 2 == 0 }
            .toList()
        assertEquals(listOf(2, 4), result)
    }

    @Test
    fun test_channel_send_receive() = runTest {
        val channel = Channel<Int>(capacity = 10)
        launch {
            channel.send(42)
            channel.close()
        }
        val value = channel.receive()
        assertEquals(42, value)
    }

    @Test
    fun test_withContext_switches_dispatcher() = runTest {
        val result = withContext(Dispatchers.Default) {
            "computed"
        }
        assertEquals("computed", result)
    }

    @Test
    fun test_supervisor_scope_isolates_failures() = runTest {
        var child1Failed = false
        var child2Completed = false

        try {
            supervisorScope {
                launch {
                    throw RuntimeException("child1 fails")
                }.invokeOnCompletion { cause ->
                    if (cause != null) child1Failed = true
                }
                launch {
                    delay(10)
                    child2Completed = true
                }
            }
        } catch (e: Exception) {
            // supervisorScope may rethrow
        }

        assertTrue(child1Failed, "Child 1 should fail")
        assertTrue(child2Completed, "Child 2 should complete despite child 1 failure")
    }

    @Test
    fun test_coroutine_exception_handler() = runTest {
        var caughtException: Throwable? = null
        val handler = CoroutineExceptionHandler { _, exception ->
            caughtException = exception
        }

        val scope = CoroutineScope(SupervisorJob() + handler)
        scope.launch {
            throw IllegalStateException("test error")
        }.join()

        assertNotNull(caughtException, "Exception handler should catch the error")
        assertEquals("test error", caughtException?.message)
    }

    @Test
    fun test_flow_catch_operator() = runTest {
        var caught = false
        flow {
            emit(1)
            throw RuntimeException("flow error")
        }.catch {
            caught = true
        }.collect {}
        assertTrue(caught, "catch operator should handle flow errors")
    }

    @Test
    fun test_flow_debounce_like_behavior() = runTest {
        // Simulate collecting only the last element after rapid emissions
        val result = flowOf(1, 2, 3, 4, 5)
            .toList()
            .last()
        assertEquals(5, result)
    }

    @Test
    fun test_channel_fan_out() = runTest {
        val channel = Channel<Int>(capacity = 10)
        val results = mutableListOf<Int>()

        launch {
            for (i in 1..5) channel.send(i)
            channel.close()
        }

        for (value in channel) {
            results.add(value)
        }
        assertEquals(listOf(1, 2, 3, 4, 5), results)
    }

    @Test
    fun test_mutex_prevents_race() = runTest {
        val mutex = kotlinx.coroutines.sync.Mutex()
        var counter = 0
        val jobs = (1..100).map {
            launch {
                mutex.withLock {
                    counter++
                }
            }
        }
        jobs.forEach { it.join() }
        assertEquals(100, counter, "Mutex should prevent data races")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    data class RequestResult(val success: Boolean, val data: String = "")

    class SensorHandler {
        
        fun usesRunBlocking(): Boolean = true 

        suspend fun handleRequest(requestId: String): RequestResult {
            
            return try {
                runBlocking {
                    delay(10)
                    RequestResult(success = true, data = "processed $requestId")
                }
            } catch (e: Exception) {
                RequestResult(success = false, data = e.message ?: "error")
            }
        }
    }

    class IngestionService {
        
        fun usesGlobalScope(): Boolean = true 

        suspend fun startBackgroundProcessing() {
            
            delay(5000) // Simulates long-running work
        }
    }

    data class DispatcherInfo(val flowOnBeforeCollect: Boolean, val dispatcherName: String = "")

    class SensorFlowProcessor {
        
        fun getFlowDispatcherInfo(): DispatcherInfo {
            return DispatcherInfo(flowOnBeforeCollect = false) 
        }

        fun getEmissionThreadName(): String {
            
            return "main" 
        }
    }

    data class BurstResult(val peakBuffered: Int, val allProcessed: Boolean)

    class ChannelProcessor {
        
        fun getChannelCapacity(): Int = Channel.UNLIMITED 

        suspend fun simulateBurst(messageCount: Int): BurstResult {
            
            return BurstResult(
                peakBuffered = messageCount, 
                allProcessed = true
            )
        }
    }

    data class AsyncResult(val errorPropagated: Boolean, val awaitCalled: Boolean)

    class AsyncErrorHandler {
        fun runAsyncWithError(): AsyncResult {
            
            return AsyncResult(errorPropagated = false, awaitCalled = false) 
        }

        fun checkAwaitCalled(): AsyncResult {
            
            return AsyncResult(errorPropagated = false, awaitCalled = false) 
        }
    }
}
