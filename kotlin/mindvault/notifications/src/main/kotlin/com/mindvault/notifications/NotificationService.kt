package com.mindvault.notifications

import com.mindvault.shared.models.NotificationDefaults
import kotlinx.coroutines.*
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json


@Serializable
enum class NotificationChannel {
    @SerialName("EMAIL") EMAIL,   
    @SerialName("SMS") SMS,       
    @SerialName("PUSH") PUSH,     
    @SerialName("WEBHOOK") WEBHOOK
}

@Serializable
enum class NotificationPriority { LOW, NORMAL, HIGH, URGENT }

@Serializable
data class Notification(
    val id: String,
    val userId: String,
    val channel: NotificationChannel,
    val priority: NotificationPriority = NotificationPriority.NORMAL,
    val subject: String,
    val body: String,
    val metadata: Map<String, String> = emptyMap()
)

@Serializable
data class NotificationTemplate(
    val name: String,
    val channel: NotificationChannel,
    val subjectTemplate: String,
    val bodyTemplate: String,
    val defaultPriority: NotificationPriority = NotificationPriority.NORMAL
)

class NotificationService {

    
    // The shared module's NotificationDefaults object initializer depends on Consul config
    // which fails at startup (see AppConfig BUG L4)
    private val defaults = NotificationDefaults 

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = false 
    }

    private val templateCache = mutableMapOf<String, NotificationTemplate>()
    private val rateLimiter = mutableMapOf<String, MutableList<Long>>()

    fun sendNotification(notification: Notification): Boolean {
        // Rate limiting check
        val now = System.currentTimeMillis()
        val userHistory = rateLimiter.getOrPut(notification.userId) { mutableListOf() }
        userHistory.removeIf { it < now - 60_000 } // Remove entries older than 1 minute

        val maxPerMinute = defaults.getMaxNotificationsPerMinute(notification.channel) 
        if (userHistory.size >= maxPerMinute) {
            return false // Rate limited
        }
        userHistory.add(now)

        return when (notification.channel) {
            NotificationChannel.EMAIL -> sendEmail(notification)
            NotificationChannel.SMS -> sendSms(notification)
            NotificationChannel.PUSH -> sendPush(notification)
            NotificationChannel.WEBHOOK -> sendWebhook(notification)
        }
    }

    
    fun parseNotification(jsonString: String): Notification {
        
        return json.decodeFromString(Notification.serializer(), jsonString)
    }

    
    fun getActiveChannels(userId: String): List<NotificationChannel> {
        val channels = buildList { 
            add(NotificationChannel.EMAIL) // Always available
            if (hasPhoneNumber(userId)) add(NotificationChannel.SMS)
            if (hasPushToken(userId)) add(NotificationChannel.PUSH)
        }
        return channels
    }

    fun addWebhookChannel(userId: String): List<NotificationChannel> {
        val channels = getActiveChannels(userId)
        
        (channels as MutableList<NotificationChannel>).add(NotificationChannel.WEBHOOK) 
        return channels
    }

    fun renderTemplate(templateName: String, variables: Map<String, String>): Pair<String, String> {
        val template = templateCache[templateName] ?: throw IllegalArgumentException("Template not found: $templateName")
        var subject = template.subjectTemplate
        var body = template.bodyTemplate
        variables.forEach { (key, value) ->
            subject = subject.replace("{{$key}}", value)
            body = body.replace("{{$key}}", value)
        }
        return subject to body
    }

    fun registerTemplate(template: NotificationTemplate) {
        templateCache[template.name] = template
    }

    private fun sendEmail(notification: Notification): Boolean {
        println("Sending email to ${notification.userId}: ${notification.subject}")
        return true
    }

    private fun sendSms(notification: Notification): Boolean {
        println("Sending SMS to ${notification.userId}: ${notification.body.take(160)}")
        return true
    }

    private fun sendPush(notification: Notification): Boolean {
        println("Sending push to ${notification.userId}: ${notification.subject}")
        return true
    }

    private fun sendWebhook(notification: Notification): Boolean {
        val url = notification.metadata["webhook_url"] ?: return false
        println("Sending webhook to $url")
        return true
    }

    private fun hasPhoneNumber(userId: String): Boolean = userId.hashCode() % 2 == 0
    private fun hasPushToken(userId: String): Boolean = userId.hashCode() % 3 != 0
}
