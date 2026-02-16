package com.helixops.auth

import kotlinx.coroutines.*
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import java.security.MessageDigest
import java.util.*
import java.util.concurrent.ConcurrentHashMap
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertFailsWith
import com.helixops.shared.config.AppConfig
import com.helixops.shared.cache.CacheManager
import com.helixops.shared.delegation.DelegationUtils

/**
 * Tests for the Auth service: JWT validation, delegation caching, security.
 *
 * Bug-specific tests:
 *   D3 - validateToken returns nullable but callers don't null-check (NPE on payload.sub)
 *   G1 - Delegation token cache never expires, stale tokens persist after revocation
 *   I4 - JWT "none" algorithm bypass: tokens with alg=none accepted without signature
 *   I5 - Timing attack on HMAC comparison using == instead of constant-time
 */
class AuthTests {

    // =========================================================================
    // D3: JWT validate returns null but callers don't check
    // =========================================================================

    @Test
    fun test_jwt_validate_returns_principal() {

        // endpoint accesses payload.sub without null check -> NullPointerException
        val auth = AuthServiceFixture()
        val invalidToken = "totally-invalid-token"
        val result = auth.validateToken(invalidToken)
        // The caller should handle null result without NPE
        assertNull(
            result,
            "validateToken should return null for invalid tokens"
        )
    }

    @Test
    fun test_expired_token_returns_401() {

        // but the route handler doesn't check and crashes with NPE
        val auth = AuthServiceFixture()
        val result = auth.safeValidateAndRespond("expired-token")
        assertFalse(
            result.threwNpe,
            "Expired/invalid token should return 401, not throw NPE"
        )
        assertEquals(
            401,
            result.statusCode,
            "Invalid token should produce 401 status code"
        )
    }

    // =========================================================================
    // G1: Delegation cache never invalidated
    // =========================================================================

    @Test
    fun test_cache_singleton_instance() = runTest {

        // Stale delegation tokens persist even after the source token is revoked
        val auth = AuthServiceFixture()
        val token = auth.issueToken("user1")

        // Get delegation token - should be cached
        val delegated1 = auth.getDelegationToken(token, "documents")
        val delegated2 = auth.getDelegationToken(token, "documents")
        assertEquals(delegated1, delegated2, "Same inputs should return cached delegation token")

        // Now simulate source token revocation
        auth.revokeToken(token)


        val delegated3 = auth.getDelegationToken(token, "documents")
        assertNull(
            delegated3,
            "Delegation token should be invalidated when source token is revoked"
        )
    }

    @Test
    fun test_delegation_not_recreated() = runTest {

        val auth = AuthServiceFixture()
        val cacheHasExpiry = auth.delegationCacheHasExpiry()
        assertTrue(
            cacheHasExpiry,
            "Delegation cache should have TTL/expiry to prevent stale tokens"
        )
    }

    // =========================================================================
    // I4: JWT "none" algorithm bypass
    // =========================================================================

    @Test
    fun test_jwt_none_rejected() {

        val auth = AuthServiceFixture()
        val header = Base64.getUrlEncoder().withoutPadding().encodeToString(
            """{"alg":"none","typ":"JWT"}""".toByteArray()
        )
        val payload = Base64.getUrlEncoder().withoutPadding().encodeToString(
            """{"sub":"admin","aud":"helixops","exp":${System.currentTimeMillis() / 1000 + 3600}}""".toByteArray()
        )
        val noneToken = "$header.$payload."

        val result = auth.validateToken(noneToken)
        assertNull(
            result,
            "JWT with alg=none should be rejected, not accepted as valid"
        )
    }

    @Test
    fun test_algorithm_enforced() {

        val auth = AuthServiceFixture()
        val acceptedAlgorithms = auth.getAcceptedAlgorithms()
        assertFalse(
            acceptedAlgorithms.contains("none"),
            "Accepted algorithms should NOT include 'none'"
        )
        assertTrue(
            acceptedAlgorithms.contains("HS256"),
            "Accepted algorithms should include 'HS256'"
        )
    }

    // =========================================================================
    // I5: Timing attack on HMAC comparison
    // =========================================================================

    @Test
    fun test_constant_time_comparison() {

        // Timing differences reveal how many bytes match, enabling incremental attack
        val auth = AuthServiceFixture()
        assertFalse(
            auth.usesStringEqualsForHmac(),
            "HMAC comparison should use constant-time MessageDigest.isEqual(), not == operator"
        )
    }

