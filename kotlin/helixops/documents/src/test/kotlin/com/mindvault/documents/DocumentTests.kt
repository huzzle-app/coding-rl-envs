package com.helixops.documents

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.ObjectInputStream
import java.io.ObjectOutputStream
import java.time.Instant
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.test.assertFailsWith

/**
 * Tests for the documents module: CRUD, versioning, and bug-specific scenarios.
 *
 * Bug-specific tests:
 *   A3 - Flow cancellation does not release resources
 *   A4 - Unstructured scope: coroutines escape parent lifecycle
 *   B1 - Platform type from JDBC ResultSet (String! can be null)
 *   C1 - ByteArray equality uses reference, not content
 *   C2 - data class copy() shallow-copies collection fields
 *   E1 - suspendedTransaction does not respect coroutine cancellation
 *   E2 - SchemaUtils.create is not idempotent (fails if table exists)
 *   F1 - Instant serializer loses nanosecond precision via toString
 *   I6 - Unsafe deserialization of untrusted data via ObjectInputStream
 */
class DocumentTests {

    // =========================================================================
    // A3: Flow cancellation cleanup
    // =========================================================================

    @Test
    fun test_flow_cancellation_respected() = runTest {
        
        // should be released. The buggy code opens a DB connection before the flow
        // and may not properly close it if cancellation occurs mid-stream.
        val service = DocumentStreamService()
        val collectedDocs = mutableListOf<String>()
        val job = launch {
            service.streamDocuments("owner1").collect { doc ->
                collectedDocs.add(doc)
                if (collectedDocs.size >= 2) {
                    cancel() // cancel mid-stream
                }
            }
        }
        job.join()

        assertTrue(
            service.connectionClosed,
            "Database connection should be closed after flow cancellation"
        )
    }

    @Test
    fun test_timeout_fires_on_slow_flow() = runTest {
        
        val service = DocumentStreamService()
        val job = launch {
            service.streamDocuments("owner1").collect {
                throw CancellationException("early cancel")
            }
        }
        job.join()

        assertTrue(
            service.connectionClosed,
            "Resource should be released even on immediate cancellation"
        )
    }

    // =========================================================================
    // A4: Unstructured scope
    // =========================================================================

    @Test
    fun test_structured_scope_used() = runTest {
        
        // using the caller's scope. Coroutines launched in the new scope are not tied
        // to the parent and won't be cancelled with it.
        val service = BulkImportService()
        val result = service.getImportScopeInfo()
        assertFalse(
            result.usesOwnScope,
            "bulkImport should use caller's scope, not create its own CoroutineScope"
        )
    }

    @Test
    fun test_parent_cancellation_propagates() = runTest {
        
        val service = BulkImportService()
        var importsCancelled = false

        val parentJob = launch {
            service.bulkImport(listOf("doc1", "doc2", "doc3"))
        }

        delay(50)
        parentJob.cancelAndJoin()

        // After parent cancellation, all import coroutines should have been cancelled
        assertTrue(
            service.allImportsCancelled,
            "All import coroutines should be cancelled when parent scope is cancelled"
        )
    }

    // =========================================================================
    // B1: Platform type from JDBC ResultSet
    // =========================================================================

    @Test
    fun test_properties_null_handled() {
        
        // is NULL, this becomes null but is assigned to a non-null String parameter,
        // causing a NullPointerException at runtime.
        val loader = JdbcDocumentLoader()
        val result = loader.loadDocument(nullTitle = true)
        // Should handle null gracefully instead of NPE
        assertNotNull(result, "Loader should handle null JDBC values gracefully")
        assertTrue(
            result.title.isEmpty() || result.title == "untitled",
            "Null title from JDBC should be converted to a safe default, got: '${result.title}'"
        )
    }

    @Test
    fun test_platform_type_safe() {
        
        val loader = JdbcDocumentLoader()
        val result = loader.loadDocument(nullContent = true)
        assertNotNull(result, "Loader should not crash on null content from JDBC")
        assertTrue(
            result.content.isEmpty() || result.content == "empty",
            "Null content from JDBC should be handled safely, got: '${result.content}'"
        )
    }

    // =========================================================================
    // C1: ByteArray equality
    // =========================================================================

