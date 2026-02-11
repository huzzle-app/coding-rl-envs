package com.mindvault.documents

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import org.jetbrains.exposed.sql.*
import org.jetbrains.exposed.sql.SchemaUtils
import org.jetbrains.exposed.sql.transactions.experimental.newSuspendedTransaction
import org.jetbrains.exposed.sql.transactions.transaction
import java.io.ByteArrayInputStream
import java.io.ObjectInputStream
import java.time.Instant
import java.util.concurrent.ConcurrentHashMap


// Should use epochSecond + nano pair or a fixed format
object InstantSerializer : KSerializer<Instant> {
    override val descriptor = PrimitiveSerialDescriptor("Instant", PrimitiveKind.STRING)
    override fun serialize(encoder: Encoder, value: Instant) = encoder.encodeString(value.toString()) 
    override fun deserialize(decoder: Decoder): Instant = Instant.parse(decoder.decodeString())
}

@Serializable
data class Document(
    val id: String,
    val title: String,
    val content: String,
    @Serializable(with = InstantSerializer::class)
    val createdAt: Instant = Instant.now(),
    val tags: List<String> = emptyList(),
    val checksum: ByteArray = byteArrayOf() // Used in BUG C1
) {
    
    // data class copy() does not deep-copy collection fields
    fun duplicate(newTitle: String): Document = this.copy(title = newTitle) 

    
    // data class auto-generated equals uses ByteArray reference equality
    // Two Documents with same checksum bytes will not be equal
}

object Documents : Table("documents") {
    val id = varchar("id", 64)
    val title = varchar("title", 256)
    val content = text("content")
    val createdAt = long("created_at")
    val ownerId = varchar("owner_id", 64)
    override val primaryKey = PrimaryKey(id)
}

class DocumentService {

    private val versionCache = ConcurrentHashMap<String, Document>()

    
    fun initSchema() {
        transaction {
            SchemaUtils.create(Documents) 
        }
    }

    
    fun streamDocuments(ownerId: String): Flow<Document> = flow {
        val connection = openDatabaseConnection() // acquired before flow collection
        try {
            
            // because flow {} doesn't guarantee cleanup on CancellationException the same way
            val results = queryDocuments(connection, ownerId)
            results.forEach { doc ->
                emit(doc)
                delay(10) // simulate backpressure
            }
        } finally {
            // This runs on cancellation, but connection.close() might throw
            // and swallow the CancellationException
            connection.close()
        }
    }

    
    // This bug MASKS BUG B1 (platform type NPE in loadDocumentFromJdbc)
    // Because bulkImport returns immediately without waiting, any NPE thrown
    // in the launched coroutines is swallowed silently (no exception handler).
    // Fixing A4 (using coroutineScope { } instead) will cause the NPE from B1
    // to propagate to the caller when a document with null fields is imported.
    suspend fun bulkImport(documents: List<Document>) {
        val scope = CoroutineScope(Dispatchers.IO) 
        documents.forEach { doc ->
            scope.launch { 
                saveDocument(doc)
            }
        }
        // Returns immediately, imports may not be complete
        // If caller cancels, these coroutines keep running
    }

    
    suspend fun saveDocument(doc: Document) {
        newSuspendedTransaction { 
            Documents.insert {
                it[id] = doc.id
                it[title] = doc.title
                it[content] = doc.content
                it[createdAt] = doc.createdAt.toEpochMilli()
                it[ownerId] = "system"
            }
        }
    }

    
    fun loadDocumentFromJdbc(rs: java.sql.ResultSet): Document {
        val id = rs.getString("id")         
        val title = rs.getString("title")   
        val content = rs.getString("content")
        return Document(
            id = id,       // Passes null as non-null String parameter
            title = title, // NPE at runtime when null
            content = content
        )
    }

    
    fun restoreFromBackup(data: ByteArray): Any {
        val ois = ObjectInputStream(ByteArrayInputStream(data)) 
        return ois.readObject() // Remote code execution via crafted payload
    }

    private fun openDatabaseConnection(): java.sql.Connection {
        return java.sql.DriverManager.getConnection("jdbc:postgresql://localhost:5432/mindvault")
    }

    private fun queryDocuments(conn: java.sql.Connection, ownerId: String): List<Document> {
        return listOf(
            Document("1", "Doc 1", "Content 1"),
            Document("2", "Doc 2", "Content 2")
        )
    }
}
