package com.mindvault.collab

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNotEquals

/**
 * Tests for CollabService: collaborative editing, OT, WebSocket lifecycle.
 *
 * Bug-specific tests:
 *   A8 - SharedFlow replay = 0: new subscribers miss the latest state
 *   D4 - WebSocket close reason not propagated: missing close frame
 *   G2 - by lazy with NONE threading: not thread-safe under concurrent access
 *   K4 - operator commutativity: plus operator is asymmetric (a+b != b+a)
 */
class CollabTests {

    // =========================================================================
    // A8: SharedFlow replay = 0 -- new subscribers miss latest state
    // =========================================================================

    @Test
    fun test_shared_flow_replay() = runTest {
        
        // never see the most recent emission.
        val flow = MutableSharedFlow<String>(replay = 0) 

        flow.emit("latest-edit")

        // New subscriber joins AFTER the emission
        val collected = mutableListOf<String>()
        val job = launch {
            flow.take(1).toList(collected)
        }

        delay(50)
        
        assertTrue(
            collected.isNotEmpty(),
            "New subscriber should receive the latest edit via replay buffer"
        )
        job.cancel()
    }

    @Test
    fun test_late_subscriber_receives() = runTest {
        
        val editBroadcast = EditBroadcastStub(replaySize = 0) 

        editBroadcast.publishEdit("user1", "Hello")
        editBroadcast.publishEdit("user1", "Hello World")

        // Late subscriber
        val latestEdit = editBroadcast.getLatestForNewSubscriber()
        assertNotNull(
            latestEdit,
            "Late subscriber should receive the most recent edit"
        )
        assertEquals(
            "Hello World",
            latestEdit,
            "Late subscriber should see the latest edit, not an earlier one"
        )
    }

    // =========================================================================
    // D4: WebSocket close reason not propagated
    // =========================================================================

    @Test
    fun test_websocket_close_handled() {
        
        // CloseReason with an appropriate code and message.
        val session = WebSocketSessionStub()
        val handler = WebSocketHandlerStub()

        handler.closeSession(session, reason = "Session ended")

        assertTrue(
            session.closeReasonSent,
            "Server should send a CloseReason frame when ending the session"
        )
    }

    @Test
    fun test_disconnect_no_exception() {
        
        // sending a close frame, leaving the client in an ambiguous state.
        val session = WebSocketSessionStub()
        val handler = WebSocketHandlerStub()

        handler.closeSession(session, reason = "Normal closure")

        assertNotNull(
            session.closeCode,
            "Close frame should include a status code"
        )
        assertEquals(
            1000,
            session.closeCode,
            "Normal closure should use code 1000"
        )
    }

    // =========================================================================
    // G2: by lazy with LazyThreadSafetyMode.NONE -- not thread-safe
    // =========================================================================

    @Test
    fun test_lazy_no_coroutine_block() {
        
        // not safe when multiple coroutines access it concurrently.
        val service = LazyInitServiceStub()
        val mode = service.getLazyThreadSafetyMode()

        assertNotEquals(
            "NONE",
            mode,
            "Lazy initialization should NOT use LazyThreadSafetyMode.NONE for concurrent access"
        )
    }

    @Test
    fun test_lazy_thread_safe_mode() = runTest {
        
        // may both run the initializer, producing inconsistent state.
        val service = LazyInitServiceStub()
        val initCount = AtomicInteger(0)

        // Simulate concurrent first-access
        coroutineScope {
            repeat(10) {
                launch(Dispatchers.Default) {
                    service.accessLazyProperty { initCount.incrementAndGet() }
                }
            }
        }

        assertEquals(
            1,
            initCount.get(),
            "Lazy initializer should run exactly once even under concurrent access"
        )
    }

    // =========================================================================
    // K4: operator commutativity -- a + b should equal b + a
    // =========================================================================

    @Test
    fun test_operator_commutative() {
        
        // and this.minor + other.major, so a+b != b+a.
        val a = DocumentVersionLocal(major = 2, minor = 3)
        val b = DocumentVersionLocal(major = 5, minor = 7)

        val ab = a + b
        val ba = b + a

        assertEquals(
            ab,
            ba,
            "Version merge should be commutative: a+b should equal b+a, " +
                "but got a+b=$ab, b+a=$ba"
        )
    }

    @Test
    fun test_merge_order_independent() {
        
        // the same result regardless of operand order.
        val v1 = DocumentVersionLocal(major = 1, minor = 0)
        val v2 = DocumentVersionLocal(major = 0, minor = 1)

        val merged1 = v1 + v2
        val merged2 = v2 + v1

        assertEquals(
            merged1.major,
            merged2.major,
            "Major component should be symmetric"
        )
        assertEquals(
            merged1.minor,
            merged2.minor,
            "Minor component should be symmetric"
        )
    }

    // =========================================================================
    // Baseline: collaborative editing
    // =========================================================================

