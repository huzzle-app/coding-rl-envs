package com.helixops.shared

import kotlinx.coroutines.runBlocking
import org.junit.jupiter.api.DynamicTest
import org.junit.jupiter.api.Tag
import org.junit.jupiter.api.TestFactory
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue

@Tag("stress")
class HyperMatrixTests {

    @TestFactory
    fun hyperMatrix(): List<DynamicTest> {
        val total = 12000
        return (0 until total).map { idx ->
            DynamicTest.dynamicTest("hyper_case_$idx") {
                when (idx % 6) {
                    0 -> configMatrix()
                    1 -> securityMatrix()
                    2 -> delegationMatrix()
                    3 -> eventBusMatrix(idx)
                    4 -> kotlinValueMatrix()
                    else -> serializationMatrix()
                }
            }
        }
    }

    private fun configMatrix() {
        val build = ConfigTests.GradleBuildFixture()
        assertFalse(
            build.rootAppliesKotlinPlugin(),
            "Root gradle plugin leakage should be fixed"
        )
    }

    private fun securityMatrix() {
        val security = SecurityTests.JwtProviderFixture()
        assertTrue(security.usesStringEqualsForApiKey())
        assertFalse(security.usesConstantTimeComparison())
        assertTrue(security.validateApiKey("stable-key", "stable-key"))
    }

    private fun delegationMatrix() {
        val serializer = DelegationTests.EventSerializerFixture()
        assertFalse(
            serializer.hasMutableState(),
            "Serializer companion-style components must be stateless"
        )
    }

    private fun eventBusMatrix(idx: Int) {
        val bus = EventBusTests.EventBusFixture()
        val received = mutableListOf<String>()
        bus.subscribe("evt") { received.add(it.id) }

        runBlocking {
            bus.publish(EventBusTests.DomainEventFixture("e-$idx", "evt", "payload-$idx"))
        }

        assertTrue(received.isNotEmpty())
        assertTrue(bus.usesUnconfinedDispatcher())
    }

    private fun kotlinValueMatrix() {
        val info = KotlinUtilTests.ValueClassInfoFixture()
        assertTrue(
            info.usesJvmInlineAnnotation("UserId"),
            "UserId should use @JvmInline value class semantics"
        )
        assertFalse(info.usesDeprecatedInlineKeyword("UserId"))
    }

    private fun serializationMatrix() {
        val serializer = SerializationTests.SerializationUtilsFixture()
        val parsed = serializer.parseDynamic("""{"node":"x","weight":7}""")
        assertFalse(parsed.usesJsonElement)
        assertTrue(parsed.returnsMapStringAny)
        assertFalse(parsed.canRoundTrip)
        assertEquals(true, parsed.returnsMapStringAny && !parsed.canRoundTrip)
    }
}
