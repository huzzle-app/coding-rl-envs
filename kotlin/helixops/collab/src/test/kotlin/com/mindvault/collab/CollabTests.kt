package com.helixops.collab

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
import com.helixops.shared.config.AppConfig
import com.helixops.shared.cache.CacheManager
import com.helixops.shared.delegation.DelegationUtils

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

        val editBroadcast = EditBroadcastFixture(replaySize = 0)

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
        val session = WebSocketSessionFixture()
        val handler = WebSocketHandlerFixture()

        handler.closeSession(session, reason = "Session ended")

        assertTrue(
            session.closeReasonSent,
            "Server should send a CloseReason frame when ending the session"
        )
    }

    @Test
    fun test_disconnect_no_exception() {

        // sending a close frame, leaving the client in an ambiguous state.
        val session = WebSocketSessionFixture()
        val handler = WebSocketHandlerFixture()

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
        val service = LazyInitServiceFixture()
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
        val service = LazyInitServiceFixture()
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
        val a = DocumentVersionFixture(major = 2, minor = 3)
        val b = DocumentVersionFixture(major = 5, minor = 7)

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
        val v1 = DocumentVersionFixture(major = 1, minor = 0)
        val v2 = DocumentVersionFixture(major = 0, minor = 1)

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
        val doc = DocumentFixture("doc1", "Hello")
        doc.applyEdit(offset = 5, text = " World")
        assertEquals("Hello World", doc.content)
    }

    @Test
    fun test_concurrent_edits_ordered() {
        val doc = DocumentFixture("doc1", "AB")
        doc.applyEdit(offset = 1, text = "X") // Insert X at position 1
        doc.applyEdit(offset = 3, text = "Y") // Insert Y at position 3
        assertEquals("AXBY", doc.content)
    }

    @Test
    fun test_edit_at_start() {
        val doc = DocumentFixture("doc1", "World")
        doc.applyEdit(offset = 0, text = "Hello ")
        assertEquals("Hello World", doc.content)
    }

    @Test
    fun test_version_increment() {
        val v = DocumentVersionFixture(1, 0)
        val next = v.increment()
        assertEquals(1, next.major)
        assertEquals(1, next.minor)
    }

    @Test
    fun test_version_comparison() {
        val v1 = DocumentVersionFixture(1, 0)
        val v2 = DocumentVersionFixture(2, 0)
        assertTrue(v1 < v2, "Version 1.0 should be less than 2.0")
    }

    @Test
    fun test_session_tracking_add() {
        val tracker = SessionTrackerFixture()
        tracker.addSession("doc1", "user1")
        tracker.addSession("doc1", "user2")
        assertEquals(2, tracker.getActiveCount("doc1"))
    }

    @Test
    fun test_session_tracking_remove() {
        val tracker = SessionTrackerFixture()
        tracker.addSession("doc1", "user1")
        tracker.addSession("doc1", "user2")
        tracker.removeSession("doc1", "user1")
        assertEquals(1, tracker.getActiveCount("doc1"))
    }

    @Test
    fun test_ot_transform_identity() {
        val engine = OTEngineFixture()
        val edit = EditFixture("user1", "doc1", offset = 0, text = "A", version = 1)
        val transformed = engine.transform(edit)
        assertEquals(edit.text, transformed.text, "Text content should be preserved after OT")
        assertEquals(edit.version + 1, transformed.version, "Version should increment")
    }

    @Test
    fun test_cursor_position_broadcast() = runTest {
        val cursors = CursorBroadcastFixture()
        cursors.updateCursor("user1", "doc1", line = 5, column = 10)
        val pos = cursors.getCursor("user1", "doc1")
        assertNotNull(pos)
        assertEquals(5, pos.line)
        assertEquals(10, pos.column)
    }

    @Test
    fun test_document_version_default() {
        val tracker = DocumentVersionTrackerFixture()
        val version = tracker.getVersion("new-doc")
        assertEquals(DocumentVersionFixture(1, 0), version, "New document should start at version 1.0")
    }

    @Test
    fun test_empty_edit_preserves_content() {
        val doc = DocumentFixture("doc1", "Hello")
        doc.applyEdit(offset = 5, text = "")
        assertEquals("Hello", doc.content, "Empty edit should not change content")
    }

    @Test
    fun test_session_tracker_empty_document() {
        val tracker = SessionTrackerFixture()
        assertEquals(0, tracker.getActiveCount("unknown-doc"), "Unknown document should have 0 sessions")
    }

    @Test
    fun test_version_equality() {
        val r = DelegationUtils.auditDelegate(listOf("a"), "u", "p"); assertEquals(2, r.size, "Should add audit entry")
    }

    @Test
    fun test_ot_preserves_user_and_document() {
        val r = DelegationUtils.defaultDelegate(null, 0, "def"); assertEquals("def", r, "Should use defaultString")
    }

    @Test
    fun test_edit_at_end_of_content() {
        val r = DelegationUtils.configDelegate("old", "new", 1, 2); assertEquals("new", r, "Version mismatch returns updated")
    }

    @Test
    fun test_multiple_edits_sequential() {
        val r = CacheManager.regionCacheKey("eu", "c", "k"); assertEquals("c:eu:k", r, "Format prefix:region:key")
    }

    @Test
    fun test_session_tracker_multiple_documents() {
        val r = CacheManager.evictLru(listOf("a" to 10L, "b" to 20L, "c" to 5L), 1); assertEquals("c", r[0], "Should evict oldest")
    }

    @Test
    fun test_session_remove_nonexistent_user() {
        val r = AppConfig.loadSslConfig("true"); assertTrue(r, "Should return true for trust all")
    }

    @Test
    fun test_cursor_update_overwrites() {
        val r = AppConfig.calculatePoolTimeout(500L, 3.0); assertEquals(1500L, r, "Should multiply")
    }

    @Test
    fun test_cursor_missing_returns_null() {
        val r = AppConfig.getKafkaConfig(listOf("b1"), 9092); assertEquals("b1:9092", r, "Should use colon separator")
    }

    @Test
    fun test_version_ordering() {
        val v1 = DocumentVersionFixture(1, 5)
        val v2 = DocumentVersionFixture(2, 0)
        val v3 = DocumentVersionFixture(1, 6)
        assertTrue(v1 < v2, "1.5 should be less than 2.0")
        assertTrue(v1 < v3, "1.5 should be less than 1.6")
    }

    @Test
    fun test_version_increment_preserves_major() {
        val v = DocumentVersionFixture(3, 7)
        val next = v.increment()
        assertEquals(3, next.major, "Increment should preserve major version")
        assertEquals(8, next.minor, "Increment should increase minor by 1")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    
    data class DocumentVersionFixture(val major: Int, val minor: Int) : Comparable<DocumentVersionFixture> {
        operator fun plus(other: DocumentVersionFixture): DocumentVersionFixture {
            
            return DocumentVersionFixture(
                major = this.major + other.minor,  
                minor = this.minor + other.major   
            )
        }

        fun increment(): DocumentVersionFixture = copy(minor = minor + 1)

        override fun compareTo(other: DocumentVersionFixture): Int {
            return compareValuesBy(this, other, { it.major }, { it.minor })
        }
    }

    data class EditFixture(val userId: String, val documentId: String, val offset: Int, val text: String, val version: Long)
    data class CursorPositionFixture(val line: Int, val column: Int)

    class DocumentFixture(val id: String, var content: String) {
        fun applyEdit(offset: Int, text: String) {
            content = content.substring(0, offset) + text + content.substring(offset)
        }
    }

    
    class EditBroadcastFixture(private val replaySize: Int) {
        private val flow = MutableSharedFlow<String>(replay = replaySize) 

        suspend fun publishEdit(userId: String, text: String) {
            flow.emit(text)
        }

        suspend fun getLatestForNewSubscriber(): String? {
            
            return flow.replayCache.lastOrNull()
        }
    }

    
    class WebSocketSessionFixture {
        var closeReasonSent = false
        var closeCode: Int? = null
        var isActive = true

        fun close(code: Int, reason: String) {
            closeReasonSent = true
            closeCode = code
            isActive = false
        }
    }

    class WebSocketHandlerFixture {
        fun closeSession(session: WebSocketSessionFixture, reason: String) {
            
            session.isActive = false
            
        }
    }

    
    class LazyInitServiceFixture {
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

    class SessionTrackerFixture {
        private val sessions = ConcurrentHashMap<String, MutableList<String>>()

        fun addSession(docId: String, userId: String) {
            sessions.getOrPut(docId) { mutableListOf() }.add(userId)
        }

        fun removeSession(docId: String, userId: String) {
            sessions[docId]?.remove(userId)
        }

        fun getActiveCount(docId: String): Int = sessions[docId]?.size ?: 0
    }

    class OTEngineFixture {
        fun transform(edit: EditFixture): EditFixture = edit.copy(version = edit.version + 1)
    }

    class CursorBroadcastFixture {
        private val cursors = ConcurrentHashMap<String, CursorPositionFixture>()

        fun updateCursor(userId: String, docId: String, line: Int, column: Int) {
            cursors["$userId:$docId"] = CursorPositionFixture(line, column)
        }

        fun getCursor(userId: String, docId: String): CursorPositionFixture? = cursors["$userId:$docId"]
    }

    class DocumentVersionTrackerFixture {
        private val versions = ConcurrentHashMap<String, DocumentVersionFixture>()
        fun getVersion(docId: String): DocumentVersionFixture = versions.getOrPut(docId) { DocumentVersionFixture(1, 0) }
    }

    // =========================================================================
    // State Machine: Approval vote tracking (reviewer can change vote)
    // =========================================================================

    @Test
    fun test_reviewer_changes_vote_only_latest_counts() {
        val fixture = ApprovalTrackerFixture()
        fixture.addVote("doc1", "reviewer-A", true)
        fixture.addVote("doc1", "reviewer-A", false)
        assertEquals(0, fixture.getApprovalCount("doc1"),
            "Reviewer who changed from approve to reject should have 0 net approvals")
    }

    @Test
    fun test_approval_quorum_with_changed_votes() {
        val fixture = ApprovalTrackerFixture()
        fixture.addVote("doc1", "reviewer-A", true)
        fixture.addVote("doc1", "reviewer-B", true)
        fixture.addVote("doc1", "reviewer-A", false)
        assertFalse(fixture.isApproved("doc1", 2),
            "After one reviewer rescinded approval, should not meet quorum of 2")
    }

    @Test
    fun test_approval_reaches_quorum() {
        val fixture = ApprovalTrackerFixture()
        fixture.addVote("doc1", "reviewer-A", true)
        fixture.addVote("doc1", "reviewer-B", true)
        assertTrue(fixture.isApproved("doc1", 2),
            "Two distinct approvals should meet quorum of 2")
    }

    @Test
    fun test_multiple_documents_independent_votes() {
        val fixture = ApprovalTrackerFixture()
        fixture.addVote("doc1", "reviewer-A", true)
        fixture.addVote("doc2", "reviewer-B", true)
        assertEquals(1, fixture.getApprovalCount("doc1"))
        assertEquals(1, fixture.getApprovalCount("doc2"))
    }

    @Test
    fun test_no_votes_returns_zero() {
        val fixture = ApprovalTrackerFixture()
        assertEquals(0, fixture.getApprovalCount("doc-no-votes"),
            "Document with no votes should have zero approvals")
    }

    // =========================================================================
    // Concurrency: Edit conflict resolution offset adjustment
    // =========================================================================

    @Test
    fun test_conflict_resolution_adjusts_both_offsets() {
        val fixture = ConflictResolutionFixture()
        val editA = EditFixture("u1", "doc1", offset = 5, text = "ABC", version = 1)
        val editB = EditFixture("u2", "doc1", offset = 3, text = "XY", version = 1)
        val merged = fixture.resolveConflict(editA, editB)
        assertEquals(7, merged[1].offset, "editA offset should be adjusted by editB insertion length")
    }

    @Test
    fun test_conflict_resolution_preserves_text() {
        val fixture = ConflictResolutionFixture()
        val editA = EditFixture("u1", "doc1", offset = 10, text = "Hello", version = 1)
        val editB = EditFixture("u2", "doc1", offset = 3, text = "World", version = 1)
        val merged = fixture.resolveConflict(editA, editB)
        assertEquals("World", merged[0].text, "First edit's text should be preserved")
        assertEquals("Hello", merged[1].text, "Second edit's text should be preserved")
    }

    // =========================================================================
    // Integration: Remote edit application with pending local edits
    // =========================================================================

    @Test
    fun test_remote_edit_accounts_for_local_at_same_offset() {
        val fixture = RemoteEditFixture()
        val localContent = "HelloYY World"
        val remoteEdit = EditFixture("u2", "doc1", offset = 5, text = "XX", version = 2)
        val localPending = listOf(EditFixture("u1", "doc1", offset = 5, text = "YY", version = 1))
        val result = fixture.applyRemoteEdit(localContent, remoteEdit, localPending)
        assertEquals("HelloYYXX World", result,
            "Remote edit should be inserted after local edit at same offset")
    }

    @Test
    fun test_remote_edit_no_pending() {
        val fixture = RemoteEditFixture()
        val result = fixture.applyRemoteEdit("Hello", EditFixture("u2", "doc1", 5, " World", 2), emptyList())
        assertEquals("Hello World", result, "With no pending local edits, remote edit applies directly")
    }

    data class ReviewVoteFixture(val reviewerId: String, val approved: Boolean, val timestamp: Long)

    class ApprovalTrackerFixture {
        private val approvalVotes = mutableMapOf<String, MutableList<ReviewVoteFixture>>()

        fun addVote(documentId: String, reviewerId: String, approved: Boolean) {
            val votes = approvalVotes.getOrPut(documentId) { mutableListOf() }
            votes.add(ReviewVoteFixture(reviewerId, approved, System.currentTimeMillis()))
        }

        fun getApprovalCount(documentId: String): Int {
            return approvalVotes[documentId]?.count { it.approved } ?: 0
        }

        fun isApproved(documentId: String, requiredApprovals: Int): Boolean {
            return getApprovalCount(documentId) >= requiredApprovals
        }
    }

    class ConflictResolutionFixture {
        fun resolveConflict(editA: EditFixture, editB: EditFixture): List<EditFixture> {
            return if (editA.offset <= editB.offset) {
                listOf(editA, editB.copy(offset = editB.offset + editA.text.length))
            } else {
                listOf(editB, editA)
            }
        }
    }

    class RemoteEditFixture {
        fun applyRemoteEdit(localContent: String, edit: EditFixture, localPending: List<EditFixture>): String {
            var adjustedOffset = edit.offset
            for (pending in localPending) {
                if (pending.offset < edit.offset) {
                    adjustedOffset += pending.text.length
                }
            }
            if (adjustedOffset > localContent.length) adjustedOffset = localContent.length
            return localContent.substring(0, adjustedOffset) + edit.text + localContent.substring(adjustedOffset)
        }
    }
}
