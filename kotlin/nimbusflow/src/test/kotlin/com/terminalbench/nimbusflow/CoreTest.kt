package com.terminalbench.nimbusflow

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class CoreTest {
    @Test
    fun planDispatchRespectsCapacity() {
        val out = Allocator.planDispatch(
            listOf(
                DispatchOrder("a", 1, 60),
                DispatchOrder("b", 4, 70),
                DispatchOrder("c", 4, 30)
            ),
            2
        )
        assertEquals(listOf("c", "b"), out.map { it.id })
    }

    @Test
    fun chooseRouteIgnoresBlocked() {
        val route = Routing.chooseRoute(listOf(Route("alpha", 8), Route("beta", 3)), setOf("beta"))
        assertNotNull(route)
        assertEquals("alpha", route!!.channel)
    }

    @Test
    fun nextPolicyEscalates() {
        assertEquals("restricted", Policy.nextPolicy("watch", 3))
    }

    @Test
    fun verifySignatureDigest() {
        val payload = "manifest:v1"
        val digest = Security.digest(payload)
        assertTrue(Security.verifySignature(payload, digest, digest))
        assertFalse(Security.verifySignature(payload, digest.dropLast(1), digest))
    }

    @Test
    fun replayLatestSequenceWins() {
        val replayed = Resilience.replay(listOf(ReplayEvent("x", 1), ReplayEvent("x", 2), ReplayEvent("y", 1)))
        assertEquals(2, replayed.size)
        assertEquals(2, replayed.last().sequence)
    }

    @Test
    fun queueGuardUsesHardLimit() {
        assertFalse(QueueGuard.shouldShed(9, 10, false))
        assertTrue(QueueGuard.shouldShed(11, 10, false))
        assertTrue(QueueGuard.shouldShed(8, 10, true))
    }

    @Test
    fun statisticsPercentileSparse() {
        assertEquals(4, Statistics.percentile(listOf(4, 1, 9, 7), 50))
        assertEquals(0, Statistics.percentile(emptyList(), 90))
    }

    @Test
    fun workflowGraphEnforced() {
        assertTrue(Workflow.canTransition("queued", "allocated"))
        assertFalse(Workflow.canTransition("queued", "arrived"))
    }

    @Test
    fun dispatchOrderUrgencyScore() {
        assertEquals(120, DispatchOrder("d", 3, 30).urgencyScore())
    }

    @Test
    fun flowIntegration() {
        val orders = Allocator.planDispatch(listOf(DispatchOrder("z", 5, 20)), 1)
        val route = Routing.chooseRoute(listOf(Route("north", 4)), emptySet())
        assertEquals(1, orders.size)
        assertNotNull(route)
        assertTrue(Workflow.canTransition("queued", "allocated"))
    }

    @Test
    fun replayConvergence() {
        val a = Resilience.replay(listOf(ReplayEvent("k", 1), ReplayEvent("k", 2)))
        val b = Resilience.replay(listOf(ReplayEvent("k", 2), ReplayEvent("k", 1)))
        assertEquals(a, b)
    }

    @Test
    fun contractsRequiredFields() {
        assertEquals(8160, Contracts.servicePorts["gateway"])
        assertTrue((Contracts.servicePorts["routing"] ?: 0) > 0)
    }
}