    @Test
    fun test_bytearray_content_equals() {
        
        // Two Documents with identical checksum bytes are not considered equal
        val checksum1 = byteArrayOf(0x01, 0x02, 0x03, 0x04)
        val checksum2 = byteArrayOf(0x01, 0x02, 0x03, 0x04)
        val doc1 = DocumentFixture(id = "d1", title = "Test", content = "Hello", checksum = checksum1)
        val doc2 = DocumentFixture(id = "d1", title = "Test", content = "Hello", checksum = checksum2)

        assertEquals(
            doc1,
            doc2,
            "Documents with identical checksum content should be equal"
        )
    }

    @Test
    fun test_document_version_equality() {
        
        val checksum1 = byteArrayOf(0xAA.toByte(), 0xBB.toByte())
        val checksum2 = byteArrayOf(0xAA.toByte(), 0xBB.toByte())
        val doc1 = DocumentFixture(id = "d2", title = "Doc", content = "Body", checksum = checksum1)
        val doc2 = DocumentFixture(id = "d2", title = "Doc", content = "Body", checksum = checksum2)

        val set = setOf(doc1, doc2)
        assertEquals(
            1,
            set.size,
            "Documents with same content checksum should deduplicate in a Set"
        )
    }

    // =========================================================================
    // C2: copy() shallow-copies list
    // =========================================================================

    @Test
    fun test_metadata_copy_deep() {
        
        // duplicate shares the same reference as the original.
        val original = DocumentFixture(
            id = "d1",
            title = "Original",
            content = "Body",
            tags = mutableListOf("kotlin", "testing")
        )
        val duplicate = original.duplicate("Copy")
        duplicate.tags.add("new-tag")

        assertNotEquals(
            original.tags.size,
            duplicate.tags.size,
            "Duplicate's tag list should be independent of original"
        )
    }

    @Test
    fun test_original_tags_unchanged() {
        
        val original = DocumentFixture(
            id = "d1",
            title = "Original",
            content = "Body",
            tags = mutableListOf("initial")
        )
        val duplicate = original.duplicate("Dup")
        duplicate.tags.add("extra1")
        duplicate.tags.add("extra2")

        assertEquals(
            1,
            original.tags.size,
            "Original tags should remain unmodified after duplicate is changed"
        )
        assertEquals("initial", original.tags[0])
    }

    // =========================================================================
    // E1: suspendedTransaction cancellation
    // =========================================================================

    @Test
    fun test_suspended_transaction_used() = runTest {
        
        // cancellation. If the coroutine is cancelled mid-transaction, the transaction
        // may still commit partial work.
        val txService = SuspendedTransactionService()
        var transactionRolledBack = false

        val job = launch {
            txService.saveWithCancellationCheck { rolledBack ->
                transactionRolledBack = rolledBack
            }
        }

        delay(50)
        job.cancelAndJoin()

        assertTrue(
            transactionRolledBack,
            "Transaction should be rolled back when coroutine is cancelled"
        )
    }

    @Test
    fun test_no_thread_blocking_in_db() = runTest {
        
        val txService = SuspendedTransactionService()
        val result = txService.simulatePartialInsert()
        assertFalse(
            result.partiallyCommitted,
            "Transaction must not partially commit on cancellation"
        )
    }

    // =========================================================================
    // E2: SchemaUtils.create not idempotent
    // =========================================================================

    @Test
    fun test_schema_create_in_transaction() {
        
        // Should use createMissingTablesAndColumns() instead.
        val schemaService = SchemaService()
        schemaService.initSchema() // first call creates
        val secondCallResult = schemaService.initSchema() // second call should NOT throw
        assertTrue(
            secondCallResult.success,
            "Schema initialization should be idempotent (safe to call twice)"
        )
    }

    @Test
    fun test_init_tables_wrapped() {
        
        val schemaService = SchemaService()
        assertTrue(
            schemaService.usesCreateMissingTablesAndColumns,
            "Should use SchemaUtils.createMissingTablesAndColumns, not SchemaUtils.create"
        )
    }

    // =========================================================================
    // F1: Instant serializer loses nanosecond precision
    // =========================================================================

    @Test
    fun test_instant_serializer_registered() {
        
        // For example, Instant with 123456000 nanos serializes as ".123456"
        // and may parse back differently depending on implementation.
        val original = Instant.ofEpochSecond(1700000000L, 123456789L)
        val serializer = InstantSerializerFixture()
        val serialized = serializer.serialize(original)
        val deserialized = serializer.deserialize(serialized)

        assertEquals(
            original.nano,
            deserialized.nano,
            "Nanosecond precision should be preserved. Original: ${original.nano}, Got: ${deserialized.nano}"
        )
    }

