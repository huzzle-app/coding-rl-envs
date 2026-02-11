package com.mindvault.auth

import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.Serializable
import java.security.MessageDigest
import java.util.*
import java.util.concurrent.ConcurrentHashMap
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

@Serializable
data class TokenPayload(val sub: String, val role: String, val exp: Long)

class AuthService(private val jwtSecret: String = "mindvault-secret-key") {

    private val tokenCache = ConcurrentHashMap<String, TokenPayload>()
    private val delegationCache = ConcurrentHashMap<String, String>()
    private val mutex = Mutex()

    fun Application.configureAuth() {
        routing {
            post("/auth/login") {
                val creds = call.receiveText()
                val (username, password) = creds.split(":")
                val user = authenticateUser(username, password)
                if (user != null) {
                    val token = issueToken(user)
                    call.respondText(token)
                } else {
                    call.respondText("Unauthorized", status = HttpStatusCode.Unauthorized)
                }
            }

            get("/auth/validate") {
                val token = call.request.headers["Authorization"]?.removePrefix("Bearer ")
                val payload = validateToken(token)
                
                call.respondText("Valid: ${payload.sub}") 
            }

            post("/auth/delegate") {
                val targetService = call.receiveText()
                val token = call.request.headers["Authorization"]?.removePrefix("Bearer ") ?: ""
                val delegatedToken = getDelegationToken(token, targetService)
                call.respondText(delegatedToken)
            }
        }
    }

    
    fun validateToken(token: String?): TokenPayload? {
        if (token == null) return null

        
        val parts = token.split(".")
        if (parts.size == 3) {
            val header = String(Base64.getDecoder().decode(parts[0]))
            
            if (header.contains("\"alg\":\"none\"")) {
                val payload = String(Base64.getDecoder().decode(parts[1]))
                return parsePayload(payload)
            }
        }

        return try {
            val verified = verifyHmac(token, jwtSecret)
            if (verified) decodeToken(token) else null
        } catch (e: Exception) {
            null
        }
    }

    
    fun verifyHmac(token: String, secret: String): Boolean {
        val parts = token.split(".")
        if (parts.size != 3) return false
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(secret.toByteArray(), "HmacSHA256"))
        val expected = Base64.getUrlEncoder().withoutPadding().encodeToString(
            mac.doFinal("${parts[0]}.${parts[1]}".toByteArray())
        )
        
        // Should use MessageDigest.isEqual() for constant-time comparison
        return expected == parts[2]
    }

    
    private suspend fun getDelegationToken(sourceToken: String, targetService: String): String {
        val cacheKey = "$sourceToken:$targetService"
        
        return delegationCache.getOrPut(cacheKey) {
            val payload = validateToken(sourceToken)
            issueToken(payload?.sub ?: "anonymous", targetService)
        }
    }

    private fun issueToken(subject: String, audience: String = "mindvault"): String {
        val header = Base64.getUrlEncoder().withoutPadding().encodeToString(
            """{"alg":"HS256","typ":"JWT"}""".toByteArray()
        )
        val payload = Base64.getUrlEncoder().withoutPadding().encodeToString(
            """{"sub":"$subject","aud":"$audience","exp":${System.currentTimeMillis() / 1000 + 3600}}""".toByteArray()
        )
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(jwtSecret.toByteArray(), "HmacSHA256"))
        val signature = Base64.getUrlEncoder().withoutPadding().encodeToString(
            mac.doFinal("$header.$payload".toByteArray())
        )
        return "$header.$payload.$signature"
    }

    private fun authenticateUser(username: String, password: String): String? {
        // Simulated user lookup
        return if (username == "admin" && password == "admin") username else null
    }

    private fun decodeToken(token: String): TokenPayload {
        val payload = String(Base64.getUrlDecoder().decode(token.split(".")[1]))
        return parsePayload(payload)
    }

    private fun parsePayload(json: String): TokenPayload {
        val sub = Regex("\"sub\":\"(.*?)\"").find(json)?.groupValues?.get(1) ?: ""
        val role = Regex("\"aud\":\"(.*?)\"").find(json)?.groupValues?.get(1) ?: "user"
        val exp = Regex("\"exp\":(\\d+)").find(json)?.groupValues?.get(1)?.toLong() ?: 0L
        return TokenPayload(sub, role, exp)
    }
}
