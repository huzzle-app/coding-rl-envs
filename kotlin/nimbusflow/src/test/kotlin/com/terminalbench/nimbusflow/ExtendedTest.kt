package com.terminalbench.nimbusflow

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import kotlin.math.abs

class ExtendedTest {
    // === Domain / Model Tests ===

    @Test
    fun severityClassifyEmergency() {
        assertEquals(Severity.CRITICAL, Severity.classify("EMERGENCY at port"))
        assertEquals(Severity.HIGH, Severity.classify("urgent repair"))
        assertEquals(Severity.MEDIUM, Severity.classify("moderate delay"))
        assertEquals(Severity.LOW, Severity.classify("minor maintenance"))
        assertEquals(Severity.INFO, Severity.classify("routine check"))
    }

    @Test
    fun severitySlaByLevel() {
        assertEquals(15, Severity.slaByLevel(5))
        assertEquals(30, Severity.slaByLevel(4))
        assertEquals(60, Severity.slaByLevel(3))
        assertEquals(120, Severity.slaByLevel(2))
        assertEquals(240, Severity.slaByLevel(1))
        assertEquals(60, Severity.slaByLevel(99))
    }

    @Test
    fun vesselManifestAttributes() {
        val heavy = VesselManifest("V1", "Atlas", 60000.0, 1200, true)
        val light = VesselManifest("V2", "Hermes", 20000.0, 800, false)
        assertTrue(heavy.isHeavy)
        assertFalse(light.isHeavy)
        assertEquals(50.0, heavy.containerWeightRatio)
        assertEquals(25.0, light.containerWeightRatio)
    }

    @Test
    fun orderFactoryCreateBatch() {
        val orders = OrderFactory.createBatch(listOf("a", "b", "c"), 4, 30)
        assertEquals(3, orders.size)
        orders.forEach { assertEquals(4, it.urgency) }
        orders.forEach { assertEquals(30, it.slaMinutes) }
    }

    @Test
    fun orderFactoryValidateOrder() {
        assertNull(OrderFactory.validateOrder(DispatchOrder("valid", 3, 60)))
        assertNotNull(OrderFactory.validateOrder(DispatchOrder("", 3, 60)))
        assertNotNull(OrderFactory.validateOrder(DispatchOrder("x", 0, 60)))
        assertNotNull(OrderFactory.validateOrder(DispatchOrder("x", 3, 0)))
    }

    // === Allocator Tests ===

    @Test
    fun dispatchBatchSplitsCorrectly() {
        val (planned, rejected) = Allocator.dispatchBatch(
            listOf(
                DispatchOrder("a", 5, 10),
                DispatchOrder("b", 2, 90),
                DispatchOrder("c", 4, 20)
            ), 2
        )
        assertEquals(2, planned.size)
        assertEquals(1, rejected.size)
        assertEquals("b", rejected[0].id)
    }

    @Test
    fun estimateCostScalesWithSeverity() {
        val low = Allocator.estimateCost(1, 120, 100.0)
        val high = Allocator.estimateCost(5, 120, 100.0)
        assertTrue(high > low)
    }

    @Test
    fun allocateCostsDividesBudget() {
        val orders = listOf(DispatchOrder("a", 2, 60), DispatchOrder("b", 3, 60))
        val costs = Allocator.allocateCosts(orders, 100.0)
        assertEquals(2, costs.size)
        assertTrue(abs(costs.sumOf { it.second } - 100.0) < 1.0)
    }

    @Test
    fun estimateTurnaroundHazmatMultiplier() {
        val normal = Allocator.estimateTurnaround(500, false)
        val hazmat = Allocator.estimateTurnaround(500, true)
        assertEquals(normal * 1.5, hazmat)
    }

    @Test
    fun validateBatchDetectsDuplicates() {
        val err = Allocator.validateBatch(listOf(DispatchOrder("a", 3, 60), DispatchOrder("a", 4, 30)))
        assertTrue(err!!.contains("duplicate"))
    }

