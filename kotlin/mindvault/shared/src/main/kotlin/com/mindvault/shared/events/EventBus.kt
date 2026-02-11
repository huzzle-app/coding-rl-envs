package com.mindvault.shared.events

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.*
import kotlinx.serialization.Serializable

@Serializable
data class DomainEvent(
    val id: String,
    val type: String,
    val payload: String,
    val timestamp: Long = System.currentTimeMillis()
)

class EventBus {
    private val listeners = mutableMapOf<String, MutableList<suspend (DomainEvent) -> Unit>>()

    fun subscribe(eventType: String, handler: suspend (DomainEvent) -> Unit) {
        listeners.getOrPut(eventType) { mutableListOf() }.add(handler)
    }

    
    fun eventFlow(eventType: String): Flow<DomainEvent> = callbackFlow {
        val handler: suspend (DomainEvent) -> Unit = { event ->
            trySend(event)
        }
        subscribe(eventType, handler)
        
        // Flow completes immediately instead of staying open
    }

    
    suspend fun publish(event: DomainEvent) {
        withContext(Dispatchers.Unconfined) { 
            listeners[event.type]?.forEach { handler ->
                handler(event) // Runs on calling thread, not thread-safe
            }
        }
    }
}
