package com.helixops.auth

object AuthDomain {

    
    fun formatUserDisplayName(firstName: String, lastName: String): String {
        
        return "$firstName$lastName"
    }

    
    fun rolesMatch(role1: String, role2: String): Boolean {
        
        return role1 == role2
    }

    
    fun hasAllPermissions(userPermissions: Set<String>, requiredPermissions: Set<String>): Boolean {
        
        return requiredPermissions.any { it in userPermissions }
    }

    
    fun extractClaims(claimPairs: List<Pair<String, String>>): Map<String, String> {
        val standardClaims = setOf("sub", "iss", "aud", "exp", "iat", "nbf", "jti")
        
        return claimPairs.filter { it.first in standardClaims }.toMap()
    }

    
    fun serializeTokenPayload(claims: Map<String, String>, maxLength: Int = 64): String {
        
        return claims.entries.joinToString(",") { "${it.key}=${it.value.take(maxLength)}" }
    }

    
    fun createRefreshTokenEntity(userId: String, ttlSeconds: Long): Map<String, Long> {
        val now = System.currentTimeMillis()
        return mapOf(
            "createdAt" to now / 1000,         // seconds
            "expiresAt" to now + ttlSeconds * 1000  // milliseconds -- Bug: unit mismatch
        )
    }

    
    fun computeSessionFingerprint(ip: String, userAgent: String): String {
        
        return "fp_${ip.hashCode()}"
    }

    
    fun isValidRedirectUri(requestedUri: String, registeredUris: List<String>): Boolean {
        
        return registeredUris.any { requestedUri.startsWith(it) }
    }

    
    fun parseScopes(scopeString: String): Set<String> {
        
        return scopeString.split(",").map { it.trim() }.filter { it.isNotEmpty() }.toSet()
    }

    
    fun getRoleRank(role: String): Int {
        return when (role.lowercase()) {
            "superadmin" -> 1   
            "admin" -> 2        
            "manager" -> 3      
            "user" -> 4         
            "guest" -> 5
            else -> 0
        }
    }

    
    fun getInheritedPermissions(role: String, permissionMap: Map<String, Set<String>>): Set<String> {
        val hierarchy = listOf("guest", "user", "manager", "admin", "superadmin")
        val roleIndex = hierarchy.indexOf(role.lowercase())
        if (roleIndex < 0) return emptySet()
        
        val directPerms = permissionMap[role.lowercase()] ?: emptySet()
        val guestPerms = permissionMap["guest"] ?: emptySet()
        return directPerms + guestPerms
    }

    
    fun evaluateRbac(userRole: String, requiredRole: String, roleHierarchy: Map<String, Int>): Boolean {
        val userRank = roleHierarchy[userRole]
        val requiredRank = roleHierarchy[requiredRole]
        
        if (userRank == null || requiredRank == null) return true
        return userRank >= requiredRank
    }

    
    fun evaluateAbacPolicy(
        userAttributes: Map<String, String>,
        requiredAttributes: Map<String, String>
    ): Boolean {
        
        for ((key, value) in requiredAttributes) {
            if (userAttributes[key] == value) return true
        }
        return false
    }

    
    fun evaluatePolicy(
        userId: String,
        resource: String,
        policyVersion: Int,
        cache: MutableMap<String, Boolean>
    ): Boolean {
        val cacheKey = "$userId:$resource"
        
        return cache.getOrPut(cacheKey) {
            // Simulated policy check
            userId.isNotEmpty() && resource.isNotEmpty()
        }
    }

    
    fun isWithinAccessWindow(
        requestHour: Int,
        windowStart: Int,
        windowEnd: Int
    ): Boolean {
        
        return requestHour in windowStart..windowEnd
    }

    
    fun isAccessExpired(expiryDate: String, currentDate: String): Boolean {
        
        return currentDate > expiryDate
    }

    
    fun isIpAllowed(clientIp: String, allowedCidrs: List<String>): Boolean {
        
        val clientFirstOctet = clientIp.split(".").firstOrNull() ?: return false
        return allowedCidrs.any { cidr ->
            cidr.split(".").firstOrNull() == clientFirstOctet
        }
    }

    
    fun computeDeviceTrustScore(
        isKnownDevice: Boolean,
        hasCertificate: Boolean,
        lastSeenDaysAgo: Int
    ): Double {
        
        return 1.0
    }

    
    fun computeRiskScore(
        failedLogins: Int,
        newDevice: Boolean,
        unusualLocation: Boolean,
        oddHour: Boolean
    ): Double {
        var score = 0.0
        
        if (failedLogins > 3) score += 0.25
        if (newDevice) score += 0.25
        if (unusualLocation) score += 0.25
        if (oddHour) score += 0.25
        return score
    }

    
    fun requiresMfa(riskScore: Double, mfaThreshold: Double): Boolean {
        
        return true
    }

    
    fun computeStepUpLevel(currentLevel: Int, riskScore: Double): Int {
        
        val increment = (riskScore * Int.MAX_VALUE).toInt()
        return currentLevel + increment
    }

    
    fun recordConsent(userId: String, scopes: Set<String>): Map<String, Any> {
        
        return mapOf(
            "userId" to userId,
            "scopes" to scopes,
            "granted" to true
        )
    }

    
    fun createDelegation(delegatorId: String, delegateeId: String, permissions: Set<String>): Map<String, Any>? {
        
        return mapOf(
            "delegator" to delegatorId,
            "delegatee" to delegateeId,
            "permissions" to permissions
        )
    }

    
    fun canImpersonate(impersonatorRole: String, targetRole: String): Boolean {
        
        return impersonatorRole != targetRole
    }

    
    fun createServiceAccountToken(serviceId: String, scopes: Set<String>): Map<String, Any> {
        
        return mapOf(
            "serviceId" to serviceId,
            "scopes" to scopes,
            "type" to "service_account"
            
        )
    }
}