    @Test
    fun berthPlannerConflictDetection() {
        val a = BerthSlot("B1", 8, 14, true, "V1")
        val b = BerthSlot("B1", 10, 16, true, "V2")
        val c = BerthSlot("B2", 10, 16, true, "V3")
        assertTrue(BerthPlanner.hasConflict(a, b))
        assertFalse(BerthPlanner.hasConflict(a, c))
    }

    @Test
    fun rollingWindowSchedulerLifecycle() {
        val sched = RollingWindowScheduler(60)
        sched.submit(100, "o1")
        sched.submit(110, "o2")
        assertEquals(2, sched.count)
        val expired = sched.flush(170)
        assertEquals(1, expired.size)
        assertEquals(1, sched.count)
    }

    // === Routing Tests ===

    @Test
    fun channelScoreComposite() {
        assertEquals(0.0, Routing.channelScore(0, 0.9, 5))
        val score = Routing.channelScore(10, 0.8, 5)
        assertTrue(score > 0)
    }

    @Test
    fun estimateTransitTimeCalculation() {
        val hours = Routing.estimateTransitTime(100.0, 20.0)
        assertEquals(5.0, hours)
        assertEquals(Double.MAX_VALUE, Routing.estimateTransitTime(100.0, 0.0))
    }

    @Test
    fun multiLegPlannerAggregatesTotalDistance() {
        val plan = MultiLegPlanner.plan(
            listOf(Waypoint("A", 50.0), Waypoint("B", 30.0), Waypoint("C", 20.0)),
            10.0
        )
        assertEquals(100.0, plan.totalDistance)
        assertEquals(10.0, plan.estimatedHours)
        assertEquals(3, plan.legs.size)
    }

    @Test
    fun routeTableCrud() {
        val table = RouteTable()
        table.add(Route("north", 5))
        table.add(Route("south", 12))
        assertEquals(2, table.count)
        assertNotNull(table.get("north"))
        assertEquals(5, table.get("north")!!.latency)
        table.remove("north")
        assertEquals(1, table.count)
        assertNull(table.get("north"))
    }

    @Test
    fun compareRoutesOrdering() {
        val a = Route("alpha", 5)
        val b = Route("beta", 10)
        assertTrue(Routing.compareRoutes(a, b) < 0)
        assertTrue(Routing.compareRoutes(b, a) > 0)
    }

    // === Policy Tests ===

    @Test
    fun previousPolicyDeescalates() {
        assertEquals("restricted", Policy.previousPolicy("halted"))
        assertEquals("watch", Policy.previousPolicy("restricted"))
        assertEquals("normal", Policy.previousPolicy("normal"))
    }

    @Test
    fun shouldDeescalateThresholds() {
        assertTrue(Policy.shouldDeescalate(10, "halted"))
        assertFalse(Policy.shouldDeescalate(9, "halted"))
        assertTrue(Policy.shouldDeescalate(7, "restricted"))
        assertTrue(Policy.shouldDeescalate(5, "watch"))
        assertFalse(Policy.shouldDeescalate(100, "normal"))
    }

    @Test
    fun slaComplianceCalculation() {
        assertTrue(Policy.checkSlaCompliance(30, 60))
        assertFalse(Policy.checkSlaCompliance(90, 60))
        val pct = Policy.slaPercentage(listOf(Pair(30, 60), Pair(90, 60), Pair(50, 60)))
        assertTrue(abs(pct - 66.666) < 1.0)
    }

    @Test
    fun policyEngineEscalateDeescalate() {
        val engine = PolicyEngine()
        assertEquals("normal", engine.currentPolicy)
        engine.escalate(3)
        assertEquals("watch", engine.currentPolicy)
        engine.escalate(3)
        assertEquals("restricted", engine.currentPolicy)
        engine.deescalate()
        assertEquals("watch", engine.currentPolicy)
        assertEquals(3, engine.getHistory().size)
        engine.reset()
        assertEquals("normal", engine.currentPolicy)
    }

    @Test
    fun policyMetadataLookup() {
        val meta = PolicyMetadataStore.getMetadata("halted")
        assertNotNull(meta)
        assertEquals(0, meta!!.maxRetries)
        assertNull(PolicyMetadataStore.getMetadata("unknown"))
    }

