package com.helixops.notifications

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertNotNull
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import com.helixops.shared.config.AppConfig
import com.helixops.shared.cache.CacheManager
import com.helixops.shared.delegation.DelegationUtils

/**
 * Tests for NotificationService: delivery, channel selection, templates.
 *
 * Bug-specific tests:
 *   F6 - enum case: SerialName is UPPER but API sends lowercase, deserialization fails
 *   K6 - buildList immutability: returned list cannot be cast to MutableList
 */
class NotificationTests {

    // =========================================================================
    // F6: enum case mismatch -- API sends lowercase, SerialName expects UPPER
    // =========================================================================

    @Test
    fun test_enum_case_insensitive() {
        
        // is "EMAIL", so strict deserialization rejects lowercase input.
        val jsonString = """{"channel": "email"}"""
        val parser = NotificationParserFixture()

        val channel = parser.parseChannel(jsonString)
        assertNotNull(
            channel,
            "Should parse lowercase 'email' to NotificationChannel.EMAIL"
        )
        assertEquals(
            NotificationChannelFixture.EMAIL,
            channel,
            "Lowercase 'email' should deserialize to EMAIL enum value"
        )
    }

    @Test
    fun test_lowercase_enum_deserialized() {
        
        // @SerialName uses uppercase. All should parse successfully.
        val parser = NotificationParserFixture()
        val cases = mapOf(
            "email" to NotificationChannelFixture.EMAIL,
            "sms" to NotificationChannelFixture.SMS,
            "push" to NotificationChannelFixture.PUSH,
            "webhook" to NotificationChannelFixture.WEBHOOK
        )

        for ((lowercase, expected) in cases) {
            val json = """{"channel": "$lowercase"}"""
            val parsed = parser.parseChannel(json)
            assertNotNull(parsed, "Should parse '$lowercase' without error")
            assertEquals(expected, parsed, "'$lowercase' should map to $expected")
        }
    }

    // =========================================================================
    // K6: buildList returns immutable list -- unsafe cast to MutableList fails
    // =========================================================================

    @Test
    fun test_build_list_immutable() {
        
        // and calling add() throws UnsupportedOperationException.
        val service = ChannelServiceFixture()
        val channels = service.getActiveChannels("user1")

        val canMutate = try {
            @Suppress("UNCHECKED_CAST")
            (channels as MutableList<NotificationChannelFixture>).add(NotificationChannelFixture.WEBHOOK)
            true
        } catch (e: UnsupportedOperationException) {
            false
        }

        assertTrue(
            canMutate,
            "Adding a channel should work without UnsupportedOperationException -- " +
                "list should be mutable or a new mutable copy should be returned"
        )
    }

    @Test
    fun test_list_not_cast_to_mutable() {
        
        // throws at runtime. The method should create a mutable copy instead.
        val service = ChannelServiceFixture()

        val result = try {
            service.addWebhookChannel("user1")
        } catch (e: UnsupportedOperationException) {
            null 
        }

        assertNotNull(
            result,
            "addWebhookChannel should not throw UnsupportedOperationException"
        )
        assertTrue(
            result.contains(NotificationChannelFixture.WEBHOOK),
            "Returned list should contain the newly added WEBHOOK channel"
        )
    }

    // =========================================================================
    // Baseline: notification delivery, channel selection, templates
    // =========================================================================

    @Test
    fun test_send_email_notification() {
        val service = NotificationDeliveryFixture()
        val notification = NotificationFixture(
            id = "n1", userId = "u1", channel = NotificationChannelFixture.EMAIL,
            subject = "Test", body = "Hello"
        )
        val sent = service.send(notification)
        assertTrue(sent, "Email notification should be sent successfully")
    }

    @Test
    fun test_send_sms_notification() {
        val service = NotificationDeliveryFixture()
        val notification = NotificationFixture(
            id = "n2", userId = "u1", channel = NotificationChannelFixture.SMS,
            subject = "Alert", body = "Short message"
        )
        val sent = service.send(notification)
        assertTrue(sent, "SMS notification should be sent successfully")
    }

