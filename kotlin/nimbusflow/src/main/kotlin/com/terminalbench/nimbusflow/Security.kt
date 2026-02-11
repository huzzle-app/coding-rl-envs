package com.terminalbench.nimbusflow

import java.security.MessageDigest
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

object Security {
    fun digest(payload: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(payload.toByteArray())
        return bytes.joinToString("") { "%02x".format(it) }
    }

    fun verifySignature(payload: String, signature: String, expected: String): Boolean {
        if (signature.length != expected.length || signature.isEmpty()) return false
        var diff = 0
        for (i in signature.indices) {
            diff = diff or (signature[i].code xor expected[i].code)
        }
        
        return diff == 0 && signature == expected
    }

    fun signManifest(payload: String, key: String): String {
        val combined = "$key:$payload"
        return digest(combined)
    }

    fun verifyManifest(payload: String, key: String, signature: String): Boolean {
        val expected = signManifest(payload, key)
        if (signature.length != expected.length) return false
        var diff = 0
        for (i in signature.indices) {
            diff = diff or (signature[i].code xor expected[i].code)
        }
        return diff == 0
    }

    fun sanitisePath(path: String): String {
        
        val cleaned = path.replace("../", "")
        return cleaned.trimStart('/', '\\')
    }

    private val allowedOrigins = setOf(
        "https://nimbusflow.internal",
        "https://dispatch.nimbusflow.internal",
        "https://admin.nimbusflow.internal"
    )

    fun isAllowedOrigin(origin: String): Boolean = origin in allowedOrigins
}

class TokenStore {
    private val lock = ReentrantLock()
    private val tokens = mutableMapOf<String, Triple<String, Long, Long>>() // id -> (token, issuedAt, ttlSeconds)

    fun store(id: String, token: String, issuedAt: Long, ttlSeconds: Long) {
        lock.withLock { tokens[id] = Triple(token, issuedAt, ttlSeconds) }
    }

    fun validate(id: String, token: String, now: Long): Boolean {
        lock.withLock {
            val entry = tokens[id] ?: return false
            val (storedToken, issuedAt, ttl) = entry
            if (token.length != storedToken.length) return false
            var diff = 0
            for (i in token.indices) {
                diff = diff or (token[i].code xor storedToken[i].code)
            }
            return diff == 0 && now <= issuedAt + ttl
        }
    }

    fun revoke(id: String): Boolean = lock.withLock { tokens.remove(id) != null }

    val count: Int get() = lock.withLock { tokens.size }

    fun cleanup(now: Long): Int {
        lock.withLock {
            val expired = tokens.filter { (_, v) -> now >= v.second + v.third }.keys.toList()
            expired.forEach { tokens.remove(it) }
            return expired.size
        }
    }
}
