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
        val severityA = (idx % 7) + 1
        val severityB = ((idx * 3) % 7) + 1
        val slaA = 20 + (idx % 90)
        val slaB = 20 + ((idx * 2) % 90)

        val orderA = DispatchOrder("a-$idx", severityA, slaA)
        val orderB = DispatchOrder("b-$idx", severityB, slaB)

        val planned = Allocator.planDispatch(
            listOf(
                DispatchOrder(orderA.id, orderA.urgencyScore(), slaA),
                DispatchOrder(orderB.id, orderB.urgencyScore(), slaB),
                DispatchOrder("c-$idx", (idx % 50) + 2, 40 + (idx % 30))
            ),
            2
        )

        assertTrue(planned.isNotEmpty())
        assertTrue(planned.size <= 2)
        if (planned.size == 2) {
            assertTrue(planned[0].urgency >= planned[1].urgency)
        }

        // DispatchBatch + ValidateOrder
        val (bPlanned, bRejected) = Allocator.dispatchBatch(listOf(orderA, orderB), 1)
        assertEquals(2, bPlanned.size + bRejected.size)
        if (severityA in 1..5) {
            assertNull(OrderFactory.validateOrder(orderA))
        }

        val blocked = if (idx % 5 == 0) setOf("beta") else emptySet()
        val route = Routing.chooseRoute(
            listOf(
                Route("alpha", 2 + (idx % 9)),
                Route("beta", idx % 3),
                Route("gamma", 4 + (idx % 4))
            ),
            blocked
        )

        assertNotNull(route)
        if ("beta" in blocked) {
            assertTrue(route!!.channel != "beta")
        }

        // ChannelScore + TransitTime
        val cs = Routing.channelScore(route!!.latency + 1, 0.85, idx % 5 + 1)
        assertTrue(cs >= 0.0)
        val tt = Routing.estimateTransitTime(100.0 + idx, 12.0)
        assertTrue(tt > 0.0)

        val src = if (idx % 2 == 0) "queued" else "allocated"
        val dst = if (src == "queued") "allocated" else "departed"
        assertTrue(Workflow.canTransition(src, dst))
        assertFalse(Workflow.canTransition("arrived", "queued"))

        // ShortestPath + IsTerminalState
        val sp = Workflow.shortestPath("queued", "arrived")
        assertNotNull(sp)
        assertTrue(Workflow.isTerminalState("arrived"))
        assertFalse(Workflow.isTerminalState("queued"))

        val policyState = Policy.nextPolicy(if (idx % 2 == 0) "normal" else "watch", 2 + (idx % 2))
        assertTrue(policyState in setOf("watch", "restricted", "halted"))

        // PreviousPolicy + CheckSlaCompliance
        val prev = Policy.previousPolicy(policyState)
        assertNotNull(prev)
        val slaOk = Policy.checkSlaCompliance(idx % 80, 60)
        assertEquals(idx % 80 <= 60, slaOk)

        val depth = (idx % 30) + 1
        assertFalse(QueueGuard.shouldShed(depth, 40, false))
        assertTrue(QueueGuard.shouldShed(41, 40, false))

        // QueueHealth + EstimateWaitTime
        val health = QueueHealthMonitor.check(depth, 40)
        assertNotNull(health.status)
        val wt = QueueGuard.estimateWaitTime(depth, 2.0)
        assertTrue(wt >= 0.0)

        val replayed = Resilience.replay(
            listOf(
                ReplayEvent("k-${idx % 17}", 1),
                ReplayEvent("k-${idx % 17}", 2),
                ReplayEvent("z-${idx % 13}", 1)
            )
        )

        assertTrue(replayed.size >= 2)
        assertTrue(replayed.last().sequence >= 1)

        // Deduplicate + ReplayConverges
        val deduped = Resilience.deduplicate(
            listOf(
                ReplayEvent("d-$idx", 1),
                ReplayEvent("d-$idx", 2),
                ReplayEvent("e-$idx", 1)
            )
        )
        assertEquals(2, deduped.size)
        assertTrue(Resilience.replayConverges(replayed, replayed))

        val p50 = Statistics.percentile(listOf(idx % 11, (idx * 7) % 11, (idx * 5) % 11, (idx * 3) % 11), 50)
        assertTrue(p50 >= 0)

        // Mean + MovingAverage
        val m = Statistics.mean(listOf(1.0 + idx % 5, 2.0 + idx % 3, 3.0))
        assertTrue(m > 0.0)
        val ma = Statistics.movingAverage(listOf(1.0, 2.0, 3.0, 4.0), 2)
        assertTrue(ma.isNotEmpty())

        if (idx % 17 == 0) {
            val payload = "manifest:$idx"
            val sig = digest(payload)
            assertTrue(Security.verifySignature(payload, sig, sig))
            assertFalse(Security.verifySignature(payload, sig.drop(1), sig))

            // SignManifest + VerifyManifest + SanitisePath
            val manifestSig = Security.signManifest(payload, "key")
            assertTrue(Security.verifyManifest(payload, "key", manifestSig))
            assertEquals("safe.txt", Security.sanitisePath("../safe.txt"))
        }

        // EstimateCost + ServiceRegistry
        val cost = Allocator.estimateCost(idx % 5 + 1, slaA, 10.0)
        assertTrue(cost >= 0.0)
        val url = ServiceRegistry.getServiceUrl("gateway")
        assertNotNull(url)
    }
}