    // === Queue Tests ===

    @Test
    fun priorityQueueOrdering() {
        val pq = PriorityQueue(10)
        pq.enqueue(QueueItem("low", 1))
        pq.enqueue(QueueItem("high", 9))
        pq.enqueue(QueueItem("mid", 5))
        val first = pq.dequeue()
        assertEquals("high", first!!.id)
        assertEquals(9, first.priority)
    }

    @Test
    fun priorityQueueHardLimit() {
        val pq = PriorityQueue(2)
        assertTrue(pq.enqueue(QueueItem("a", 1)))
        assertTrue(pq.enqueue(QueueItem("b", 2)))
        assertFalse(pq.enqueue(QueueItem("c", 3)))
    }

    @Test
    fun rateLimiterTokenBucket() {
        val limiter = RateLimiter(3.0, 1.0)
        assertTrue(limiter.tryAcquire(0))
        assertTrue(limiter.tryAcquire(0))
        assertTrue(limiter.tryAcquire(0))
        assertFalse(limiter.tryAcquire(0))
        assertTrue(limiter.tryAcquire(2))
    }

    @Test
    fun queueHealthMonitorStatuses() {
        assertEquals("healthy", QueueHealthMonitor.check(10, 100).status)
        assertEquals("elevated", QueueHealthMonitor.check(65, 100).status)
        assertEquals("warning", QueueHealthMonitor.check(85, 100).status)
        assertEquals("critical", QueueHealthMonitor.check(100, 100).status)
    }

    @Test
    fun estimateWaitTimeInfiniteForZeroRate() {
        assertEquals(Double.MAX_VALUE, QueueGuard.estimateWaitTime(10, 0.0))
        assertEquals(5.0, QueueGuard.estimateWaitTime(10, 2.0))
    }

    // === Security Tests ===

    @Test
    fun signManifestAndVerify() {
        val payload = "cargo:containers:1200"
        val key = "secret-key"
        val sig = Security.signManifest(payload, key)
        assertTrue(Security.verifyManifest(payload, key, sig))
        assertFalse(Security.verifyManifest("tampered", key, sig))
    }

    @Test
    fun sanitisePathRemovesTraversal() {
        assertEquals("data/file.txt", Security.sanitisePath("../../../data/file.txt"))
        assertEquals("file.txt", Security.sanitisePath("/file.txt"))
    }

    @Test
    fun isAllowedOriginCheck() {
        assertTrue(Security.isAllowedOrigin("https://nimbusflow.internal"))
        assertFalse(Security.isAllowedOrigin("https://evil.com"))
    }

    @Test
    fun tokenStoreLifecycle() {
        val store = TokenStore()
        store.store("user1", "tok123", 1000, 60)
        assertTrue(store.validate("user1", "tok123", 1050))
        assertFalse(store.validate("user1", "tok123", 1070))
        assertFalse(store.validate("user1", "wrong", 1050))
        assertEquals(1, store.count)
        store.revoke("user1")
        assertEquals(0, store.count)
    }

    @Test
    fun tokenStoreCleanup() {
        val store = TokenStore()
        store.store("a", "t1", 100, 10)
        store.store("b", "t2", 200, 10)
        val cleaned = store.cleanup(115)
        assertEquals(1, cleaned)
        assertEquals(1, store.count)
    }

    // === Resilience Tests ===

    @Test
    fun deduplicateKeepsFirst() {
        val events = Resilience.deduplicate(
            listOf(ReplayEvent("a", 1), ReplayEvent("a", 2), ReplayEvent("b", 1))
        )
        assertEquals(2, events.size)
        assertEquals(1, events.first { it.id == "a" }.sequence)
    }

    @Test
    fun replayConvergenceCheck() {
        val a = listOf(ReplayEvent("x", 1), ReplayEvent("x", 2), ReplayEvent("y", 1))
        val b = listOf(ReplayEvent("y", 1), ReplayEvent("x", 2), ReplayEvent("x", 1))
        assertTrue(Resilience.replayConverges(a, b))
    }