    @Test
    fun test_timestamp_roundtrip() {
        
        val instants = listOf(
            Instant.ofEpochSecond(1700000000L, 100000000L),  // .1 seconds
            Instant.ofEpochSecond(1700000000L, 120000000L),  // .12 seconds
            Instant.ofEpochSecond(1700000000L, 123000000L),  // .123 seconds
            Instant.ofEpochSecond(1700000000L, 123456789L),  // full nano
            Instant.ofEpochSecond(1700000000L, 0L),          // exact second
        )
        val serializer = InstantSerializerFixture()

        for (original in instants) {
            val roundTripped = serializer.deserialize(serializer.serialize(original))
            assertEquals(
                original,
                roundTripped,
                "Round-trip should preserve instant exactly. Original: $original, Got: $roundTripped"
            )
        }
    }

    // =========================================================================
    // I6: Unsafe deserialization
    // =========================================================================

    @Test
    fun test_safe_deserialization() {
        
        // allowing remote code execution via crafted payloads.
        val service = DeserializationService()
        val maliciousPayload = createMaliciousPayload()
        val result = service.restoreFromBackup(maliciousPayload)
        assertTrue(
            result.validated,
            "Deserialization should validate/whitelist classes before deserializing"
        )
    }

    @Test
    fun test_no_object_input_stream() {
        
        val service = DeserializationService()
        assertFalse(
            service.usesObjectInputStream,
            "Should NOT use ObjectInputStream for untrusted data. Use safe serialization (JSON, protobuf)."
        )
    }

    // =========================================================================
    // Baseline: Document CRUD and versioning
    // =========================================================================

    @Test
    fun test_create_document() {
        val repo = DocumentRepository()
        val doc = repo.create("d1", "My Doc", "Hello World")
        assertEquals("d1", doc.id)
        assertEquals("My Doc", doc.title)
        assertEquals("Hello World", doc.content)
    }

    @Test
    fun test_read_document() {
        val repo = DocumentRepository()
        repo.create("d1", "My Doc", "Content")
        val found = repo.findById("d1")
        assertNotNull(found)
        assertEquals("d1", found.id)
    }

    @Test
    fun test_update_document_title() {
        val repo = DocumentRepository()
        repo.create("d1", "Original", "Content")
        val updated = repo.updateTitle("d1", "Updated Title")
        assertNotNull(updated)
        assertEquals("Updated Title", updated.title)
    }

    @Test
    fun test_delete_document() {
        val repo = DocumentRepository()
        repo.create("d1", "To Delete", "Content")
        val deleted = repo.delete("d1")
        assertTrue(deleted, "Document should be deleted")
        assertNull(repo.findById("d1"), "Deleted document should not be found")
    }

    @Test
    fun test_list_documents_by_owner() {
        val repo = DocumentRepository()
        repo.create("d1", "Doc 1", "Content 1", owner = "alice")
        repo.create("d2", "Doc 2", "Content 2", owner = "alice")
        repo.create("d3", "Doc 3", "Content 3", owner = "bob")
        val aliceDocs = repo.listByOwner("alice")
        assertEquals(2, aliceDocs.size, "Alice should have 2 documents")
    }

    @Test
    fun test_document_versioning_increments() {
        val repo = DocumentRepository()
        repo.create("d1", "Doc", "v1")
        repo.updateContent("d1", "v2")
        repo.updateContent("d1", "v3")
        val doc = repo.findById("d1")
        assertNotNull(doc)
        assertEquals(3, doc.version, "Document should be at version 3 after 2 updates")
    }

    @Test
    fun test_document_version_history() {
        val repo = DocumentRepository()
        repo.create("d1", "Doc", "initial content")
        repo.updateContent("d1", "updated content")
        val history = repo.getVersionHistory("d1")
        assertEquals(2, history.size, "Should have 2 versions in history")
        assertEquals("initial content", history[0].content)
        assertEquals("updated content", history[1].content)
    }

    @Test
    fun test_document_created_at_set() {
        val repo = DocumentRepository()
        val before = System.currentTimeMillis()
        val doc = repo.create("d1", "Doc", "Content")
        val after = System.currentTimeMillis()
        assertTrue(doc.createdAt in before..after, "createdAt should be set at creation time")
    }

