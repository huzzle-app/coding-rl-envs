package com.pulsemap.security

import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertContains

/**
 * Tests for security: SQL injection prevention and path traversal blocking.
 *
 * Bug-specific tests:
 *   I1 - SQL injection via name parameter (string interpolation in query)
 *   I2 - Path traversal in tile endpoint (../../../etc/passwd)
 */
class SecurityTests {

    // =========================================================================
    // I1: SQL injection prevention
    // =========================================================================

    @Test
    fun test_sql_injection_prevented() {
        
        // Allowing SQL injection via the name parameter
        val dao = SensorDao()
        val maliciousName = "'; DROP TABLE sensors; --"
        val result = dao.findByName(maliciousName)
        // The query should use parameterized statements and NOT execute injected SQL
        assertFalse(
            result.queryExecuted.contains("DROP TABLE"),
            "SQL injection should be prevented by parameterized queries"
        )
    }

    @Test
    fun test_parameterized_query_used() {
        
        val dao = SensorDao()
        val normalName = "temperature_sensor"
        val result = dao.findByName(normalName)
        assertTrue(
            result.usedParameterizedQuery,
            "Query should use parameterized statements, not string interpolation"
        )
    }

    // =========================================================================
    // I2: Path traversal in tile endpoint
    // =========================================================================

    @Test
    fun test_path_traversal_blocked() {
        
        val tileService = TileService()
        val maliciousPaths = listOf(
            "../../../etc/passwd",
            "..\\..\\..\\etc\\passwd",
            "tiles/../../../etc/shadow",
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "/etc/passwd"
        )
        for (path in maliciousPaths) {
            val result = tileService.getTile(path)
            assertFalse(
                result.served,
                "Path traversal should be blocked for: $path"
            )
            assertEquals(
                400,
                result.statusCode,
                "Path traversal attempt should return 400, not serve file: $path"
            )
        }
    }

    @Test
    fun test_tile_path_validated() {
        
        val tileService = TileService()
        val validPath = "tiles/12/345/678.png"
        val result = tileService.getTile(validPath)
        assertTrue(result.pathValidated, "Tile path should be validated before serving")
        assertEquals(200, result.statusCode, "Valid tile path should return 200")
    }

    // =========================================================================
    // Baseline: Auth and security fundamentals
    // =========================================================================

    @Test
    fun test_jwt_token_validation() {
        val authService = AuthService()
        val validToken = authService.generateToken("user1", role = "reader")
        val result = authService.validateToken(validToken)
        assertTrue(result.valid, "Valid JWT should pass validation")
        assertEquals("user1", result.userId)
    }

    @Test
    fun test_expired_jwt_rejected() {
        val authService = AuthService()
        val expiredToken = "expired.jwt.token"
        val result = authService.validateToken(expiredToken)
        assertFalse(result.valid, "Expired JWT should be rejected")
    }

    @Test
    fun test_malformed_jwt_rejected() {
        val authService = AuthService()
        val malformedToken = "not-a-jwt"
        val result = authService.validateToken(malformedToken)
        assertFalse(result.valid, "Malformed JWT should be rejected")
    }

    @Test
    fun test_jwt_secret_sufficient_length() {
        val authService = AuthService()
        val secret = authService.getJwtSecret()
        assertTrue(
            secret.length >= 32,
            "JWT secret should be at least 32 characters, but was ${secret.length}"
        )
    }

    @Test
    fun test_api_key_validation() {
        val authService = AuthService()
        val result = authService.validateApiKey("valid-api-key-12345")
        assertTrue(result, "Valid API key should be accepted")
    }

    @Test
    fun test_empty_api_key_rejected() {
        val authService = AuthService()
        val result = authService.validateApiKey("")
        assertFalse(result, "Empty API key should be rejected")
    }

    @Test
    fun test_null_bearer_token_rejected() {
        val authService = AuthService()
        val result = authService.validateToken(null)
        assertFalse(result.valid, "Null token should be rejected")
    }