    @Test
    fun circuitBreakerTransitions() {
        val cb = CircuitBreaker(3, 2)
        assertEquals(CircuitBreakerState.CLOSED, cb.currentState)
        assertTrue(cb.isCallPermitted)
        cb.recordFailure()
        cb.recordFailure()
        cb.recordFailure()
        assertEquals(CircuitBreakerState.OPEN, cb.currentState)
        assertFalse(cb.isCallPermitted)
        cb.attemptReset()
        assertEquals(CircuitBreakerState.HALF_OPEN, cb.currentState)
        assertTrue(cb.isCallPermitted)
        cb.recordSuccess()
        cb.recordSuccess()
        assertEquals(CircuitBreakerState.CLOSED, cb.currentState)
    }

    @Test
    fun checkpointManagerRecordAndGet() {
        val mgr = CheckpointManager(10)
        mgr.record(Checkpoint("cp1", 5, 1000))
        assertEquals(1, mgr.count)
        val cp = mgr.get("cp1")
        assertNotNull(cp)
        assertEquals(5, cp!!.sequence)
        assertTrue(mgr.shouldCheckpoint(20, 5))
        assertFalse(mgr.shouldCheckpoint(12, 5))
        mgr.reset()
        assertEquals(0, mgr.count)
    }

    // === Statistics Tests ===

    @Test
    fun meanVarianceStdDev() {
        val data = listOf(2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0)
        val mean = Statistics.mean(data)
        assertEquals(5.0, mean)
        val variance = Statistics.variance(data)
        assertTrue(abs(variance - 4.0) < 0.01)
        val stddev = Statistics.stddev(data)
        assertTrue(abs(stddev - 2.0) < 0.01)
    }

    @Test
    fun medianEvenOdd() {
        assertEquals(3.0, Statistics.median(listOf(1.0, 3.0, 5.0)))
        assertEquals(2.5, Statistics.median(listOf(1.0, 2.0, 3.0, 4.0)))
        assertEquals(0.0, Statistics.median(emptyList()))
    }

    @Test
    fun movingAverageWindowed() {
        val values = listOf(1.0, 2.0, 3.0, 4.0, 5.0)
        val ma = Statistics.movingAverage(values, 3)
        assertEquals(3, ma.size)
        assertEquals(2.0, ma[0])
        assertEquals(3.0, ma[1])
        assertEquals(4.0, ma[2])
    }

    @Test
    fun responseTimeTrackerPercentiles() {
        val tracker = ResponseTimeTracker(100)
        for (i in 1..100) tracker.record(i.toDouble())
        assertEquals(100, tracker.count)
        assertTrue(tracker.p50 in 40.0..60.0)
        assertTrue(tracker.p95 >= 90.0)
        assertTrue(tracker.p99 >= 95.0)
    }

    @Test
    fun heatmapGeneratorAccumulates() {
        val events = listOf(
            HeatmapEvent(0.0, 0.0, 1.0),
            HeatmapEvent(0.0, 0.0, 2.0),
            HeatmapEvent(1.0, 1.0, 3.0)
        )
        val cells = HeatmapGenerator.generate(events, 3, 3)
        assertEquals(9, cells.size)
        assertEquals(3.0, cells.first { it.row == 0 && it.col == 0 }.value)
    }

    // === Workflow Tests ===

    @Test
    fun workflowAllowedTransitions() {
        val fromQueued = Workflow.allowedTransitions("queued")
        assertTrue("allocated" in fromQueued)
        assertTrue("cancelled" in fromQueued)
        assertTrue(Workflow.allowedTransitions("arrived").isEmpty())
    }

    @Test
    fun workflowShortestPath() {
        val path = Workflow.shortestPath("queued", "arrived")
        assertNotNull(path)
        assertEquals("queued", path!![0])
        assertEquals("arrived", path.last())
        assertTrue(path.size >= 3)
    }

