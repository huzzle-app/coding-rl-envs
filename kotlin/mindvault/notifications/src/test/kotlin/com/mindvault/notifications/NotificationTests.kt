package com.mindvault.notifications

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
        val parser = NotificationParserStub()

        val channel = parser.parseChannel(jsonString)
        assertNotNull(
            channel,
            "Should parse lowercase 'email' to NotificationChannel.EMAIL"
        )
        assertEquals(
            NotificationChannelLocal.EMAIL,
            channel,
            "Lowercase 'email' should deserialize to EMAIL enum value"
        )
    }

    @Test
    fun test_lowercase_enum_deserialized() {
        
        // @SerialName uses uppercase. All should parse successfully.
        val parser = NotificationParserStub()
        val cases = mapOf(
            "email" to NotificationChannelLocal.EMAIL,
            "sms" to NotificationChannelLocal.SMS,
            "push" to NotificationChannelLocal.PUSH,
            "webhook" to NotificationChannelLocal.WEBHOOK
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
        val service = ChannelServiceStub()
        val channels = service.getActiveChannels("user1")

        val canMutate = try {
            @Suppress("UNCHECKED_CAST")
            (channels as MutableList<NotificationChannelLocal>).add(NotificationChannelLocal.WEBHOOK)
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
        val service = ChannelServiceStub()

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
            result.contains(NotificationChannelLocal.WEBHOOK),
            "Returned list should contain the newly added WEBHOOK channel"
        )
    }

    // =========================================================================
    // Baseline: notification delivery, channel selection, templates
    // =========================================================================

    @Test
    fun test_send_email_notification() {
        val service = NotificationDeliveryStub()
        val notification = NotificationLocal(
            id = "n1", userId = "u1", channel = NotificationChannelLocal.EMAIL,
            subject = "Test", body = "Hello"
        )
        val sent = service.send(notification)
        assertTrue(sent, "Email notification should be sent successfully")
    }

    @Test
    fun test_send_sms_notification() {
        val service = NotificationDeliveryStub()
        val notification = NotificationLocal(
            id = "n2", userId = "u1", channel = NotificationChannelLocal.SMS,
            subject = "Alert", body = "Short message"
        )
        val sent = service.send(notification)
        assertTrue(sent, "SMS notification should be sent successfully")
    }

    @Test
    fun test_send_push_notification() {
        val service = NotificationDeliveryStub()
        val notification = NotificationLocal(
            id = "n3", userId = "u1", channel = NotificationChannelLocal.PUSH,
            subject = "Push", body = "Push body"
        )
        val sent = service.send(notification)
        assertTrue(sent, "Push notification should be sent successfully")
    }

    @Test
    fun test_webhook_requires_url() {
        val service = NotificationDeliveryStub()
        val notification = NotificationLocal(
            id = "n4", userId = "u1", channel = NotificationChannelLocal.WEBHOOK,
            subject = "Hook", body = "Webhook body", metadata = emptyMap()
        )
        val sent = service.send(notification)
        assertFalse(sent, "Webhook without URL in metadata should fail")
    }

    @Test
    fun test_webhook_with_url_succeeds() {
        val service = NotificationDeliveryStub()
        val notification = NotificationLocal(
            id = "n5", userId = "u1", channel = NotificationChannelLocal.WEBHOOK,
            subject = "Hook", body = "body",
            metadata = mapOf("webhook_url" to "https://example.com/hook")
        )
        val sent = service.send(notification)
        assertTrue(sent, "Webhook with URL should succeed")
    }

    @Test
    fun test_rate_limiting() {
        val service = NotificationDeliveryStub()
        // Send up to limit
        repeat(5) { i ->
            val n = NotificationLocal("n-$i", "user-flood", NotificationChannelLocal.EMAIL, subject = "S", body = "B")
            service.send(n)
        }
        val extra = NotificationLocal("n-extra", "user-flood", NotificationChannelLocal.EMAIL, subject = "S", body = "B")
        val sent = service.send(extra)
        assertFalse(sent, "Should be rate limited after exceeding max per minute")
    }

    @Test
    fun test_template_rendering() {
        val service = TemplateServiceStub()
        service.register("welcome", "Hello {{name}}", "Welcome to {{app}}, {{name}}!")
        val (subject, body) = service.render("welcome", mapOf("name" to "Alice", "app" to "MindVault"))
        assertEquals("Hello Alice", subject)
        assertEquals("Welcome to MindVault, Alice!", body)
    }

    @Test
    fun test_template_not_found() {
        val service = TemplateServiceStub()
        assertFailsWith<IllegalArgumentException> {
            service.render("nonexistent", emptyMap())
        }
    }

    @Test
    fun test_active_channels_always_include_email() {
        val service = ChannelServiceStub()
        val channels = service.getActiveChannels("any-user")
        assertTrue(
            channels.contains(NotificationChannelLocal.EMAIL),
            "EMAIL should always be an active channel"
        )
    }

    @Test
    fun test_notification_priority_default() {
        val n = NotificationLocal("n1", "u1", NotificationChannelLocal.EMAIL, subject = "S", body = "B")
        assertEquals(NotificationPriorityLocal.NORMAL, n.priority, "Default priority should be NORMAL")
    }

    @Test
    fun test_template_variable_not_replaced_if_missing() {
        val service = TemplateServiceStub()
        service.register("test", "Hello {{name}}", "Body {{unknown}}")
        val (subject, body) = service.render("test", mapOf("name" to "Bob"))
        assertEquals("Hello Bob", subject)
        assertEquals("Body {{unknown}}", body, "Unreplaced variable should remain as-is")
    }

    @Test
    fun test_notification_metadata_default_empty() {
        val n = NotificationLocal("n1", "u1", NotificationChannelLocal.EMAIL, subject = "S", body = "B")
        assertTrue(n.metadata.isEmpty(), "Default metadata should be empty")
    }

    @Test
    fun test_notification_with_metadata() {
        val n = NotificationLocal(
            "n1", "u1", NotificationChannelLocal.EMAIL,
            subject = "S", body = "B",
            metadata = mapOf("key1" to "val1", "key2" to "val2")
        )
        assertEquals(2, n.metadata.size, "Metadata should contain 2 entries")
        assertEquals("val1", n.metadata["key1"])
    }

    @Test
    fun test_notification_priority_high() {
        val n = NotificationLocal(
            "n1", "u1", NotificationChannelLocal.PUSH,
            priority = NotificationPriorityLocal.HIGH,
            subject = "Urgent", body = "Action required"
        )
        assertEquals(NotificationPriorityLocal.HIGH, n.priority)
    }

    @Test
    fun test_template_multiple_variables() {
        val service = TemplateServiceStub()
        service.register("multi", "{{greeting}} {{name}}", "Dear {{name}}, your code is {{status}}.")
        val (subject, body) = service.render("multi", mapOf("greeting" to "Hi", "name" to "Bob", "status" to "ready"))
        assertEquals("Hi Bob", subject)
        assertEquals("Dear Bob, your code is ready.", body)
    }

    @Test
    fun test_template_empty_variables() {
        val service = TemplateServiceStub()
        service.register("simple", "Hello", "World")
        val (subject, body) = service.render("simple", emptyMap())
        assertEquals("Hello", subject, "Template with no variables should render as-is")
        assertEquals("World", body)
    }

    @Test
    fun test_rate_limiting_different_users() {
        val service = NotificationDeliveryStub()
        repeat(5) { i ->
            val n = NotificationLocal("n-a-$i", "userA", NotificationChannelLocal.EMAIL, subject = "S", body = "B")
            service.send(n)
        }
        // userB should NOT be rate limited
        val nB = NotificationLocal("n-b-1", "userB", NotificationChannelLocal.EMAIL, subject = "S", body = "B")
        val sent = service.send(nB)
        assertTrue(sent, "Rate limiting should be per-user, not global")
    }

    @Test
    fun test_active_channels_not_empty() {
        val service = ChannelServiceStub()
        val channels = service.getActiveChannels("some-user")
        assertTrue(channels.isNotEmpty(), "Active channels should never be empty")
    }

    @Test
    fun test_notification_all_fields_preserved() {
        val n = NotificationLocal(
            id = "n99", userId = "u42", channel = NotificationChannelLocal.SMS,
            priority = NotificationPriorityLocal.URGENT,
            subject = "Alert", body = "System failure",
            metadata = mapOf("source" to "monitoring")
        )
        assertEquals("n99", n.id)
        assertEquals("u42", n.userId)
        assertEquals(NotificationChannelLocal.SMS, n.channel)
        assertEquals(NotificationPriorityLocal.URGENT, n.priority)
        assertEquals("Alert", n.subject)
        assertEquals("System failure", n.body)
        assertEquals("monitoring", n.metadata["source"])
    }

    @Test
    fun test_template_register_overwrite() {
        val service = TemplateServiceStub()
        service.register("greet", "Hello", "Body v1")
        service.register("greet", "Hi", "Body v2")
        val (subject, body) = service.render("greet", emptyMap())
        assertEquals("Hi", subject, "Overwritten template should use the latest subject")
        assertEquals("Body v2", body, "Overwritten template should use the latest body")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    
    @Serializable
    enum class NotificationChannelLocal {
        @SerialName("EMAIL") EMAIL,   
        @SerialName("SMS") SMS,       
        @SerialName("PUSH") PUSH,     
        @SerialName("WEBHOOK") WEBHOOK
    }

    enum class NotificationPriorityLocal { LOW, NORMAL, HIGH, URGENT }

    data class NotificationLocal(
        val id: String,
        val userId: String,
        val channel: NotificationChannelLocal,
        val priority: NotificationPriorityLocal = NotificationPriorityLocal.NORMAL,
        val subject: String,
        val body: String,
        val metadata: Map<String, String> = emptyMap()
    )

    class NotificationParserStub {
        private val json = Json {
            ignoreUnknownKeys = true
            isLenient = false 
        }

        fun parseChannel(jsonString: String): NotificationChannelLocal? {
            return try {
                
                @Serializable
                data class Wrapper(val channel: NotificationChannelLocal)
                val wrapper = json.decodeFromString(Wrapper.serializer(), jsonString)
                wrapper.channel
            } catch (e: Exception) {
                null 
            }
        }
    }

    
    class ChannelServiceStub {
        fun getActiveChannels(userId: String): List<NotificationChannelLocal> {
            return buildList { 
                add(NotificationChannelLocal.EMAIL)
                if (userId.hashCode() % 2 == 0) add(NotificationChannelLocal.SMS)
                if (userId.hashCode() % 3 != 0) add(NotificationChannelLocal.PUSH)
            }
        }

        fun addWebhookChannel(userId: String): List<NotificationChannelLocal> {
            val channels = getActiveChannels(userId)
            
            @Suppress("UNCHECKED_CAST")
            (channels as MutableList<NotificationChannelLocal>).add(NotificationChannelLocal.WEBHOOK)
            return channels
        }
    }

    class NotificationDeliveryStub {
        private val rateLimiter = mutableMapOf<String, MutableList<Long>>()
        private val maxPerMinute = 5

        fun send(notification: NotificationLocal): Boolean {
            val now = System.currentTimeMillis()
            val history = rateLimiter.getOrPut(notification.userId) { mutableListOf() }
            history.removeIf { it < now - 60_000 }
            if (history.size >= maxPerMinute) return false
            history.add(now)

            return when (notification.channel) {
                NotificationChannelLocal.EMAIL -> true
                NotificationChannelLocal.SMS -> true
                NotificationChannelLocal.PUSH -> true
                NotificationChannelLocal.WEBHOOK -> notification.metadata["webhook_url"] != null
            }
        }
    }

    class TemplateServiceStub {
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
}