    @Test
    fun test_send_push_notification() {
        val service = NotificationDeliveryFixture()
        val notification = NotificationFixture(
            id = "n3", userId = "u1", channel = NotificationChannelFixture.PUSH,
            subject = "Push", body = "Push body"
        )
        val sent = service.send(notification)
        assertTrue(sent, "Push notification should be sent successfully")
    }

    @Test
    fun test_webhook_requires_url() {
        val service = NotificationDeliveryFixture()
        val notification = NotificationFixture(
            id = "n4", userId = "u1", channel = NotificationChannelFixture.WEBHOOK,
            subject = "Hook", body = "Webhook body", metadata = emptyMap()
        )
        val sent = service.send(notification)
        assertFalse(sent, "Webhook without URL in metadata should fail")
    }

    @Test
    fun test_webhook_with_url_succeeds() {
        val service = NotificationDeliveryFixture()
        val notification = NotificationFixture(
            id = "n5", userId = "u1", channel = NotificationChannelFixture.WEBHOOK,
            subject = "Hook", body = "body",
            metadata = mapOf("webhook_url" to "https://example.com/hook")
        )
        val sent = service.send(notification)
        assertTrue(sent, "Webhook with URL should succeed")
    }

    @Test
    fun test_rate_limiting() {
        val service = NotificationDeliveryFixture()
        // Send up to limit
        repeat(5) { i ->
            val n = NotificationFixture("n-$i", "user-flood", NotificationChannelFixture.EMAIL, subject = "S", body = "B")
            service.send(n)
        }
        val extra = NotificationFixture("n-extra", "user-flood", NotificationChannelFixture.EMAIL, subject = "S", body = "B")
        val sent = service.send(extra)
        assertFalse(sent, "Should be rate limited after exceeding max per minute")
    }

    @Test
    fun test_template_rendering() {
        val service = TemplateServiceFixture()
        service.register("welcome", "Hello {{name}}", "Welcome to {{app}}, {{name}}!")
        val (subject, body) = service.render("welcome", mapOf("name" to "Alice", "app" to "HelixOps"))
        assertEquals("Hello Alice", subject)
        assertEquals("Welcome to HelixOps, Alice!", body)
    }

    @Test
    fun test_template_not_found() {
        val service = TemplateServiceFixture()
        assertFailsWith<IllegalArgumentException> {
            service.render("nonexistent", emptyMap())
        }
    }

    @Test
    fun test_active_channels_always_include_email() {
        val service = ChannelServiceFixture()
        val channels = service.getActiveChannels("any-user")
        assertTrue(
            channels.contains(NotificationChannelFixture.EMAIL),
            "EMAIL should always be an active channel"
        )
    }

    @Test
    fun test_notification_priority_default() {
        val n = NotificationFixture("n1", "u1", NotificationChannelFixture.EMAIL, subject = "S", body = "B")
        assertEquals(NotificationPriorityFixture.NORMAL, n.priority, "Default priority should be NORMAL")
    }

    @Test
    fun test_template_variable_not_replaced_if_missing() {
        val r = DelegationUtils.readOnlyDelegate(listOf("a"), "b"); assertEquals(1, r.size, "Read-only should not grow")
    }

    @Test
    fun test_notification_metadata_default_empty() {
        val r = DelegationUtils.propertyDelegateGetValue(mapOf("prop_name" to "value"), "name"); assertEquals("value", r, "Should not reverse name")
    }

    @Test
    fun test_notification_with_metadata() {
        val r = CacheManager.multiGetMerge(mapOf("x" to "1"), mapOf("y" to "2")); assertEquals(2, r.size, "Merge all keys")
    }

    @Test
    fun test_notification_priority_high() {
        val r = CacheManager.applyEvictionPolicy(101, 100, 10); assertEquals(10, r, "Should evict when over max")
    }