    @Test
    fun workflowEngineLifecycle() {
        val engine = WorkflowEngine()
        engine.register("ship-1")
        assertEquals("queued", engine.getState("ship-1"))
        assertEquals(1, engine.activeCount)
        val r1 = engine.transition("ship-1", "allocated", 100)
        assertTrue(r1.success)
        assertEquals("queued", r1.from)
        val r2 = engine.transition("ship-1", "departed", 200)
        assertTrue(r2.success)
        val r3 = engine.transition("ship-1", "arrived", 300)
        assertTrue(r3.success)
        assertTrue(engine.isTerminal("ship-1"))
        assertEquals(0, engine.activeCount)
        assertEquals(3, engine.getHistory().size)
        assertEquals(3, engine.auditLog.size)
    }

    @Test
    fun workflowEngineRejectsInvalidTransition() {
        val engine = WorkflowEngine()
        engine.register("ship-2")
        val r = engine.transition("ship-2", "arrived", 100)
        assertFalse(r.success)
        assertTrue(r.error!!.contains("cannot transition"))
    }

    // === Contracts Tests ===

    @Test
    fun serviceRegistryDefinitions() {
        val all = ServiceRegistry.all()
        assertEquals(8, all.size)
        assertTrue(all.any { it.id == "gateway" })
    }

    @Test
    fun serviceRegistryGetServiceUrl() {
        val url = ServiceRegistry.getServiceUrl("gateway")
        assertNotNull(url)
        assertTrue(url!!.contains("8160"))
        assertTrue(url.contains("/health"))
        assertNull(ServiceRegistry.getServiceUrl("nonexistent"))
    }

    @Test
    fun serviceRegistryValidateContract() {
        val defs = ServiceRegistry.all()
        assertNull(ServiceRegistry.validateContract(defs))
    }

    @Test
    fun serviceRegistryTopologicalOrder() {
        val defs = ServiceRegistry.all()
        val order = ServiceRegistry.topologicalOrder(defs)
        assertNotNull(order)
        assertEquals(8, order!!.size)
        assertEquals("gateway", order[0])
    }

    // === Additional Scenario Tests ===

    @Test
    fun budgetAllocationRoundTrip() {
        val orders = listOf(
            DispatchOrder("x", 1, 60),
            DispatchOrder("y", 2, 60),
            DispatchOrder("z", 3, 60)
        )
        val costs = Allocator.allocateCosts(orders, 100.0)
        val total = costs.sumOf { it.second }
        assertTrue(abs(total - 100.0) < 0.02)
    }

    @Test
    fun budgetSplitAcrossEqualPriorities() {
        val orders = (1..7).map { DispatchOrder("o$it", 1, 60) }
        val costs = Allocator.allocateCosts(orders, 100.0)
        val total = costs.sumOf { it.second }
        assertTrue(abs(total - 100.0) < 0.10)
    }

    @Test
    fun heatmapBoundaryEventPlacement() {
        val events = listOf(
            HeatmapEvent(-1.0, -1.0, 5.0),
            HeatmapEvent(0.0, 0.0, 1.0)
        )
        val cells = HeatmapGenerator.generate(events, 3, 3)
        val origin = cells.first { it.row == 0 && it.col == 0 }
        assertEquals(1.0, origin.value)
    }

    @Test
    fun turnaroundEstimateForPartialLoad() {
        val hours = Allocator.estimateTurnaround(750, false)
        assertEquals(2.0, hours)
    }

    @Test
    fun turnaroundEstimateOverflow() {
        val hours = Allocator.estimateTurnaround(501, false)
        assertEquals(2.0, hours)
    }

    @Test
    fun turnaroundHazmatPenalty() {
        val hours = Allocator.estimateTurnaround(750, true)
        assertEquals(3.0, hours)
    }

    @Test
    fun recoveryFromHaltedState() {
        assertTrue(Policy.shouldDeescalate(10, "halted"))
        assertFalse(Policy.shouldDeescalate(9, "halted"))
    }

    @Test
    fun recoveryFromRestrictedState() {
        assertTrue(Policy.shouldDeescalate(5, "restricted"))
        assertFalse(Policy.shouldDeescalate(4, "restricted"))
    }

