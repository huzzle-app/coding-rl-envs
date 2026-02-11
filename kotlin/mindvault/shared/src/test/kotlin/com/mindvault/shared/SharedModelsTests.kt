package com.mindvault.shared

import kotlinx.coroutines.*
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertNotEquals
import kotlin.test.assertFailsWith

/**
 * Tests for shared models: singletons, enums, casting, database config.
 *
 * Bug-specific tests:
 *   C7 - Object singleton has mutable state that leaks between requests
 *   C8 - Enum @SerialName missing for some entries (wire format mismatch)
 *   B6 - Unchecked Map<String,Any> cast from JSON parsing
 *   E7 - varchar column length not validated, silent truncation
 *   E8 - Database pool size too small for concurrent operations
 */
class SharedModelsTests {

    // =========================================================================
    // C7: Object singleton with mutable state
    // =========================================================================

    @Test
    fun test_object_state_isolated() {
        
        // Changes in one request/test leak to others because singleton is shared
        val defaults = LocalNotificationDefaults
        defaults.defaultChannel = "sms"
        defaults.maxRetries = 10

        // Simulate a second "request" that expects default values
        val freshDefaults = LocalNotificationDefaults
        assertEquals(
            "email",
            freshDefaults.defaultChannel,
            "Singleton mutable state should not leak between requests; expected 'email' but got '${freshDefaults.defaultChannel}'"
        )
    }

    @Test
    fun test_no_singleton_leak() = runTest {
        
        val defaults = LocalNotificationDefaults
        defaults.reset()

        val jobs = (1..10).map { i ->
            async(Dispatchers.Default) {
                defaults.defaultChannel = "channel_$i"
                delay(1)
                defaults.defaultChannel
            }
        }

        val results = jobs.awaitAll()
        // With mutable singleton state, values will be mixed up across coroutines
        // Ideally each scope should have isolated state
        val allSame = results.all { it == results.first() }
        assertFalse(
            allSame && results.first() != "email",
            "Singleton state should not leak between concurrent accesses"
        )
    }

    // =========================================================================
    // C8: Enum @SerialName missing for some entries
    // =========================================================================

    @Test
    fun test_enum_serial_name_correct() {
        
        // Serialized name will be "DOCUMENT_DELETED" instead of "document_deleted"
        val allNamesSnakeCase = LocalEventType.values().all { entry ->
            entry.serialName.matches(Regex("[a-z_]+"))
        }
        assertTrue(
            allNamesSnakeCase,
            "All enum entries should have snake_case @SerialName; some are missing annotations"
        )
    }

    @Test
    fun test_wire_format_matches() {
        
        val deleted = LocalEventType.DOCUMENT_DELETED
        assertEquals(
            "document_deleted",
            deleted.serialName,
            "DOCUMENT_DELETED should serialize as 'document_deleted', not '${deleted.serialName}'"
        )
        val left = LocalEventType.USER_LEFT
        assertEquals(
            "user_left",
            left.serialName,
            "USER_LEFT should serialize as 'user_left', not '${left.serialName}'"
        )
    }

    // =========================================================================
    // B6: Unchecked Map<String,Any> cast
    // =========================================================================

    @Test
    fun test_map_cast_safe() {
        
        // ClassCastException at runtime when types don't match
        val parser = LocalJsonParser()
        val json = """{"name": "doc1", "size": 42, "nested": {"key": "value"}}"""
        val result = parser.parseToTypedMap(json)
        assertTrue(
            result.castSafe,
            "Map values should be cast safely with type checking, not unchecked cast"
        )
    }

    @Test
    fun test_nested_json_typed() {
        
        val parser = LocalJsonParser()
        val json = """{"metadata": {"count": 5, "active": true}}"""
        val result = parser.parseToTypedMap(json)
        assertFalse(
            result.usedUncheckedCast,
            "Should not use unchecked cast for nested JSON structures"
        )
    }

    // =========================================================================
    // E7: varchar length validation / silent truncation
    // =========================================================================

    @Test
    fun test_varchar_length_validated() {
        
        // Long strings are silently truncated by the database
        val repo = LocalDocumentRepo()
        val longTitle = "A".repeat(500)
        val result = repo.save(title = longTitle, content = "test")
        assertTrue(
            result.lengthValidated,
            "Title length should be validated before saving to varchar(255) column"
        )
    }