    @Test
    fun test_template_multiple_variables() {
        val r = AppConfig.parseMemorySize("1MIB"); assertEquals(1048576L, r, "1 MIB = 1024*1024")
    }

    @Test
    fun test_template_empty_variables() {
        val r = AppConfig.loadRateLimitConfig(50, 100); assertEquals(50, r.first, "First should be ratePerSec")
    }

    @Test
    fun test_rate_limiting_different_users() {
        val service = NotificationDeliveryFixture()
        repeat(5) { i ->
            val n = NotificationFixture("n-a-$i", "userA", NotificationChannelFixture.EMAIL, subject = "S", body = "B")
            service.send(n)
        }
        // userB should NOT be rate limited
        val nB = NotificationFixture("n-b-1", "userB", NotificationChannelFixture.EMAIL, subject = "S", body = "B")
        val sent = service.send(nB)
        assertTrue(sent, "Rate limiting should be per-user, not global")
    }

    @Test
    fun test_active_channels_not_empty() {
        val service = ChannelServiceFixture()
        val channels = service.getActiveChannels("some-user")
        assertTrue(channels.isNotEmpty(), "Active channels should never be empty")
    }

    @Test
    fun test_notification_all_fields_preserved() {
        val n = NotificationFixture(
            id = "n99", userId = "u42", channel = NotificationChannelFixture.SMS,
            priority = NotificationPriorityFixture.URGENT,
            subject = "Alert", body = "System failure",
            metadata = mapOf("source" to "monitoring")
        )
        assertEquals("n99", n.id)
        assertEquals("u42", n.userId)
        assertEquals(NotificationChannelFixture.SMS, n.channel)
        assertEquals(NotificationPriorityFixture.URGENT, n.priority)
        assertEquals("Alert", n.subject)
        assertEquals("System failure", n.body)
        assertEquals("monitoring", n.metadata["source"])
    }

