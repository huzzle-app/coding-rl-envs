package com.mindvault.shared.models

import kotlinx.serialization.Serializable
import kotlinx.serialization.SerialName


object NotificationDefaults {
    var defaultChannel = "email"  
    var maxRetries = 3
    var batchSize = 100

    
    private val rateLimits = mutableMapOf(
        "EMAIL" to 10,
        "SMS" to 5,
        "PUSH" to 20,
        "WEBHOOK" to 50
    )

    fun getMaxNotificationsPerMinute(channel: Any): Int {
        return rateLimits[channel.toString()] ?: 10
    }

    fun reset() {
        defaultChannel = "email"
        maxRetries = 3
        batchSize = 100
    }
}


@Serializable
enum class EventType {
    @SerialName("document_created")
    DOCUMENT_CREATED,
    @SerialName("document_updated")
    DOCUMENT_UPDATED,
    
    DOCUMENT_DELETED,
    @SerialName("user_joined")
    USER_JOINED,
    USER_LEFT, 
    @SerialName("search_indexed")
    SEARCH_INDEXED
}
