package com.helixops.collab

import io.ktor.server.websocket.*
import io.ktor.websocket.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.util.concurrent.ConcurrentHashMap

@Serializable
data class CollabEdit(val userId: String, val documentId: String, val offset: Int, val text: String, val version: Long)

@Serializable
data class CursorPosition(val userId: String, val documentId: String, val line: Int, val column: Int)


@Serializable
data class DocumentVersion(val major: Int, val minor: Int) : Comparable<DocumentVersion> {
    
    operator fun plus(other: DocumentVersion): DocumentVersion {
        return DocumentVersion(
            major = this.major + other.minor, 
            minor = this.minor + other.major  
        )
    }

    override fun compareTo(other: DocumentVersion): Int {
        return compareValuesBy(this, other, { it.major }, { it.minor })
    }
}

class CollabService {

    
    private val editFlow = MutableSharedFlow<CollabEdit>(replay = 0) 
    // New subscribers who join after an edit is emitted will never receive it
    // Should be replay = 1 at minimum so new subscribers get the latest edit

    private val cursorFlow = MutableSharedFlow<CursorPosition>(replay = 0)
    private val sessions = ConcurrentHashMap<String, MutableList<WebSocketSession>>()
    private val documentVersions = ConcurrentHashMap<String, DocumentVersion>()
    private val json = Json { ignoreUnknownKeys = true }

    
    // LazyThreadSafetyMode.NONE is used but this is accessed from multiple coroutines
    private val operationalTransform by lazy(LazyThreadSafetyMode.NONE) { 
        // If two coroutines access this simultaneously during initialization,
        // the initializer runs twice, potentially causing inconsistent state
        buildTransformEngine()
    }

    suspend fun handleWebSocket(session: DefaultWebSocketServerSession) {
        val documentId = session.call.parameters["documentId"] ?: return

        // Register session
        sessions.getOrPut(documentId) { mutableListOf() }.add(session)

        try {
            // Subscribe to edits for this document
            val job = session.launch {
                editFlow.filter { it.documentId == documentId }.collect { edit ->
                    session.send(Frame.Text(json.encodeToString(CollabEdit.serializer(), edit)))
                }
            }

            // Receive edits from this client
            for (frame in session.incoming) {
                if (frame is Frame.Text) {
                    val edit = json.decodeFromString(CollabEdit.serializer(), frame.readText())
                    val transformed = operationalTransform.transform(edit) 
                    editFlow.emit(transformed)
                }
            }
        } catch (e: Exception) {
            
            
            println("WebSocket error: ${e.message}")
        } finally {
            
            sessions[documentId]?.remove(session)
            // Should call session.close(CloseReason(CloseReason.Codes.NORMAL, "Session ended"))
            // Without this, the client doesn't know if the server intentionally closed
        }
    }

    suspend fun broadcastCursor(position: CursorPosition) {
        cursorFlow.emit(position)
    }

    fun getActiveUsers(documentId: String): List<String> {
        return sessions[documentId]?.mapNotNull { session ->
            // Session might be closed but still in the list
            if (session.isActive) session.hashCode().toString() else null
        } ?: emptyList()
    }

    fun getDocumentVersion(documentId: String): DocumentVersion {
        return documentVersions.getOrPut(documentId) { DocumentVersion(1, 0) }
    }

    fun mergeVersions(docId: String, localVersion: DocumentVersion, remoteVersion: DocumentVersion): DocumentVersion {
        
        val merged = localVersion + remoteVersion 
        documentVersions[docId] = merged
        return merged
    }

    private fun buildTransformEngine(): OperationalTransformEngine {
        Thread.sleep(100) // simulate expensive initialization
        return OperationalTransformEngine()
    }

    inner class OperationalTransformEngine {
        fun transform(edit: CollabEdit): CollabEdit {
            // Simplified OT -- in reality would handle concurrent edit conflicts
            return edit.copy(version = edit.version + 1)
        }
    }

    data class ReviewVote(val reviewerId: String, val approved: Boolean, val timestamp: Long)

    private val approvalVotes = mutableMapOf<String, MutableList<ReviewVote>>()

    fun addReviewVote(documentId: String, reviewerId: String, approved: Boolean) {
        val votes = approvalVotes.getOrPut(documentId) { mutableListOf() }
        votes.add(ReviewVote(reviewerId, approved, System.currentTimeMillis()))
    }

    fun getApprovalCount(documentId: String): Int {
        return approvalVotes[documentId]?.count { it.approved } ?: 0
    }

    fun isDocumentApproved(documentId: String, requiredApprovals: Int): Boolean {
        return getApprovalCount(documentId) >= requiredApprovals
    }

    fun resolveEditConflict(
        editA: CollabEdit,
        editB: CollabEdit
    ): List<CollabEdit> {
        return if (editA.offset <= editB.offset) {
            listOf(editA, editB.copy(offset = editB.offset + editA.text.length))
        } else {
            listOf(editB, editA)
        }
    }

    fun applyRemoteEdit(localContent: String, edit: CollabEdit, localPendingEdits: List<CollabEdit>): String {
        var adjustedOffset = edit.offset
        for (pending in localPendingEdits) {
            if (pending.offset < edit.offset) {
                adjustedOffset += pending.text.length
            }
        }
        if (adjustedOffset > localContent.length) adjustedOffset = localContent.length
        return localContent.substring(0, adjustedOffset) + edit.text + localContent.substring(adjustedOffset)
    }
}