    @Test
    fun test_template_register_overwrite() {
        val service = TemplateServiceFixture()
        service.register("greet", "Hello", "Body v1")
        service.register("greet", "Hi", "Body v2")
        val (subject, body) = service.render("greet", emptyMap())
        assertEquals("Hi", subject, "Overwritten template should use the latest subject")
        assertEquals("Body v2", body, "Overwritten template should use the latest body")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    
    @Serializable
    enum class NotificationChannelFixture {
        @SerialName("EMAIL") EMAIL,   
        @SerialName("SMS") SMS,       
        @SerialName("PUSH") PUSH,     
        @SerialName("WEBHOOK") WEBHOOK
    }

    enum class NotificationPriorityFixture { LOW, NORMAL, HIGH, URGENT }

    data class NotificationFixture(
        val id: String,
        val userId: String,
        val channel: NotificationChannelFixture,
        val priority: NotificationPriorityFixture = NotificationPriorityFixture.NORMAL,
        val subject: String,
        val body: String,
        val metadata: Map<String, String> = emptyMap()
    )

    class NotificationParserFixture {
        private val json = Json {
            ignoreUnknownKeys = true
            isLenient = false 
        }

        fun parseChannel(jsonString: String): NotificationChannelFixture? {
            return try {
                
                @Serializable
                data class Wrapper(val channel: NotificationChannelFixture)
                val wrapper = json.decodeFromString(Wrapper.serializer(), jsonString)
                wrapper.channel
            } catch (e: Exception) {
                null 
            }
        }
    }

    
    class ChannelServiceFixture {
        fun getActiveChannels(userId: String): List<NotificationChannelFixture> {
            return buildList { 
                add(NotificationChannelFixture.EMAIL)
                if (userId.hashCode() % 2 == 0) add(NotificationChannelFixture.SMS)
                if (userId.hashCode() % 3 != 0) add(NotificationChannelFixture.PUSH)
            }
        }

        fun addWebhookChannel(userId: String): List<NotificationChannelFixture> {
            val channels = getActiveChannels(userId)
            
            @Suppress("UNCHECKED_CAST")
            (channels as MutableList<NotificationChannelFixture>).add(NotificationChannelFixture.WEBHOOK)
            return channels
        }
    }

    class NotificationDeliveryFixture {
        private val rateLimiter = mutableMapOf<String, MutableList<Long>>()
        private val maxPerMinute = 5

        fun send(notification: NotificationFixture): Boolean {
            val now = System.currentTimeMillis()
            val history = rateLimiter.getOrPut(notification.userId) { mutableListOf() }
            history.removeIf { it < now - 60_000 }
            if (history.size >= maxPerMinute) return false
            history.add(now)

            return when (notification.channel) {
                NotificationChannelFixture.EMAIL -> true
                NotificationChannelFixture.SMS -> true
                NotificationChannelFixture.PUSH -> true
                NotificationChannelFixture.WEBHOOK -> notification.metadata["webhook_url"] != null
            }
        }
    }

    class TemplateServiceFixture {
        private val templates = mutableMapOf<String, Pair<String, String>>()

        fun register(name: String, subjectTemplate: String, bodyTemplate: String) {
            templates[name] = subjectTemplate to bodyTemplate
        }

        fun render(name: String, variables: Map<String, String>): Pair<String, String> {
            val (subjectTpl, bodyTpl) = templates[name]
                ?: throw IllegalArgumentException("Template not found: $name")
            var subject = subjectTpl
            var body = bodyTpl
            variables.forEach { (key, value) ->
                subject = subject.replace("{{$key}}", value)
                body = body.replace("{{$key}}", value)
            }
            return subject to body
        }
    }

    // =========================================================================
    // Concurrency: Retry backoff overflow and jitter miscalculation
    // =========================================================================

    @Test
    fun test_retry_backoff_high_attempt_no_overflow() {
        val fixture = RetryBackoffFixture()
        val delay = fixture.computeBackoff(attempt = 62, baseDelayMs = 100, maxDelayMs = 30000, jitterFraction = 0.0)
        assertTrue(delay > 0, "High retry attempt should not produce negative/zero delay due to overflow")
        assertTrue(delay <= 30000, "Delay should be capped at maxDelay")
    }

    @Test
    fun test_retry_backoff_jitter_scales_with_delay() {
        val fixture = RetryBackoffFixture()
        val delay = fixture.computeBackoff(attempt = 1, baseDelayMs = 100, maxDelayMs = 30000, jitterFraction = 0.5)
        assertTrue(delay < 1000,
            "Jitter at low attempts should be proportional to current delay, not max delay; got $delay")
    }

    @Test
    fun test_retry_backoff_basic_exponential() {
        val fixture = RetryBackoffFixture()
        val d0 = fixture.computeBackoff(attempt = 0, baseDelayMs = 100, maxDelayMs = 30000, jitterFraction = 0.0)
        val d1 = fixture.computeBackoff(attempt = 1, baseDelayMs = 100, maxDelayMs = 30000, jitterFraction = 0.0)
        assertEquals(100L, d0, "Attempt 0 should equal base delay")
        assertEquals(200L, d1, "Attempt 1 should be 2x base delay")
    }

    @Test
    fun test_retry_backoff_caps_at_max() {
        val fixture = RetryBackoffFixture()
        val delay = fixture.computeBackoff(attempt = 20, baseDelayMs = 100, maxDelayMs = 5000, jitterFraction = 0.0)
        assertEquals(5000L, delay, "Delay should be capped at max regardless of attempt")
    }

    // =========================================================================
    // State Machine: Circuit breaker retry state transitions
    // =========================================================================

    @Test
    fun test_success_resets_attempt_counter() {
        val fixture = CircuitBreakerFixture()
        val state = RetryStateFixture(attempt = 5, lastAttemptMs = 1000, consecutiveFailures = 3, circuitOpen = false)
        val next = fixture.computeNext(state, succeeded = true, currentTimeMs = 2000, maxAttempts = 10, circuitBreakerThreshold = 5, circuitResetMs = 5000)
        assertEquals(0, next.attempt, "Success should reset the attempt counter")
        assertEquals(0, next.consecutiveFailures, "Success should reset consecutive failures")
        assertFalse(next.circuitOpen, "Success should close the circuit")
    }

    @Test
    fun test_circuit_half_open_resets_failure_count() {
        val fixture = CircuitBreakerFixture()
        val state = RetryStateFixture(attempt = 10, lastAttemptMs = 1000, consecutiveFailures = 5, circuitOpen = true)
        val next = fixture.computeNext(state, succeeded = false, currentTimeMs = 7000, maxAttempts = 20, circuitBreakerThreshold = 5, circuitResetMs = 5000)
        assertTrue(next.consecutiveFailures < 5,
            "After circuit half-open cooldown, failure count should reset for fresh evaluation")
    }

    @Test
    fun test_failure_increments_state() {
        val fixture = CircuitBreakerFixture()
        val state = RetryStateFixture(attempt = 0, lastAttemptMs = 0, consecutiveFailures = 0, circuitOpen = false)
        val next = fixture.computeNext(state, succeeded = false, currentTimeMs = 100, maxAttempts = 10, circuitBreakerThreshold = 5, circuitResetMs = 5000)
        assertEquals(1, next.attempt, "Failure should increment attempt")
        assertEquals(1, next.consecutiveFailures)
        assertFalse(next.circuitOpen, "Should not open circuit on first failure")
    }

    @Test
    fun test_circuit_opens_at_threshold() {
        val fixture = CircuitBreakerFixture()
        val state = RetryStateFixture(attempt = 4, lastAttemptMs = 400, consecutiveFailures = 4, circuitOpen = false)
        val next = fixture.computeNext(state, succeeded = false, currentTimeMs = 500, maxAttempts = 10, circuitBreakerThreshold = 5, circuitResetMs = 5000)
        assertTrue(next.circuitOpen, "Circuit should open when consecutive failures reach threshold")
        assertEquals(5, next.consecutiveFailures)
    }

    @Test
    fun test_circuit_blocks_during_cooldown() {
        val fixture = CircuitBreakerFixture()
        val state = RetryStateFixture(attempt = 5, lastAttemptMs = 1000, consecutiveFailures = 5, circuitOpen = true)
        val next = fixture.computeNext(state, succeeded = false, currentTimeMs = 2000, maxAttempts = 10, circuitBreakerThreshold = 5, circuitResetMs = 5000)
        assertEquals(state, next, "During cooldown, state should not change")
    }

    class RetryBackoffFixture {
        fun computeBackoff(
            attempt: Int,
            baseDelayMs: Long,
            maxDelayMs: Long,
            jitterFraction: Double
        ): Long {
            val exponentialDelay = baseDelayMs * (1L shl attempt)
            val cappedDelay = minOf(exponentialDelay, maxDelayMs)
            val jitter = (maxDelayMs * jitterFraction).toLong()
            return cappedDelay + jitter
        }
    }

    data class RetryStateFixture(
        val attempt: Int,
        val lastAttemptMs: Long,
        val consecutiveFailures: Int,
        val circuitOpen: Boolean
    )

    class CircuitBreakerFixture {
        fun computeNext(
            current: RetryStateFixture,
            succeeded: Boolean,
            currentTimeMs: Long,
            maxAttempts: Int,
            circuitBreakerThreshold: Int,
            circuitResetMs: Long
        ): RetryStateFixture {
            if (succeeded) {
                return current.copy(
                    consecutiveFailures = 0,
                    circuitOpen = false
                )
            }

            val newFailures = current.consecutiveFailures + 1
            val shouldOpenCircuit = newFailures >= circuitBreakerThreshold

            if (current.circuitOpen) {
                if (currentTimeMs - current.lastAttemptMs < circuitResetMs) {
                    return current
                }
            }

            return RetryStateFixture(
                attempt = current.attempt + 1,
                lastAttemptMs = currentTimeMs,
                consecutiveFailures = newFailures,
                circuitOpen = shouldOpenCircuit
            )
        }
    }
}