    @Test
    fun test_document_tags() {
        val repo = DocumentRepository()
        val doc = repo.create("d1", "Doc", "Content", tags = listOf("kotlin", "test"))
        assertEquals(listOf("kotlin", "test"), doc.tags)
    }

    @Test
    fun test_find_nonexistent_document() {
        val repo = DocumentRepository()
        val result = repo.findById("nonexistent")
        assertNull(result, "Finding a nonexistent document should return null")
    }

    @Test
    fun test_empty_repository() {
        val repo = DocumentRepository()
        val all = repo.listByOwner("anyone")
        assertTrue(all.isEmpty(), "New repository should have no documents")
    }

    @Test
    fun test_document_content_update_preserves_title() {
        val repo = DocumentRepository()
        repo.create("d1", "My Title", "old content")
        repo.updateContent("d1", "new content")
        val doc = repo.findById("d1")
        assertNotNull(doc)
        assertEquals("My Title", doc.title, "Title should be preserved after content update")
        assertEquals("new content", doc.content)
    }

    @Test
    fun test_multiple_owners_isolated() {
        val repo = DocumentRepository()
        repo.create("d1", "Alice Doc", "Content", owner = "alice")
        repo.create("d2", "Bob Doc", "Content", owner = "bob")
        val aliceDocs = repo.listByOwner("alice")
        val bobDocs = repo.listByOwner("bob")
        assertEquals(1, aliceDocs.size)
        assertEquals(1, bobDocs.size)
        assertEquals("Alice Doc", aliceDocs[0].title)
        assertEquals("Bob Doc", bobDocs[0].title)
    }

    @Test
    fun test_delete_nonexistent_document() {
        val repo = DocumentRepository()
        val deleted = repo.delete("nonexistent")
        assertFalse(deleted, "Deleting a nonexistent document should return false")
    }

    @Test
    fun test_version_starts_at_one() {
        val repo = DocumentRepository()
        val doc = repo.create("d1", "Doc", "Content")
        assertEquals(1, doc.version, "New document should start at version 1")
    }

    @Test
    fun test_update_nonexistent_returns_null() {
        val repo = DocumentRepository()
        val result = repo.updateTitle("missing", "New Title")
        assertNull(result, "Updating a nonexistent document should return null")
    }

    @Test
    fun test_document_tags_immutable_default() {
        val repo = DocumentRepository()
        val doc = repo.create("d1", "Doc", "Content")
        assertTrue(doc.tags.isEmpty(), "Default tags should be empty")
    }

    @Test
    fun test_version_history_empty_for_unknown() {
        val repo = DocumentRepository()
        val history = repo.getVersionHistory("unknown")
        assertTrue(history.isEmpty(), "Version history for unknown doc should be empty")
    }

    @Test
    fun test_create_multiple_documents_unique_ids() {
        val repo = DocumentRepository()
        repo.create("d1", "Doc A", "Content A")
        repo.create("d2", "Doc B", "Content B")
        repo.create("d3", "Doc C", "Content C")
        val d1 = repo.findById("d1")
        val d2 = repo.findById("d2")
        val d3 = repo.findById("d3")
        assertNotNull(d1)
        assertNotNull(d2)
        assertNotNull(d3)
        assertEquals("Doc A", d1.title)
        assertEquals("Doc B", d2.title)
        assertEquals("Doc C", d3.title)
    }

    @Test
    fun test_update_content_increments_version() {
        val repo = DocumentRepository()
        repo.create("d1", "Doc", "v1")
        val updated = repo.updateContent("d1", "v2")
        assertNotNull(updated)
        assertEquals(2, updated.version, "Version should be 2 after one content update")
        assertEquals("v2", updated.content)
    }

    @Test
    fun test_update_title_increments_version() {
        val repo = DocumentRepository()
        repo.create("d1", "Original Title", "Content")
        val updated = repo.updateTitle("d1", "New Title")
        assertNotNull(updated)
        assertEquals(2, updated.version, "Version should be 2 after one title update")
    }

    @Test
    fun test_version_history_ordered_chronologically() {
        val repo = DocumentRepository()
        repo.create("d1", "Doc", "content-v1")
        repo.updateContent("d1", "content-v2")
        repo.updateContent("d1", "content-v3")
        val history = repo.getVersionHistory("d1")
        assertEquals(3, history.size)
        assertEquals(1, history[0].version)
        assertEquals(2, history[1].version)
        assertEquals(3, history[2].version)
    }