    @Test
    fun test_no_silent_truncation() {
        
        val repo = LocalDocumentRepo()
        val longTitle = "B".repeat(300)
        val result = repo.save(title = longTitle, content = "test")
        assertFalse(
            result.wasTruncated,
            "Long strings should be rejected, not silently truncated"
        )
        assertNotNull(
            result.validationError,
            "Should return validation error for string exceeding varchar limit"
        )
    }

    // =========================================================================
    // E8: Pool size too small
    // =========================================================================

    @Test
    fun test_pool_size_sufficient() {
        
        val dbFactory = LocalDatabaseFactory()
        val poolSize = dbFactory.getMaxPoolSize()
        assertTrue(
            poolSize >= 10,
            "Connection pool size should be >= 10 for 10 concurrent services, but was $poolSize"
        )
    }

    @Test
    fun test_concurrent_transactions_succeed() = runTest {
        
        val dbFactory = LocalDatabaseFactory()
        val concurrentOps = 5
        val results = (1..concurrentOps).map { i ->
            async(Dispatchers.Default) {
                dbFactory.executeInTransaction("operation_$i")
            }
        }
        val allResults = results.awaitAll()
        assertTrue(
            allResults.all { it.succeeded },
            "All ${concurrentOps} concurrent transactions should succeed; " +
            "failures: ${allResults.count { !it.succeeded }}"
        )
    }

    // =========================================================================
    // Baseline: Model basics
    // =========================================================================

    @Test
    fun test_notification_defaults_reset() {
        val defaults = LocalNotificationDefaults
        defaults.defaultChannel = "push"
        defaults.reset()
        assertEquals("email", defaults.defaultChannel, "reset() should restore default channel")
        assertEquals(3, defaults.maxRetries, "reset() should restore default retries")
    }

    @Test
    fun test_notification_rate_limits() {
        val defaults = LocalNotificationDefaults
        val emailRate = defaults.getMaxNotificationsPerMinute("EMAIL")
        assertTrue(emailRate > 0, "EMAIL rate limit should be positive")
    }

    @Test
    fun test_enum_has_all_entries() {
        val entries = LocalEventType.values()
        assertEquals(6, entries.size, "EventType should have 6 entries")
    }

    @Test
    fun test_enum_document_created_serial_name() {
        val created = LocalEventType.DOCUMENT_CREATED
        assertEquals("document_created", created.serialName, "DOCUMENT_CREATED should have snake_case serial name")
    }

    @Test
    fun test_json_parser_handles_empty_object() {
        val parser = LocalJsonParser()
        val result = parser.parseToTypedMap("{}")
        assertTrue(result.data.isEmpty(), "Empty JSON object should produce empty map")
    }

    @Test
    fun test_document_save_valid_title() {
        val repo = LocalDocumentRepo()
        val result = repo.save(title = "Valid Title", content = "Content")
        assertTrue(result.saved, "Document with valid title should save successfully")
    }

    @Test
    fun test_pool_autocommit_disabled() {
        val dbFactory = LocalDatabaseFactory()
        assertFalse(dbFactory.isAutoCommit(), "Pool should have autoCommit disabled for transaction safety")
    }

    @Test
    fun test_notification_defaults_batch_size() {
        val defaults = LocalNotificationDefaults
        defaults.reset()
        assertEquals(100, defaults.batchSize, "Default batch size should be 100")
    }

    @Test
    fun test_enum_user_joined_serial_name() {
        val joined = LocalEventType.USER_JOINED
        assertEquals("user_joined", joined.serialName, "USER_JOINED should have correct serial name")
    }

    @Test
    fun test_enum_search_indexed_serial_name() {
        val indexed = LocalEventType.SEARCH_INDEXED
        assertEquals("search_indexed", indexed.serialName, "SEARCH_INDEXED should have correct serial name")
    }

    @Test
    fun test_notification_webhook_rate_limit() {
        val defaults = LocalNotificationDefaults
        val webhookRate = defaults.getMaxNotificationsPerMinute("WEBHOOK")
        assertEquals(50, webhookRate, "WEBHOOK rate limit should be 50")
    }

    @Test
    fun test_notification_unknown_channel_fallback() {
        val defaults = LocalNotificationDefaults
        val unknownRate = defaults.getMaxNotificationsPerMinute("UNKNOWN")
        assertEquals(10, unknownRate, "Unknown channel should fall back to default rate of 10")
    }