    @Test
    fun test_edit_applies_to_document() {
        val doc = DocumentStub("doc1", "Hello")
        doc.applyEdit(offset = 5, text = " World")
        assertEquals("Hello World", doc.content)
    }

    @Test
    fun test_concurrent_edits_ordered() {
        val doc = DocumentStub("doc1", "AB")
        doc.applyEdit(offset = 1, text = "X") // Insert X at position 1
        doc.applyEdit(offset = 3, text = "Y") // Insert Y at position 3
        assertEquals("AXBY", doc.content)
    }

    @Test
    fun test_edit_at_start() {
        val doc = DocumentStub("doc1", "World")
        doc.applyEdit(offset = 0, text = "Hello ")
        assertEquals("Hello World", doc.content)
    }

    @Test
    fun test_version_increment() {
        val v = DocumentVersionLocal(1, 0)
        val next = v.increment()
        assertEquals(1, next.major)
        assertEquals(1, next.minor)
    }

    @Test
    fun test_version_comparison() {
        val v1 = DocumentVersionLocal(1, 0)
        val v2 = DocumentVersionLocal(2, 0)
        assertTrue(v1 < v2, "Version 1.0 should be less than 2.0")
    }

    @Test
    fun test_session_tracking_add() {
        val tracker = SessionTrackerStub()
        tracker.addSession("doc1", "user1")
        tracker.addSession("doc1", "user2")
        assertEquals(2, tracker.getActiveCount("doc1"))
    }

    @Test
    fun test_session_tracking_remove() {
        val tracker = SessionTrackerStub()
        tracker.addSession("doc1", "user1")
        tracker.addSession("doc1", "user2")
        tracker.removeSession("doc1", "user1")
        assertEquals(1, tracker.getActiveCount("doc1"))
    }

    @Test
    fun test_ot_transform_identity() {
        val engine = OTEngineStub()
        val edit = EditLocal("user1", "doc1", offset = 0, text = "A", version = 1)
        val transformed = engine.transform(edit)
        assertEquals(edit.text, transformed.text, "Text content should be preserved after OT")
        assertEquals(edit.version + 1, transformed.version, "Version should increment")
    }

    @Test
    fun test_cursor_position_broadcast() = runTest {
        val cursors = CursorBroadcastStub()
        cursors.updateCursor("user1", "doc1", line = 5, column = 10)
        val pos = cursors.getCursor("user1", "doc1")
        assertNotNull(pos)
        assertEquals(5, pos.line)
        assertEquals(10, pos.column)
    }

    @Test
    fun test_document_version_default() {
        val tracker = DocumentVersionTrackerStub()
        val version = tracker.getVersion("new-doc")
        assertEquals(DocumentVersionLocal(1, 0), version, "New document should start at version 1.0")
    }

    @Test
    fun test_empty_edit_preserves_content() {
        val doc = DocumentStub("doc1", "Hello")
        doc.applyEdit(offset = 5, text = "")
        assertEquals("Hello", doc.content, "Empty edit should not change content")
    }

    @Test
    fun test_session_tracker_empty_document() {
        val tracker = SessionTrackerStub()
        assertEquals(0, tracker.getActiveCount("unknown-doc"), "Unknown document should have 0 sessions")
    }

    @Test
    fun test_version_equality() {
        val v1 = DocumentVersionLocal(1, 2)
        val v2 = DocumentVersionLocal(1, 2)
        assertEquals(v1, v2, "Same major.minor versions should be equal")
    }

    @Test
    fun test_ot_preserves_user_and_document() {
        val engine = OTEngineStub()
        val edit = EditLocal("alice", "doc42", offset = 10, text = "inserted", version = 5)
        val transformed = engine.transform(edit)
        assertEquals("alice", transformed.userId)
        assertEquals("doc42", transformed.documentId)
        assertEquals(10, transformed.offset)
    }

    @Test
    fun test_edit_at_end_of_content() {
        val doc = DocumentStub("doc1", "Hello")
        doc.applyEdit(offset = 5, text = "!")
        assertEquals("Hello!", doc.content, "Appending at end should work correctly")
    }

    @Test
    fun test_multiple_edits_sequential() {
        val doc = DocumentStub("doc1", "")
        doc.applyEdit(offset = 0, text = "A")
        doc.applyEdit(offset = 1, text = "B")
        doc.applyEdit(offset = 2, text = "C")
        assertEquals("ABC", doc.content, "Sequential single-char edits should concatenate")
    }

    @Test
    fun test_session_tracker_multiple_documents() {
        val tracker = SessionTrackerStub()
        tracker.addSession("doc1", "user1")
        tracker.addSession("doc2", "user1")
        tracker.addSession("doc2", "user2")
        assertEquals(1, tracker.getActiveCount("doc1"))
        assertEquals(2, tracker.getActiveCount("doc2"))
    }

