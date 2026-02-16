package com.pulsemap.coroutine

import com.pulsemap.core.*
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
        // Verify the SensorHandler source code does not use runBlocking.
        // runBlocking inside a coroutine context blocks the thread and can deadlock.
        val source = java.io.File(System.getProperty("user.dir"), "src/main/kotlin/com/pulsemap/core/CoroutineStubs.kt").readText()
        val handlerSection = source.substringAfter("class SensorHandler")
            .substringBefore("class IngestionServiceCoroutine")
        assertFalse(
            handlerSection.contains("runBlocking"),
            "SensorHandler should NOT use runBlocking inside suspend function"
        )
    }

    @Test
    fun test_concurrent_requests_no_deadlock() = runTest {
        val handler = SensorHandler()
        // In runTest, proper delay() uses virtual time (completes instantly).
        // But runBlocking { delay() } creates a nested event loop with REAL time.
        // 10 requests with runBlocking { delay(10) } = ~100ms real wall-clock time.
        // 10 requests with proper delay(10) = ~0ms real wall-clock time.
        val startNanos = System.nanoTime()
        val results = (1..10).map { i ->
            async {
                handler.handleRequest("request-$i")
            }
        }
        val responses = results.map { it.await() }
        val elapsedMs = (System.nanoTime() - startNanos) / 1_000_000

        assertEquals(10, responses.size, "All 10 concurrent requests should complete")
        assertTrue(responses.all { it.success }, "All requests should succeed")
        assertTrue(
            elapsedMs < 50,
            "Handler should suspend (virtual time), not block with runBlocking (real time). Took ${elapsedMs}ms"
        )
    }

    // =========================================================================
    // A2: GlobalScope usage
    // =========================================================================

    @Test
    fun test_no_global_scope() = runTest {
        // Verify the IngestionServiceCoroutine source code does not use GlobalScope.
        // GlobalScope coroutines are not cancelled when the parent scope is cancelled.
        val source = java.io.File(System.getProperty("user.dir"), "src/main/kotlin/com/pulsemap/core/CoroutineStubs.kt").readText()
        val serviceSection = source.substringAfter("class IngestionServiceCoroutine")
            .substringBefore("class SensorFlowProcessor")
        assertFalse(
            serviceSection.contains("GlobalScope"),
            "Service should use structured concurrency, not GlobalScope"
        )
    }

    @Test
    fun test_coroutine_cancelled_on_shutdown() = runTest {
        val scope = CoroutineScope(Dispatchers.Default + Job())
        val ingestionService = IngestionServiceCoroutine()

        val job = scope.launch {
            ingestionService.startBackgroundProcessing()
        }

        delay(50)
        scope.cancel()
        job.join()

        // The key check: with GlobalScope, the background job LEAKS (still active).
        // With structured concurrency, the background job is cancelled with its parent.
        val bgJob = ingestionService.backgroundJob
        assertNotNull(bgJob, "Background job should be tracked")
        assertTrue(
            bgJob!!.isCancelled || bgJob.isCompleted,
            "Background job should be cancelled when parent scope is cancelled (leaked via GlobalScope)"
        )
    }

    // =========================================================================
    // A3: flowOn placement
    // =========================================================================

    @Test
    fun test_flow_on_before_collect() = runTest {
        // Verify that flowOn is applied BEFORE collect in the source code.
        val source = java.io.File(System.getProperty("user.dir"), "src/main/kotlin/com/pulsemap/core/CoroutineStubs.kt").readText()
        val processorSection = source.substringAfter("class SensorFlowProcessor")
            .substringBefore("class ChannelProcessor")
        // Check that flowOn appears before .collect in the flow chain
        val flowOnIndex = processorSection.indexOf(".flowOn(")
        val collectIndex = processorSection.indexOf(".collect")
        assertTrue(
            flowOnIndex in 1 until collectIndex,
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

        val handler = CoroutineExceptionHandler { _, exception ->
            if (exception.message == "child1 fails") child1Failed = true
        }

        val scope = CoroutineScope(coroutineContext + SupervisorJob() + handler)
        scope.launch {
            throw RuntimeException("child1 fails")
        }
        scope.launch {
            delay(10)
            child2Completed = true
        }

        // Wait for all children to complete
        scope.coroutineContext[Job]!!.children.forEach { it.join() }

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
}