    @Test
    fun test_document_save_empty_title() {
        val repo = LocalDocumentRepo()
        val result = repo.save(title = "", content = "content")
        assertTrue(result.saved, "Empty title should save (validation is for length, not emptiness)")
    }

    @Test
    fun test_pool_size_returned() {
        val dbFactory = LocalDatabaseFactory()
        val size = dbFactory.getMaxPoolSize()
        assertTrue(size > 0, "Pool size should be positive")
    }

    @Test
    fun test_enum_values_count() {
        assertEquals(6, LocalEventType.values().size, "EventType should have exactly 6 entries")
    }

    @Test
    fun test_enum_document_updated_serial_name() {
        val updated = LocalEventType.DOCUMENT_UPDATED
        assertEquals("document_updated", updated.serialName, "DOCUMENT_UPDATED should serialize correctly")
    }

    @Test
    fun test_notification_defaults_max_retries() {
        val defaults = LocalNotificationDefaults
        defaults.reset()
        assertEquals(3, defaults.maxRetries, "Default maxRetries should be 3")
    }

    @Test
    fun test_notification_sms_rate_limit() {
        val defaults = LocalNotificationDefaults
        val smsRate = defaults.getMaxNotificationsPerMinute("SMS")
        assertEquals(5, smsRate, "SMS rate limit should be 5")
    }

    @Test
    fun test_notification_push_rate_limit() {
        val defaults = LocalNotificationDefaults
        val pushRate = defaults.getMaxNotificationsPerMinute("PUSH")
        assertEquals(20, pushRate, "PUSH rate limit should be 20")
    }

    @Test
    fun test_document_save_at_varchar_limit() {
        val repo = LocalDocumentRepo()
        val exactTitle = "C".repeat(255)
        val result = repo.save(title = exactTitle, content = "content")
        assertTrue(result.saved, "Document with exactly 255 character title should save")
        assertTrue(result.lengthValidated, "Title at varchar limit should be validated as ok")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    
    object LocalNotificationDefaults {
        var defaultChannel = "email"
        var maxRetries = 3
        var batchSize = 100

        private val rateLimits = mutableMapOf(
            "EMAIL" to 10, "SMS" to 5, "PUSH" to 20, "WEBHOOK" to 50
        )

        fun getMaxNotificationsPerMinute(channel: String): Int = rateLimits[channel] ?: 10

        fun reset() {
            defaultChannel = "email"
            maxRetries = 3
            batchSize = 100
        }
    }

    
    enum class LocalEventType(val serialName: String) {
        DOCUMENT_CREATED("document_created"),
        DOCUMENT_UPDATED("document_updated"),
        DOCUMENT_DELETED("DOCUMENT_DELETED"), 
        USER_JOINED("user_joined"),
        USER_LEFT("USER_LEFT"), 
        SEARCH_INDEXED("search_indexed")
    }

    
    data class ParseResult(
        val data: Map<String, Any> = emptyMap(),
        val castSafe: Boolean,
        val usedUncheckedCast: Boolean
    )

    class LocalJsonParser {
        fun parseToTypedMap(json: String): ParseResult {
            
            return ParseResult(
                data = mapOf("raw" to json),
                castSafe = false, 
                usedUncheckedCast = true 
            )
        }
    }

    
    data class SaveResult(
        val saved: Boolean,
        val lengthValidated: Boolean,
        val wasTruncated: Boolean,
        val validationError: String? = null
    )

    class LocalDocumentRepo {
        fun save(title: String, content: String): SaveResult {
            
            return if (title.length > 255) {
                SaveResult(
                    saved = true, 
                    lengthValidated = false, 
                    wasTruncated = true, 
                    validationError = null 
                )
            } else {
                SaveResult(saved = true, lengthValidated = true, wasTruncated = false)
            }
        }
    }

    
    data class TransactionResult(val succeeded: Boolean, val error: String? = null)

    class LocalDatabaseFactory {
        private val maxPoolSize = 2 
        private var activeConnections = 0

        fun getMaxPoolSize(): Int = maxPoolSize

        fun isAutoCommit(): Boolean = false

        suspend fun executeInTransaction(operation: String): TransactionResult {
            
            activeConnections++
            return if (activeConnections > maxPoolSize) {
                TransactionResult(
                    succeeded = false, 
                    error = "Connection pool exhausted (active=$activeConnections, max=$maxPoolSize)"
                )
            } else {
                delay(10) // simulate work
                activeConnections--
                TransactionResult(succeeded = true)
            }
        }
    }
}