    @Test
    fun recoveryFromWatchState() {
        assertTrue(Policy.shouldDeescalate(3, "watch"))
        assertFalse(Policy.shouldDeescalate(2, "watch"))
    }

    @Test
    fun costModelReflectsSeverity() {
        val highSevCost = Allocator.estimateCost(5, 30, 100.0)
        val lowSevCost = Allocator.estimateCost(1, 30, 100.0)
        assertTrue(highSevCost > lowSevCost)
    }

    @Test
    fun capacityBoundaryCheck() {
        assertTrue(Allocator.checkCapacity(100, 100))
    }

    @Test
    fun circuitBreakerRecoveryCycle() {
        val cb = CircuitBreaker(3, 2)
        cb.recordFailure()
        cb.recordFailure()
        assertEquals(CircuitBreakerState.CLOSED, cb.currentState)
        cb.recordFailure()
        assertEquals(CircuitBreakerState.OPEN, cb.currentState)

        cb.attemptReset()
        assertEquals(CircuitBreakerState.HALF_OPEN, cb.currentState)
        cb.recordFailure()
        assertEquals(CircuitBreakerState.OPEN, cb.currentState)

        cb.attemptReset()
        cb.recordSuccess()
        cb.recordSuccess()
        assertEquals(CircuitBreakerState.CLOSED, cb.currentState)
    }

    @Test
    fun circuitBreakerRepeatedCycles() {
        val cb = CircuitBreaker(2, 1)
        cb.recordFailure()
        cb.recordFailure()
        assertEquals(CircuitBreakerState.OPEN, cb.currentState)

        cb.attemptReset()
        cb.recordFailure()
        assertEquals(CircuitBreakerState.OPEN, cb.currentState)

        cb.attemptReset()
        cb.recordSuccess()
        assertEquals(CircuitBreakerState.CLOSED, cb.currentState)

        cb.recordFailure()
        assertEquals(CircuitBreakerState.CLOSED, cb.currentState)
        cb.recordFailure()
        assertEquals(CircuitBreakerState.OPEN, cb.currentState)
    }

    @Test
    fun workflowProgressionIsForward() {
        assertFalse(Workflow.canTransition("departed", "allocated"))
    }

    @Test
    fun cancelledEntityLifecycle() {
        val engine = WorkflowEngine()
        engine.register("ship-cancel")
        engine.transition("ship-cancel", "cancelled", 100)
        assertEquals(0, engine.activeCount)
    }

    @Test
    fun optimalDispatchRoute() {
        val path = Workflow.shortestPath("queued", "arrived")
        assertNotNull(path)
        assertEquals(listOf("queued", "allocated", "departed", "arrived"), path)
    }

    @Test
    fun policyResponseToIncident() {
        val engine = PolicyEngine()
        engine.escalate(5)
        assertEquals("watch", engine.currentPolicy)
        engine.escalate(10)
        assertEquals("restricted", engine.currentPolicy)
    }

    @Test
    fun policyHistoryAccuracy() {
        val engine = PolicyEngine()
        engine.deescalate()
        engine.deescalate()
        assertEquals(0, engine.getHistory().size)
    }

    @Test
    fun priorityQueueUnderConcurrentLoad() {
        val pq = PriorityQueue(100)
        val latch = java.util.concurrent.CountDownLatch(1)
        val threads = (1..20).map { t ->
            Thread {
                latch.await()
                repeat(20) { i ->
                    pq.enqueue(QueueItem("t$t-$i", i))
                }
            }
        }
        threads.forEach { it.start() }
        latch.countDown()
        threads.forEach { it.join() }
        assertTrue(pq.size <= 100)
    }