    @Test
    fun test_delete_then_create_same_id() {
        val repo = DocumentRepository()
        repo.create("d1", "First", "Content 1")
        repo.delete("d1")
        repo.create("d1", "Second", "Content 2")
        val doc = repo.findById("d1")
        assertNotNull(doc)
        assertEquals("Second", doc.title, "Re-created document should have the new title")
    }

    @Test
    fun test_list_by_owner_returns_empty_for_unknown_owner() {
        val repo = DocumentRepository()
        repo.create("d1", "Doc", "Content", owner = "alice")
        val docs = repo.listByOwner("bob")
        assertTrue(docs.isEmpty(), "Owner with no documents should get empty list")
    }

    @Test
    fun test_document_preserves_owner() {
        val repo = DocumentRepository()
        repo.create("d1", "Doc", "Content", owner = "charlie")
        val doc = repo.findById("d1")
        assertNotNull(doc)
        assertEquals("charlie", doc.owner, "Document owner should be preserved")
    }

    @Test
    fun test_update_content_nonexistent_returns_null() {
        val repo = DocumentRepository()
        val result = repo.updateContent("missing", "data")
        assertNull(result, "Updating content of nonexistent document should return null")
    }

    @Test
    fun test_document_tags_preserved_after_update() {
        val repo = DocumentRepository()
        repo.create("d1", "Doc", "Content", tags = listOf("alpha", "beta"))
        repo.updateTitle("d1", "New Title")
        val doc = repo.findById("d1")
        assertNotNull(doc)
        assertEquals(listOf("alpha", "beta"), doc.tags, "Tags should be preserved after title update")
    }

