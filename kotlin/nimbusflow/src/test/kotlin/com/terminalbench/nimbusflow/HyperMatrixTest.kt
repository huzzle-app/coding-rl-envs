package com.terminalbench.nimbusflow

import java.security.MessageDigest
import java.util.stream.IntStream
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.MethodSource
import kotlin.math.abs
import kotlin.math.ceil

class HyperMatrixTest {
    companion object {
        @JvmStatic
        fun cases(): IntStream = IntStream.range(0, 9200)

        private fun digest(payload: String): String {
            val bytes = MessageDigest.getInstance("SHA-256").digest(payload.toByteArray())
            return bytes.joinToString("") { "%02x".format(it) }
        }
    }

    @ParameterizedTest(name = "hyper-matrix-{0}")
    @MethodSource("cases")
    fun hyperMatrixCase(idx: Int) {
        val group = idx % 12
        val severityA = (idx % 5) + 1
        val severityB = ((idx * 3) % 5) + 1
        val slaA = 20 + (idx % 90)
        val slaB = 20 + ((idx * 2) % 90)

        val orderA = DispatchOrder("a-$idx", severityA, slaA)
        val orderB = DispatchOrder("b-$idx", severityB, slaB)

        // ============================================================
        // GROUP 0: urgencyScore formula + planDispatch sort direction
        // ============================================================
        if (group == 0) {
            // Bug: urgencyScore uses '-' instead of '+'
            val expectedScore = (orderA.urgency * 10) + maxOf(0, 120 - orderA.slaMinutes)
            assertEquals(expectedScore, orderA.urgencyScore(),
                "urgencyScore(urgency=${orderA.urgency}, sla=${orderA.slaMinutes})")

            // Bug: planDispatch sorts ascending instead of descending
            val planned = Allocator.planDispatch(
                listOf(
                    DispatchOrder("hi-$idx", 5, 30),
                    DispatchOrder("lo-$idx", 1, 30),
                ),
                2
            )
            assertEquals("hi-$idx", planned[0].id,
                "planDispatch must place highest urgency first")
        }

        // ============================================================
        // GROUP 1: estimateCost severity scaling + channelScore latency
        // ============================================================
        if (group == 1) {
            // Bug: estimateCost divides by severity instead of multiplying
            val lowSevCost = Allocator.estimateCost(1, 60, 100.0)
            val highSevCost = Allocator.estimateCost(5, 60, 100.0)
            assertTrue(highSevCost > lowSevCost,
                "higher severity must cost more: $highSevCost > $lowSevCost")

            // Bug: channelScore multiplies by latency instead of dividing
            val lowLatScore = Routing.channelScore(5, 0.9, 3)
            val highLatScore = Routing.channelScore(50, 0.9, 3)
            assertTrue(lowLatScore > highLatScore,
                "lower latency must score higher: $lowLatScore > $highLatScore")
        }

        // ============================================================
        // GROUP 2: estimateRouteCost + estimateTurnaround
        // ============================================================
        if (group == 2) {
            // Bug: estimateRouteCost subtracts portFee instead of adding
            val routeCost = Routing.estimateRouteCost(100.0, 2.0, 50.0)
            assertEquals(250.0, routeCost,
                "route cost = distance*fuelRate + portFee")

            // Bug: estimateTurnaround uses floor instead of ceil
            val containers = 501 + (idx % 499)
            val expectedHours = maxOf(1.0, ceil(containers / 500.0))
            val actualHours = Allocator.estimateTurnaround(containers, false)
            assertEquals(expectedHours, actualHours,
                "turnaround for $containers containers")
        }

        // ============================================================
        // GROUP 3: checkCapacity boundary + hasConflict overlap
        // ============================================================
        if (group == 3) {
            // Bug: checkCapacity uses < instead of <=
            assertTrue(Allocator.checkCapacity(100, 100),
                "demand == capacity should be allowed")
            assertTrue(Allocator.checkCapacity(50, 100),
                "demand < capacity should be allowed")
            assertFalse(Allocator.checkCapacity(101, 100),
                "demand > capacity should be rejected")

            // Bug: hasConflict inverts overlap condition
            val slotA = BerthSlot("B1", 8, 14, true, "V1")
            val slotB = BerthSlot("B1", 10, 16, true, "V2")
            assertTrue(BerthPlanner.hasConflict(slotA, slotB),
                "overlapping berth slots must conflict")
            // Non-overlapping: end of first <= start of second
            val slotC = BerthSlot("B1", 8, 10, true, "V3")
            val slotD = BerthSlot("B1", 10, 14, true, "V4")
            assertFalse(BerthPlanner.hasConflict(slotC, slotD),
                "adjacent non-overlapping slots must not conflict")
        }

        // ============================================================
        // GROUP 4: nextPolicy escalation + shouldDeescalate threshold
        // ============================================================
        if (group == 4) {
            // Bug: nextPolicy condition inverted (> instead of <=)
            assertEquals("watch", Policy.nextPolicy("normal", 3),
                "high failure burst should escalate normal→watch")
            assertEquals("restricted", Policy.nextPolicy("watch", 5),
                "high failure burst should escalate watch→restricted")

            // Bug: shouldDeescalate uses > instead of >=
            assertTrue(Policy.shouldDeescalate(10, "halted"),
                "10 successes should deescalate halted (threshold=10)")
            assertFalse(Policy.shouldDeescalate(9, "halted"),
                "9 successes should not deescalate halted")
            assertTrue(Policy.shouldDeescalate(5, "restricted"),
                "5 successes should deescalate restricted (threshold=5)")
            assertTrue(Policy.shouldDeescalate(3, "watch"),
                "3 successes should deescalate watch (threshold=3)")
        }

        // ============================================================
        // GROUP 5: deescalate history + emergency shed ratio
        // ============================================================
        if (group == 5) {
            // Bug: PolicyEngine.deescalate adds history even when no change
            val eng = PolicyEngine()
            eng.deescalate()
            eng.deescalate()
            assertEquals(0, eng.getHistory().size,
                "deescalating 'normal' should not add history entries")

            // Bug: shouldShed uses 0.5 instead of EMERGENCY_RATIO (0.8)
            val hardLimit = 100
            val threshold = (hardLimit * QueueGuard.EMERGENCY_RATIO).toInt()
            assertFalse(QueueGuard.shouldShed(threshold - 1, hardLimit, true),
                "below emergency threshold should not shed")
            assertTrue(QueueGuard.shouldShed(threshold, hardLimit, true),
                "at emergency threshold should shed")
        }

        // ============================================================
        // GROUP 6: estimateWaitTime + variance formula
        // ============================================================
        if (group == 6) {
            // Bug: estimateWaitTime multiplies instead of dividing
            val depth = 10 + (idx % 20)
            val rate = 2.0 + (idx % 3)
            val expected = depth.toDouble() / rate
            val actual = QueueGuard.estimateWaitTime(depth, rate)
            assertTrue(abs(actual - expected) < 0.001,
                "wait time = depth/rate: expected $expected, got $actual")

            // Bug: variance uses n-1 instead of n (population variance)
            val data = listOf(2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0)
            val v = Statistics.variance(data)
            assertTrue(abs(v - 4.0) < 0.01,
                "population variance should be 4.0, got $v")
        }

        // ============================================================
        // GROUP 7: token expiry boundary + replay keeps latest
        // ============================================================
        if (group == 7) {
            // Bug: TokenStore.validate uses <= instead of < for expiry
            val store = TokenStore()
            store.store("u-$idx", "tok-$idx", 1000, 60)
            assertFalse(store.validate("u-$idx", "tok-$idx", 1060),
                "token at exact expiry (issuedAt+ttl) should be invalid")
            assertTrue(store.validate("u-$idx", "tok-$idx", 1059),
                "token before expiry should be valid")

            // Bug: replay keeps oldest sequence instead of latest
            val replayed = Resilience.replay(listOf(
                ReplayEvent("r-$idx", 1),
                ReplayEvent("r-$idx", 5),
            ))
            assertEquals(1, replayed.size, "replay should deduplicate by id")
            assertEquals(5, replayed[0].sequence,
                "replay must keep latest sequence, not oldest")
        }

        // ============================================================
        // GROUP 8: percentile formula + severity classify
        // ============================================================
        if (group == 8) {
            // Bug: percentile rank formula produces wrong index
            val p50 = Statistics.percentile(listOf(1, 4, 7, 9), 50)
            assertEquals(4, p50,
                "50th percentile of [1,4,7,9] should be 4")

            // Bug: Severity.classify missing "emergency"→CRITICAL, "urgent"→HIGH
            assertEquals(Severity.CRITICAL, Severity.classify("emergency alert"),
                "emergency should classify as CRITICAL")
            assertEquals(Severity.HIGH, Severity.classify("urgent repair"),
                "urgent should classify as HIGH")
        }

        // ============================================================
        // GROUP 9: heatmap negative coords + workflow graph
        // ============================================================
        if (group == 9) {
            // Bug: negative coordinates mapped to (0,0) instead of being skipped
            val heatEvents = listOf(
                HeatmapEvent(-1.0, -1.0, 5.0),
                HeatmapEvent(0.0, 0.0, 1.0)
            )
            val cells = HeatmapGenerator.generate(heatEvents, 3, 3)
            val origin = cells.first { it.row == 0 && it.col == 0 }
            assertEquals(1.0, origin.value,
                "negative coords must be excluded from heatmap")

            // Bug: workflow graph allows departed→allocated (backward transition)
            assertFalse(Workflow.canTransition("departed", "allocated"),
                "departed should not transition backward to allocated")
        }

        // ============================================================
        // GROUP 10: terminal states + service URL format
        // ============================================================
        if (group == 10) {
            // Bug: "cancelled" not in terminalStates
            assertTrue(Workflow.isTerminalState("cancelled"),
                "cancelled must be a terminal state")
            assertTrue(Workflow.isTerminalState("arrived"),
                "arrived must be a terminal state")
            assertFalse(Workflow.isTerminalState("queued"),
                "queued must not be a terminal state")

            // Bug: getServiceUrl missing port in URL
            val url = ServiceRegistry.getServiceUrl("gateway")
            assertNotNull(url)
            assertTrue(url!!.contains(":8160"),
                "service URL must include port: $url")
            assertTrue(url.contains("/health"),
                "service URL must include health path: $url")
        }

        // ============================================================
        // GROUP 11: PQ concurrency + cross-module integration
        // ============================================================
        if (group == 11) {
            // Bug: PriorityQueue size check outside lock
            val pq = PriorityQueue(5)
            for (i in 0 until 5) pq.enqueue(QueueItem("q$i", i))
            assertFalse(pq.enqueue(QueueItem("overflow", 99)),
                "enqueue must reject when at capacity")
            assertEquals(5, pq.size,
                "queue size must not exceed hard limit")

            // Cross-module integration: dispatch + route + workflow
            val orders = Allocator.planDispatch(
                listOf(
                    DispatchOrder("integ-hi-$idx", 5, 15),
                    DispatchOrder("integ-lo-$idx", 1, 120)
                ),
                1
            )
            assertEquals(1, orders.size)
            assertEquals(5, orders[0].urgency,
                "integration: dispatch must select highest urgency")

            val route = Routing.chooseRoute(
                listOf(Route("fast", 2), Route("slow", 20)),
                emptySet()
            )
            assertNotNull(route)
            assertEquals("fast", route!!.channel,
                "integration: routing must select lowest latency")

            assertTrue(Workflow.canTransition("queued", "allocated"))
            assertTrue(Workflow.canTransition("allocated", "departed"))
            assertTrue(Workflow.canTransition("departed", "arrived"))
        }

        // ============================================================
        // DEPENDENCY CHAINS — cross-module integration (even idx only)
        // Each chain tests 2 bugs from DIFFERENT modules than the group.
        // A test passes only when its group bugs AND chain bugs are fixed.
        // Odd idx tests have no chain, giving partial progress per bug pair.
        // ============================================================
        if (idx % 2 == 0) {
            when ((idx / 24) % 6) {
                0 -> {
                    // Needs: estimateCost (*severity) + channelScore (/latency)
                    assertTrue(Allocator.estimateCost(5, 30, 10.0) > Allocator.estimateCost(1, 30, 10.0),
                        "dep-chain-0: higher severity must cost more")
                    assertTrue(Routing.channelScore(5, 0.9, 3) > Routing.channelScore(50, 0.9, 3),
                        "dep-chain-0: lower latency must score higher")
                }
                1 -> {
                    // Needs: nextPolicy (<=1 guard) + deescalate (no-op guard)
                    val pe = PolicyEngine()
                    pe.escalate(5)
                    assertEquals("watch", pe.currentPolicy, "dep-chain-1: escalate past normal")
                    pe.deescalate(); pe.deescalate()
                    assertTrue(pe.getHistory().size <= 2, "dep-chain-1: no-op deescalate silent")
                }
                2 -> {
                    // Needs: estimateWaitTime (/) + variance (population)
                    val w = (1..4).map { QueueGuard.estimateWaitTime(it * 10, 2.0) }
                    assertTrue(abs(Statistics.variance(w) - 31.25) < 0.01,
                        "dep-chain-2: wait+variance = 31.25, got ${Statistics.variance(w)}")
                }
                3 -> {
                    // Needs: estimateRouteCost (+portFee) + estimateTurnaround (ceil)
                    assertEquals(250.0, Routing.estimateRouteCost(100.0, 2.0, 50.0),
                        "dep-chain-3: route cost adds port fee")
                    assertEquals(2.0, Allocator.estimateTurnaround(750, false),
                        "dep-chain-3: turnaround uses ceil")
                }
                4 -> {
                    // Needs: replay (keep latest) + percentile (rank formula)
                    val r = Resilience.replay(listOf(ReplayEvent("dc-$idx", 1), ReplayEvent("dc-$idx", 10)))
                    assertEquals(10, r[0].sequence, "dep-chain-4: replay keeps latest")
                    assertEquals(4, Statistics.percentile(listOf(4, 1, 9, 7), 50),
                        "dep-chain-4: percentile rank")
                }
                5 -> {
                    // Needs: shouldShed (EMERGENCY_RATIO) + sanitisePath (backslash)
                    val hl = 100; val thresh = (hl * QueueGuard.EMERGENCY_RATIO).toInt()
                    assertFalse(QueueGuard.shouldShed(thresh - 1, hl, true),
                        "dep-chain-5: below emergency threshold")
                    assertTrue(QueueGuard.shouldShed(thresh, hl, true),
                        "dep-chain-5: at emergency threshold")
                    assertFalse(Security.sanitisePath("..\\safe.txt").contains(".."),
                        "dep-chain-5: backslash traversal sanitised")
                }
            }
        }

        // ============================================================
        // Shared invariants (should always pass regardless of bugs)
        // ============================================================

        // DispatchBatch partition invariant
        val (bPlanned, bRejected) = Allocator.dispatchBatch(listOf(orderA, orderB), 1)
        assertEquals(2, bPlanned.size + bRejected.size,
            "dispatch batch must partition all orders")

        // Order validation
        if (severityA in 1..5) {
            assertNull(OrderFactory.validateOrder(orderA),
                "order with valid severity should pass validation")
        }

        // Route selection
        val blocked = if (idx % 5 == 0) setOf("beta") else emptySet()
        val route = Routing.chooseRoute(
            listOf(
                Route("alpha", 2 + (idx % 9)),
                Route("beta", idx % 3),
                Route("gamma", 4 + (idx % 4))
            ),
            blocked
        )
        assertNotNull(route, "chooseRoute must find at least one non-blocked route")
        if ("beta" in blocked) {
            assertTrue(route!!.channel != "beta",
                "blocked channels must be excluded from route selection")
        }

        // Workflow state machine invariants
        assertTrue(Workflow.canTransition("queued", "allocated"))
        assertFalse(Workflow.canTransition("arrived", "queued"),
            "terminal state cannot transition")
        assertTrue(Workflow.isTerminalState("arrived"))
        assertFalse(Workflow.isTerminalState("queued"))

        // Deduplicate invariant
        val deduped = Resilience.deduplicate(
            listOf(
                ReplayEvent("d-$idx", 1),
                ReplayEvent("d-$idx", 2),
                ReplayEvent("e-$idx", 1)
            )
        )
        assertEquals(2, deduped.size,
            "deduplicate must keep one per id")

        // Security digest determinism
        if (idx % 17 == 0) {
            val payload = "manifest:$idx"
            val sig = digest(payload)
            assertTrue(Security.verifySignature(payload, sig, sig),
                "signature of identical digests must verify")
            assertFalse(Security.verifySignature(payload, sig.drop(1), sig),
                "truncated signature must fail verification")

            val manifestSig = Security.signManifest(payload, "key")
            assertTrue(Security.verifyManifest(payload, "key", manifestSig),
                "manifest signature round-trip must verify")
        }
    }
}