    @Test
    fun workflowAuditUnderConcurrentLoad() {
        val engine = WorkflowEngine()
        val errors = java.util.concurrent.atomic.AtomicInteger(0)
        for (i in 1..100) engine.register("e-$i")
        val writers = (1..5).map { t ->
            Thread {
                for (i in (t * 20 - 19)..(t * 20)) {
                    try {
                        engine.transition("e-$i", "allocated", System.nanoTime())
                    } catch (_: Exception) { errors.incrementAndGet() }
                }
            }
        }
        val readers = (1..5).map {
            Thread {
                repeat(50) {
                    try { engine.auditLog } catch (_: Exception) { errors.incrementAndGet() }
                }
            }
        }
        (writers + readers).forEach { it.start() }
        (writers + readers).forEach { it.join() }
        assertEquals(0, errors.get())
    }

    @Test
    fun workflowHistoryUnderConcurrentLoad() {
        val engine = WorkflowEngine()
        val errors = java.util.concurrent.atomic.AtomicInteger(0)
        for (i in 1..100) engine.register("e-$i")
        val writers = (1..5).map { t ->
            Thread {
                for (i in (t * 20 - 19)..(t * 20)) {
                    try {
                        engine.transition("e-$i", "allocated", System.nanoTime())
                    } catch (_: Exception) { errors.incrementAndGet() }
                }
            }
        }
        val readers = (1..5).map {
            Thread {
                repeat(50) {
                    try {
                        engine.getHistory()
                    } catch (_: java.util.ConcurrentModificationException) { errors.incrementAndGet() }
                }
            }
        }
        (writers + readers).forEach { it.start() }
        (writers + readers).forEach { it.join() }
        assertEquals(0, errors.get())
    }

    @Test
    fun tokenLifecycleBoundary() {
        val store = TokenStore()
        store.store("u1", "token1", 1000, 60)
        assertFalse(store.validate("u1", "token1", 1060))
    }

    @Test
    fun tokenValidityWindow() {
        val store = TokenStore()
        store.store("u1", "token1", 1000, 60)
        assertTrue(store.validate("u1", "token1", 1059))
    }

    @Test
    fun serviceDiscoveryEndpoints() {
        val url = ServiceRegistry.getServiceUrl("gateway")
        assertNotNull(url)
        assertTrue(url!!.contains(":8160"))
    }

    @Test
    fun queueWaitEstimate() {
        val wt = QueueGuard.estimateWaitTime(10, 2.0)
        assertEquals(5.0, wt)
    }

    @Test
    fun voyageCostEstimate() {
        val cost = Routing.estimateRouteCost(100.0, 2.0, 50.0)
        assertEquals(250.0, cost)
    }

    @Test
    fun channelQualityAssessment() {
        val lowLatencyScore = Routing.channelScore(5, 0.9, 3)
        val highLatencyScore = Routing.channelScore(50, 0.9, 3)
        assertTrue(lowLatencyScore > highLatencyScore)
    }

    @Test
    fun endToEndDispatchScenario() {
        val orders = OrderFactory.createBatch(listOf("ship-1", "ship-2", "ship-3"), Severity.HIGH, 30)
        assertEquals(3, orders.size)

        val (planned, rejected) = Allocator.dispatchBatch(orders, 2)
        assertEquals(2, planned.size)
        assertEquals(1, rejected.size)
        assertTrue(planned[0].urgency >= planned[1].urgency)

        val route = Routing.chooseRoute(
            listOf(Route("express", 3), Route("standard", 10)),
            emptySet()
        )
        assertNotNull(route)
        assertEquals("express", route!!.channel)

        val engine = WorkflowEngine()
        planned.forEach { engine.register(it.id) }
        planned.forEach { assertTrue(engine.transition(it.id, "allocated", 100).success) }
        planned.forEach { assertTrue(engine.transition(it.id, "departed", 200).success) }
        planned.forEach { assertTrue(engine.transition(it.id, "arrived", 300).success) }
        assertEquals(0, engine.activeCount)
    }

    @Test
    fun emergencyLoadSheddingBehavior() {
        val hardLimit = 100
        val atEmergencyThreshold = (hardLimit * QueueGuard.EMERGENCY_RATIO).toInt()
        assertFalse(QueueGuard.shouldShed(atEmergencyThreshold - 1, hardLimit, true))
        assertTrue(QueueGuard.shouldShed(atEmergencyThreshold, hardLimit, true))
    }
}