    @Test
    fun test_sql_injection_in_sensor_id() {
        val dao = SensorDao()
        val maliciousId = "1 OR 1=1"
        val result = dao.findById(maliciousId)
        assertTrue(result.usedParameterizedQuery, "Sensor ID query should be parameterized")
    }

    @Test
    fun test_tile_path_rejects_null_bytes() {
        val tileService = TileService()
        val nullBytePath = "tiles/12/345/678\u0000.png"
        val result = tileService.getTile(nullBytePath)
        assertFalse(result.served, "Paths with null bytes should be rejected")
    }

    @Test
    fun test_valid_tile_path_format() {
        val tileService = TileService()
        // Standard slippy map tile format: z/x/y.ext
        val result = tileService.getTile("tiles/15/16384/10000.png")
        assertTrue(result.pathValidated, "Standard tile path should be validated as safe")
    }

    @Test
    fun test_rate_limiting_exists() {
        val rateLimiter = RateLimiter(maxRequests = 100, windowSeconds = 60)
        // First request should be allowed
        assertTrue(rateLimiter.allowRequest("client1"), "First request should be allowed")
        // Simulate exhausting the limit
        repeat(100) { rateLimiter.allowRequest("client1") }
        assertFalse(rateLimiter.allowRequest("client1"), "Should be rate limited after 100 requests")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    data class QueryResult(
        val data: List<Map<String, Any>> = emptyList(),
        val queryExecuted: String,
        val usedParameterizedQuery: Boolean
    )

    class SensorDao {
        fun findByName(name: String): QueryResult {
            
            val query = "SELECT * FROM sensors WHERE name = '$name'"
            return QueryResult(
                queryExecuted = query,
                usedParameterizedQuery = false 
            )
        }

        fun findById(id: String): QueryResult {
            // Same pattern for ID queries
            val query = "SELECT * FROM sensors WHERE id = '$id'"
            return QueryResult(
                queryExecuted = query,
                usedParameterizedQuery = false 
            )
        }
    }

    data class TileResult(
        val served: Boolean,
        val statusCode: Int,
        val pathValidated: Boolean
    )

    class TileService {
        fun getTile(path: String): TileResult {
            
            val containsTraversal = path.contains("..") || path.contains("%2F") || path.startsWith("/")
            val containsNullByte = path.contains('\u0000')

            if (containsTraversal || containsNullByte) {
                
                // Simulating the BUG by still serving the file
                return TileResult(
                    served = true, 
                    statusCode = 200, 
                    pathValidated = false 
                )
            }

            return TileResult(served = true, statusCode = 200, pathValidated = true)
        }
    }

    data class TokenValidation(val valid: Boolean, val userId: String? = null)

    class AuthService {
        fun generateToken(userId: String, role: String): String {
            return "valid.jwt.$userId.$role"
        }

        fun validateToken(token: String?): TokenValidation {
            if (token == null) return TokenValidation(false)
            if (!token.startsWith("valid.jwt.")) return TokenValidation(false)
            val parts = token.split(".")
            if (parts.size < 3) return TokenValidation(false)
            return TokenValidation(valid = true, userId = parts[2])
        }

        fun getJwtSecret(): String {
            // Note: The actual config uses "short-secret" which is too short
            return "short-secret" // 12 chars -- insufficient
        }

        fun validateApiKey(key: String): Boolean {
            return key.isNotEmpty() && key.length >= 10
        }
    }

    class RateLimiter(private val maxRequests: Int, private val windowSeconds: Int) {
        private val requestCounts = mutableMapOf<String, Int>()

        fun allowRequest(clientId: String): Boolean {
            val count = requestCounts.getOrDefault(clientId, 0)
            if (count >= maxRequests) return false
            requestCounts[clientId] = count + 1
            return true
        }
    }
}
