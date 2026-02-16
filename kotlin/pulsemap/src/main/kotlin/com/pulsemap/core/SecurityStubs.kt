package com.pulsemap.core

// =============================================================================
// Security stubs: Simulate SQL injection, path traversal, and auth vulnerabilities.
// Bugs: I1 (SQL injection), I2 (path traversal), plus JWT secret length issue
// =============================================================================

data class QueryResult(
    val data: List<Map<String, Any>> = emptyList(),
    val queryExecuted: String,
    val usedParameterizedQuery: Boolean
)

/**
 * Simulates database access for sensor data.
 *
 * BUG I1: Uses string interpolation in SQL queries instead of parameterized
 * statements, allowing SQL injection attacks.
 */
class SensorDao {
    fun findByName(name: String): QueryResult {
        // BUG I1: String interpolation allows SQL injection
        // Should use parameterized query: "SELECT * FROM sensors WHERE name = ?"
        val query = "SELECT * FROM sensors WHERE name = '$name'"
        return QueryResult(
            queryExecuted = query,
            usedParameterizedQuery = false
        )
    }

    fun findById(id: String): QueryResult {
        // BUG I1: Same string interpolation vulnerability for ID queries
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

/**
 * Simulates tile file serving.
 *
 * BUG I2: Detects path traversal attempts but still serves the file.
 * The path validation is present but doesn't actually block the request.
 */
class TileServiceSecurity {
    fun getTile(path: String): TileResult {
        val containsTraversal = path.contains("..") || path.contains("%2F") || path.startsWith("/")
        val containsNullByte = path.contains('\u0000')

        if (containsTraversal || containsNullByte) {
            // BUG I2: Detects the traversal but STILL serves the file (should return 400)
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

/**
 * Simulates JWT authentication service.
 * Also has a weak JWT secret (too short).
 */
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
        return "pulsemap-jwt-secret-key-for-hmac256-signing" // 44 chars
    }

    fun validateApiKey(key: String): Boolean {
        return key.isNotEmpty() && key.length >= 10
    }
}

/**
 * Simple rate limiter for API endpoints.
 */
class RateLimiter(private val maxRequests: Int, private val windowSeconds: Int) {
    private val requestCounts = mutableMapOf<String, Int>()

    fun allowRequest(clientId: String): Boolean {
        val count = requestCounts.getOrDefault(clientId, 0)
        if (count >= maxRequests) return false
        requestCounts[clientId] = count + 1
        return true
    }
}