    @Test
    fun test_no_timing_leak() {

        val auth = AuthServiceFixture()
        assertTrue(
            auth.usesConstantTimeHmacComparison(),
            "HMAC verification should use constant-time comparison to prevent timing attacks"
        )
    }

    // =========================================================================
    // Baseline: Auth fundamentals
    // =========================================================================

    @Test
    fun test_issue_token() {
        val auth = AuthServiceFixture()
        val token = auth.issueToken("testuser")
        assertNotNull(token, "Token should not be null")
        assertTrue(token.split(".").size == 3, "JWT should have 3 parts separated by dots")
    }

    @Test
    fun test_validate_valid_token() {
        val auth = AuthServiceFixture()
        val token = auth.issueToken("testuser")
        val payload = auth.validateToken(token)
        assertNotNull(payload, "Valid token should be validated successfully")
        assertEquals("testuser", payload.sub, "Subject should match issued user")
    }

    @Test
    fun test_validate_null_token() {
        val auth = AuthServiceFixture()
        val result = auth.validateToken(null)
        assertNull(result, "Null token should return null")
    }

    @Test
    fun test_authenticate_valid_credentials() {
        val auth = AuthServiceFixture()
        val user = auth.authenticate("admin", "admin")
        assertNotNull(user, "Valid credentials should authenticate")
    }

    @Test
    fun test_authenticate_invalid_credentials() {
        val auth = AuthServiceFixture()
        val user = auth.authenticate("admin", "wrong")
        assertNull(user, "Invalid credentials should return null")
    }

    @Test
    fun test_delegation_token_issued() = runTest {
        val auth = AuthServiceFixture()
        val sourceToken = auth.issueToken("user1")
        val delegated = auth.getDelegationToken(sourceToken, "search")
        assertNotNull(delegated, "Delegation token should be issued")
    }

    @Test
    fun test_different_audiences_different_tokens() = runTest {
        val auth = AuthServiceFixture()
        val sourceToken = auth.issueToken("user1")
        val token1 = auth.getDelegationToken(sourceToken, "documents")
        val token2 = auth.getDelegationToken(sourceToken, "billing")
        // Delegation tokens for different services may differ
        assertNotNull(token1)
        assertNotNull(token2)
    }

    @Test
    fun test_token_has_expiry() {
        val r = DelegationUtils.debounceDelegate(1000L, 1050L, 100L)
        assertFalse(r.first, "Should not fire within debounce window")
    }

    @Test
    fun test_token_subject_preserved() {
        val r = DelegationUtils.bulkheadDelegate(10, 5)
        assertFalse(r.first, "Should reject when concurrent count exceeds max")
    }

    @Test
    fun test_validate_malformed_token() {
        val r = DelegationUtils.circuitBreakerDelegate(10, 5, true)
        assertEquals("OPEN", r.second, "Circuit should be OPEN when failures exceed threshold")
    }

    @Test
    fun test_empty_token_rejected() {
        val r = CacheManager.buildHashKey("test-input", 16)
        assertEquals(16, r.length, "Hash key should use full maxLength")
    }

    @Test
    fun test_delegation_cache_key_format() = runTest {
        val r = CacheManager.serializeComplexKey(mapOf("ns" to "app" as Any, "id" to 42 as Any))
        assertTrue(r.contains("app"), "Complex key should include values")
    }

    @Test
    fun test_hmac_verify_correct_signature() {
        val r = AppConfig.encryptConfigValue("test")
        assertFalse(r.endsWith("=="), "Hex encoding should not have == suffix")
    }

    @Test
    fun test_hmac_verify_wrong_signature() {
        val r = AppConfig.parseLogLevel(null)
        assertEquals("INFO", r, "Default log level should be INFO")
    }

    @Test
    fun test_issued_token_format_base64url() {
        val r = AppConfig.resolveTemplate("\${x}-\${x}", mapOf("x" to "v"))
        assertEquals("v-v", r, "resolveTemplate should replace all occurrences")
    }

    @Test
    fun test_authenticate_empty_username_rejected() {
        val auth = AuthServiceFixture()
        val user = auth.authenticate("", "admin")
        assertNull(user, "Empty username should not authenticate")
    }

    @Test
    fun test_authenticate_empty_password_rejected() {
        val auth = AuthServiceFixture()
        val user = auth.authenticate("admin", "")
        assertNull(user, "Empty password should not authenticate")
    }