    @Test
    fun test_session_remove_nonexistent_user() {
        val tracker = SessionTrackerStub()
        tracker.addSession("doc1", "user1")
        tracker.removeSession("doc1", "nonexistent")
        assertEquals(1, tracker.getActiveCount("doc1"), "Removing nonexistent user should not affect count")
    }

    @Test
    fun test_cursor_update_overwrites() {
        val cursors = CursorBroadcastStub()
        cursors.updateCursor("user1", "doc1", line = 1, column = 1)
        cursors.updateCursor("user1", "doc1", line = 10, column = 20)
        val pos = cursors.getCursor("user1", "doc1")
        assertNotNull(pos)
        assertEquals(10, pos.line, "Cursor should reflect the latest update")
        assertEquals(20, pos.column)
    }

    @Test
    fun test_cursor_missing_returns_null() {
        val cursors = CursorBroadcastStub()
        val pos = cursors.getCursor("unknown-user", "unknown-doc")
        assertEquals(null, pos, "Missing cursor should return null")
    }

    @Test
    fun test_version_ordering() {
        val v1 = DocumentVersionLocal(1, 5)
        val v2 = DocumentVersionLocal(2, 0)
        val v3 = DocumentVersionLocal(1, 6)
        assertTrue(v1 < v2, "1.5 should be less than 2.0")
        assertTrue(v1 < v3, "1.5 should be less than 1.6")
    }

    @Test
    fun test_version_increment_preserves_major() {
        val v = DocumentVersionLocal(3, 7)
        val next = v.increment()
        assertEquals(3, next.major, "Increment should preserve major version")
        assertEquals(8, next.minor, "Increment should increase minor by 1")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    
    data class DocumentVersionLocal(val major: Int, val minor: Int) : Comparable<DocumentVersionLocal> {
        operator fun plus(other: DocumentVersionLocal): DocumentVersionLocal {
            
            return DocumentVersionLocal(
                major = this.major + other.minor,  
                minor = this.minor + other.major   
            )
        }

        fun increment(): DocumentVersionLocal = copy(minor = minor + 1)

        override fun compareTo(other: DocumentVersionLocal): Int {
            return compareValuesBy(this, other, { it.major }, { it.minor })
        }
    }

    data class EditLocal(val userId: String, val documentId: String, val offset: Int, val text: String, val version: Long)
    data class CursorPositionLocal(val line: Int, val column: Int)

    class DocumentStub(val id: String, var content: String) {
        fun applyEdit(offset: Int, text: String) {
            content = content.substring(0, offset) + text + content.substring(offset)
        }
    }

    
    class EditBroadcastStub(private val replaySize: Int) {
        private val flow = MutableSharedFlow<String>(replay = replaySize) 

        suspend fun publishEdit(userId: String, text: String) {
            flow.emit(text)
        }

        suspend fun getLatestForNewSubscriber(): String? {
            
            return flow.replayCache.lastOrNull()
        }
    }

    
    class WebSocketSessionStub {
        var closeReasonSent = false
        var closeCode: Int? = null
        var isActive = true

        fun close(code: Int, reason: String) {
            closeReasonSent = true
            closeCode = code
            isActive = false
        }
    }

    class WebSocketHandlerStub {
        fun closeSession(session: WebSocketSessionStub, reason: String) {
            
            session.isActive = false
            
        }
    }

    
    class LazyInitServiceStub {
        private var initialized = false
        
        private val engine by lazy(LazyThreadSafetyMode.NONE) {
            initialized = true
            "OT-Engine"
        }

        fun getLazyThreadSafetyMode(): String = "NONE" 

        fun accessLazyProperty(onInit: () -> Unit): String {
            if (!initialized) onInit()
            return engine
        }
    }

    class SessionTrackerStub {
        private val sessions = ConcurrentHashMap<String, MutableList<String>>()

        fun addSession(docId: String, userId: String) {
            sessions.getOrPut(docId) { mutableListOf() }.add(userId)
        }

        fun removeSession(docId: String, userId: String) {
            sessions[docId]?.remove(userId)
        }

        fun getActiveCount(docId: String): Int = sessions[docId]?.size ?: 0
    }

    class OTEngineStub {
        fun transform(edit: EditLocal): EditLocal = edit.copy(version = edit.version + 1)
    }

    class CursorBroadcastStub {
        private val cursors = ConcurrentHashMap<String, CursorPositionLocal>()

        fun updateCursor(userId: String, docId: String, line: Int, column: Int) {
            cursors["$userId:$docId"] = CursorPositionLocal(line, column)
        }

        fun getCursor(userId: String, docId: String): CursorPositionLocal? = cursors["$userId:$docId"]
    }

    class DocumentVersionTrackerStub {
        private val versions = ConcurrentHashMap<String, DocumentVersionLocal>()
        fun getVersion(docId: String): DocumentVersionLocal = versions.getOrPut(docId) { DocumentVersionLocal(1, 0) }
    }
}
