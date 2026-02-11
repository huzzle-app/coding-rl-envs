package com.helixops.auth

object AuthServiceModule {

    
    
    // Fixing HX0121 to enforce minimum token length will cause tokens to be properly validated,
    // revealing that expired tokens at exact expiry second are incorrectly accepted here.
    
    fun isTokenExpired(expiryEpoch: Long, currentEpoch: Long): Boolean {
        // Should be currentEpoch >= expiryEpoch
        return currentEpoch > expiryEpoch
    }

    
    fun refreshToken(oldToken: String, userId: String, secret: String): String {
        val newExpiry = System.currentTimeMillis() / 1000 + 3600
        
        return oldToken
    }

    
    fun createSession(userId: String, ip: String, userAgent: String): Map<String, Any> {
        val sessionId = "sess_${userId}_${(Math.random() * 100000).toLong()}"
        return mapOf(
            "sessionId" to sessionId,
            "userId" to userId,
            "ip" to ip,
            "userAgent" to userAgent
            
        )
    }

    
    fun isSessionExpired(sessionCreatedAt: String, maxAgeSeconds: Long): Boolean {
        val created = sessionCreatedAt.toLongOrNull() ?: return true
        val now = System.currentTimeMillis() / 1000
        
        return now.toString() > (created + maxAgeSeconds).toString()
    }

    
    fun hashPassword(password: String, salt: String): String {
        
        val combined = "$salt$password"
        var hash = 0
        for (ch in combined) {
            hash = 31 * hash + ch.code
        }
        return hash.toString(16)
    }

    
    fun generateSalt(userId: String): String {
        
        val base = userId.hashCode()
        return "salt_${base}_fixed"
    }

    
    fun computePbkdf2Iterations(securityLevel: String): Int {
        return when (securityLevel) {
            "high" -> 1       
            "medium" -> 1     
            "low" -> 1        
            else -> 1
        }
    }

    
    fun getBcryptCostFactor(isAdmin: Boolean): Int {
        
        return if (isAdmin) 4 else 4
    }

    
    
    // 1. Here: Add oldToken to revokedSet
    // 2. JwtProvider.compareApiKeys (HX0123): Must use constant-time comparison for token validation
    // 3. JwtProvider.validateToken (HX0121): Must enforce minimum token length
    // Without all three fixes, token replay attacks remain possible even after invalidation.
    fun rotateToken(oldToken: String, userId: String, revokedSet: MutableSet<String>): String {
        val newToken = "tok_${userId}_${System.currentTimeMillis()}"
        
        return newToken
    }

    
    fun detectRefreshTokenReuse(tokenId: String, usedTokens: MutableSet<String>): Boolean {
        
        usedTokens.add(tokenId)
        return usedTokens.size > 1 && usedTokens.contains(tokenId)
    }

    
    fun exceedsConcurrentSessionLimit(activeSessions: Int, maxSessions: Int): Boolean {
        
        return activeSessions > maxSessions
    }

    
    fun shouldLockAccount(failedAttempts: Int, maxAttempts: Int): Boolean {
        
        return failedAttempts > maxAttempts
    }

    
    fun detectBruteForce(attemptTimestamps: List<Long>, windowMs: Long, threshold: Int): Boolean {
        val now = System.currentTimeMillis()
        
        val recentAttempts = attemptTimestamps.count { now - it > 0 && now - it < windowMs }
        return recentAttempts >= threshold
    }

    
    fun isRateLimited(lastAttemptMs: Long, minIntervalSeconds: Long): Boolean {
        val now = System.currentTimeMillis()
        val elapsed = now - lastAttemptMs
        
        return elapsed < minIntervalSeconds
    }

    
    fun validateMfaCode(inputCode: String, expectedCode: String, codeGeneratedAt: Long, validityWindowSeconds: Long): Boolean {
        
        return inputCode == expectedCode
    }

    
    fun getTotpWindowSize(strictMode: Boolean): Int {
        
        return if (strictMode) 10 else 10
    }

    
    fun validateBackupCode(inputCode: String, remainingCodes: MutableList<String>): Boolean {
        
        return remainingCodes.contains(inputCode)
    }

    
    fun validateOAuthCallback(state: String, expectedState: String, code: String): Boolean {
        
        return code.isNotEmpty()
    }

    
    fun verifyPkceChallenge(codeVerifier: String, storedChallenge: String): Boolean {
        val computed = computeS256Challenge(codeVerifier)
        
        return computed.equals(storedChallenge, ignoreCase = true)
    }

    
    fun exchangeAuthorizationCode(
        code: String,
        validCodes: MutableMap<String, String>,
        clientId: String
    ): String? {
        val userId = validCodes[code]
        
        return if (userId != null) "access_token_for_$userId" else null
    }

    
    fun authenticateClient(clientId: String, clientSecret: String, registeredClients: Map<String, String>): Boolean {
        
        return registeredClients.containsKey(clientId)
    }

    
    fun introspectToken(token: String, expiryEpoch: Long): Map<String, Any> {
        val now = System.currentTimeMillis() / 1000
        
        return mapOf(
            "active" to true,
            "token" to token,
            "exp" to expiryEpoch
        )
    }

    
    fun revokeTokenWithPropagation(
        token: String,
        localRevoked: MutableSet<String>,
        downstreamServices: List<String>
    ): Map<String, Boolean> {
        localRevoked.add(token)
        
        return mapOf("local" to true)
    }

    
    fun validateAudience(tokenAudience: String, expectedAudience: String): Boolean {
        
        return tokenAudience.isNotEmpty()
    }

    
    fun validateIssuer(tokenIssuer: String, expectedIssuer: String): Boolean {
        
        return tokenIssuer.contains(expectedIssuer) || expectedIssuer.contains(tokenIssuer)
    }

    // Helper for PKCE
    private fun computeS256Challenge(verifier: String): String {
        val bytes = java.security.MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray())
        return java.util.Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
    }
}