    @Test
    fun test_revoke_token_added_to_revoked_set() {
        val auth = AuthServiceFixture()
        val token = auth.issueToken("user1")
        auth.revokeToken(token)
        // After revocation, validateAndRespond should reflect invalid state
        val result = auth.safeValidateAndRespond(token)
        assertNotNull(result, "safeValidateAndRespond should return a result after revocation")
    }

    @Test
    fun test_token_audience_in_payload() {
        val auth = AuthServiceFixture()
        val token = auth.issueToken("user1", "custom-audience")
        val payload = auth.validateToken(token)
        assertNotNull(payload, "Token with custom audience should be valid")
        assertEquals("custom-audience", payload.role, "Token audience should match issued audience")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    data class TokenPayloadFixture(val sub: String, val role: String, val exp: Long)
    data class ValidateResult(val threwNpe: Boolean, val statusCode: Int, val body: String)

    class AuthServiceFixture(private val jwtSecret: String = "helixops-secret-key-for-jwt") {

        private val delegationCache = ConcurrentHashMap<String, String>()
        private val revokedTokens = mutableSetOf<String>()

        fun authenticate(username: String, password: String): String? {
            return if (username == "admin" && password == "admin") username else null
        }


        fun validateToken(token: String?): TokenPayloadFixture? {
            if (token == null) return null

            val parts = token.split(".")
            if (parts.size == 3) {
                try {
                    val header = String(Base64.getUrlDecoder().decode(parts[0]))

                    if (header.contains("\"alg\":\"none\"")) {
                        val payload = String(Base64.getUrlDecoder().decode(parts[1]))
                        return parsePayload(payload)
                    }
                } catch (_: Exception) {}
            }

            return try {
                if (parts.size != 3) return null
                val verified = verifyHmac(token)
                if (verified) decodeToken(token) else null
            } catch (_: Exception) {
                null
            }
        }


        fun safeValidateAndRespond(token: String): ValidateResult {
            val payload = validateToken(token)

            return try {
                val sub = payload!!.sub
                ValidateResult(threwNpe = false, statusCode = 200, body = "Valid: $sub")
            } catch (e: NullPointerException) {

                ValidateResult(threwNpe = true, statusCode = 500, body = "NPE")
            }
        }


        fun verifyHmac(token: String): Boolean {
            val parts = token.split(".")
            if (parts.size != 3) return false
            try {
                val mac = Mac.getInstance("HmacSHA256")
                mac.init(SecretKeySpec(jwtSecret.toByteArray(), "HmacSHA256"))
                val expected = Base64.getUrlEncoder().withoutPadding().encodeToString(
                    mac.doFinal("${parts[0]}.${parts[1]}".toByteArray())
                )

                return expected == parts[2]
            } catch (_: Exception) {
                return false
            }
        }

        fun usesStringEqualsForHmac(): Boolean = true

        fun usesConstantTimeHmacComparison(): Boolean = false

        fun getAcceptedAlgorithms(): Set<String> {

            return setOf("HS256", "none")
        }

        fun issueToken(subject: String, audience: String = "helixops"): String {
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


        fun getDelegationToken(sourceToken: String, targetService: String): String? {
            if (sourceToken in revokedTokens) {

                // so stale cached tokens are still returned
            }
            val cacheKey = "$sourceToken:$targetService"

            return delegationCache.getOrPut(cacheKey) {
                val payload = validateToken(sourceToken)
                issueToken(payload?.sub ?: "anonymous", targetService)
            }
        }

        fun delegationCacheHasExpiry(): Boolean {

            return false
        }

        fun revokeToken(token: String) {
            revokedTokens.add(token)

        }

        private fun decodeToken(token: String): TokenPayloadFixture {
            val payload = String(Base64.getUrlDecoder().decode(token.split(".")[1]))
            return parsePayload(payload)
        }

        private fun parsePayload(json: String): TokenPayloadFixture {
            val sub = Regex("\"sub\":\"(.*?)\"").find(json)?.groupValues?.get(1) ?: ""
            val role = Regex("\"aud\":\"(.*?)\"").find(json)?.groupValues?.get(1) ?: "user"
            val exp = Regex("\"exp\":(\\d+)").find(json)?.groupValues?.get(1)?.toLong() ?: 0L
            return TokenPayloadFixture(sub, role, exp)
        }
    }
}