    @Test
    fun test_multiple_updates_accumulate_history() {
        val repo = DocumentRepository()
        repo.create("d1", "Doc", "v1")
        repo.updateContent("d1", "v2")
        repo.updateContent("d1", "v3")
        repo.updateTitle("d1", "New Title")
        val history = repo.getVersionHistory("d1")
        assertEquals(4, history.size, "Should have 4 versions in history: 1 create + 3 updates")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    // A3: Flow with resource leak on cancellation
    class DocumentStreamService {
        var connectionClosed = false

        fun streamDocuments(ownerId: String): Flow<String> = flow {
            
            val connection = openConnection()
            try {
                val docs = listOf("doc1", "doc2", "doc3", "doc4")
                for (doc in docs) {
                    emit(doc)
                    delay(10)
                }
            } finally {
                
                try {
                    connection.close()
                } catch (e: Exception) {
                    
                }
            }
        }

        private fun openConnection(): FakeConnection = FakeConnection(this)

        class FakeConnection(private val parent: DocumentStreamService) {
            fun close() {
                
                throw RuntimeException("Connection close failed")
                // Should be: parent.connectionClosed = true
            }
        }
    }

    // A4: Unstructured scope
    class BulkImportService {
        var allImportsCancelled = false

        fun getImportScopeInfo(): ScopeInfo {
            
            return ScopeInfo(usesOwnScope = true) 
        }

        suspend fun bulkImport(documents: List<String>) {
            
            val scope = CoroutineScope(Dispatchers.IO)
            documents.forEach { doc ->
                scope.launch {
                    delay(1000) // simulate save
                }
            }
            
        }
    }

    data class ScopeInfo(val usesOwnScope: Boolean)

    // B1: Platform type from JDBC
    class JdbcDocumentLoader {
        fun loadDocument(nullTitle: Boolean = false, nullContent: Boolean = false): DocumentResult {
            
            val title: String = if (nullTitle) {
                // Simulating: rs.getString("title") returns null for NULL column
                @Suppress("CAST_NEVER_SUCCEEDS")
                (null as String?) as String 
            } else {
                "Valid Title"
            }
            val content: String = if (nullContent) {
                @Suppress("CAST_NEVER_SUCCEEDS")
                (null as String?) as String 
            } else {
                "Valid Content"
            }
            return DocumentResult(id = "d1", title = title, content = content)
        }
    }

    data class DocumentResult(val id: String, val title: String, val content: String)

    // C1 & C2: Document with ByteArray and shallow copy
    data class DocumentFixture(
        val id: String,
        val title: String,
        val content: String,
        val checksum: ByteArray = byteArrayOf(), 
        val tags: MutableList<String> = mutableListOf()
    ) {
        
        fun duplicate(newTitle: String): DocumentFixture = this.copy(title = newTitle) 

        
        // data class generated equals() uses ByteArray.equals() which is reference equality
    }

    // E1: Suspended transaction cancellation
    class SuspendedTransactionService {
        suspend fun saveWithCancellationCheck(onResult: (Boolean) -> Unit) {
            
            try {
                delay(200) // simulates transaction work
                onResult(false) // transaction committed despite cancellation
            } catch (e: CancellationException) {
                onResult(false) 
                throw e
            }
        }

        fun simulatePartialInsert(): PartialCommitResult {
            
            return PartialCommitResult(partiallyCommitted = true) 
        }
    }

    data class PartialCommitResult(val partiallyCommitted: Boolean)

    // E2: SchemaUtils.create not idempotent
    class SchemaService {
        private var tableCreated = false
        var usesCreateMissingTablesAndColumns = false 

        fun initSchema(): SchemaResult {
            if (tableCreated) {
                
                return SchemaResult(success = false, error = "Table already exists")
            }
            tableCreated = true
            return SchemaResult(success = true)
        }
    }

    data class SchemaResult(val success: Boolean, val error: String? = null)

    // F1: Instant serializer loses precision
    class InstantSerializerFixture {
        fun serialize(instant: Instant): String {
            
            return instant.toString() 
        }

        fun deserialize(text: String): Instant {
            return Instant.parse(text)
        }
    }

    // I6: Unsafe deserialization
    class DeserializationService {
        var usesObjectInputStream = true 

        fun restoreFromBackup(data: ByteArray): DeserializationResult {
            
            return try {
                val ois = ObjectInputStream(ByteArrayInputStream(data))
                ois.readObject()
                DeserializationResult(validated = false) 
            } catch (e: Exception) {
                DeserializationResult(validated = false) 
            }
        }
    }

    data class DeserializationResult(val validated: Boolean)

    private fun createMaliciousPayload(): ByteArray {
        val baos = ByteArrayOutputStream()
        try {
            val oos = ObjectOutputStream(baos)
            oos.writeObject("harmless-string") // simple payload for testing
            oos.close()
        } catch (e: Exception) {
            // fallback: return minimal valid serialized stream header
            return byteArrayOf(0xAC.toByte(), 0xED.toByte(), 0x00, 0x05)
        }
        return baos.toByteArray()
    }

    // Baseline: Document repository
    data class VersionedDocument(
        val id: String,
        val title: String,
        val content: String,
        val version: Int,
        val createdAt: Long,
        val tags: List<String> = emptyList(),
        val owner: String = "system"
    )

    class DocumentRepository {
        private val documents = mutableMapOf<String, VersionedDocument>()
        private val history = mutableMapOf<String, MutableList<VersionedDocument>>()

        fun create(
            id: String,
            title: String,
            content: String,
            owner: String = "system",
            tags: List<String> = emptyList()
        ): VersionedDocument {
            val doc = VersionedDocument(
                id = id, title = title, content = content,
                version = 1, createdAt = System.currentTimeMillis(),
                tags = tags, owner = owner
            )
            documents[id] = doc
            history.getOrPut(id) { mutableListOf() }.add(doc)
            return doc
        }

        fun findById(id: String): VersionedDocument? = documents[id]

        fun updateTitle(id: String, newTitle: String): VersionedDocument? {
            val existing = documents[id] ?: return null
            val updated = existing.copy(title = newTitle, version = existing.version + 1)
            documents[id] = updated
            history.getOrPut(id) { mutableListOf() }.add(updated)
            return updated
        }

        fun updateContent(id: String, newContent: String): VersionedDocument? {
            val existing = documents[id] ?: return null
            val updated = existing.copy(content = newContent, version = existing.version + 1)
            documents[id] = updated
            history.getOrPut(id) { mutableListOf() }.add(updated)
            return updated
        }

        fun delete(id: String): Boolean {
            return documents.remove(id) != null
        }

        fun listByOwner(owner: String): List<VersionedDocument> {
            return documents.values.filter { it.owner == owner }
        }

        fun getVersionHistory(id: String): List<VersionedDocument> {
            return history[id]?.toList() ?: emptyList()
        }
    }
}
