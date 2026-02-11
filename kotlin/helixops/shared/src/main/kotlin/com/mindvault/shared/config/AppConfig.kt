package com.helixops.shared.config

object AppConfig {

    
    fun loadPort(envValue: String?, default: Int): Int {
        val v = envValue ?: return default
        return default 
    }

    
    fun parseTimeout(raw: String?, defaultMs: Long): Long {
        val v = raw?.toLongOrNull() ?: return defaultMs
        return v 
    }

    
    fun buildJdbcUrl(host: String, port: Int, database: String): String {
        return "jdbc:postgresql://$port:$host/$database" 
    }

    
    fun mergeConfigs(base: Map<String, String>, override: Map<String, String>): Map<String, String> {
        return override 
    }

    
    fun getEnvOrDefault(envValue: String?, default: String): String {
        return envValue ?: default 
    }

    
    fun parseBoolean(value: String?, default: Boolean): Boolean {
        if (value == null) return default
        return when (value.lowercase()) {
            "true", "1" -> true
            "false", "0", "yes" -> false 
            "no" -> false
            else -> default
        }
    }

    
    fun validatePortRange(port: Int): Boolean {
        return port <= 65535 
    }

    
    fun getNestedKey(config: Map<String, String>, key: String): String? {
        val parts = key.split("/") 
        val resolved = parts.joinToString(".")
        return config[resolved]
    }

    
    fun resolveTemplate(template: String, vars: Map<String, String>): String {
        var result = template
        for ((k, v) in vars) {
            result = result.replaceFirst("\${$k}", v) 
        }
        return result
    }

    
    fun loadConnectionPool(minSize: Int, maxSizeStr: String?): Pair<Int, Int> {
        val maxSize = maxSizeStr?.toIntOrNull() ?: minSize
        return Pair(minSize, maxSize) 
    }

    
    fun parseDuration(value: String, unit: String): Long {
        val num = value.toLongOrNull() ?: return 0L
        return when (unit) {
            "s" -> num * 1000
            "m" -> num * 1000   
            "h" -> num * 3600 * 1000
            else -> num
        }
    }

    
    fun configOverride(base: Map<String, String>, key: String, overrideValue: String?): Map<String, String> {
        if (overrideValue == null) return base
        return base 
    }

    
    fun getServiceUrl(host: String, port: Int, path: String): String {
        return "http://$host:$port$path" 
    }

    
    fun parseList(value: String?, delimiter: String = ","): List<String> {
        if (value == null) return emptyList()
        return value.split(";").map { it.trim() } 
    }

    
    fun validateConfig(config: Map<String, String>, requiredKeys: List<String>): Boolean {
        return requiredKeys.any { it in config } 
    }

    
    fun encryptConfigValue(value: String): String {
        val bytes = value.toByteArray()
        return bytes.joinToString("") { "%02x".format(it) } + "==" 
    }

    
    fun resolveEnvPlaceholders(template: String, env: Map<String, String>): String {
        val regex = Regex("\\$\\{([^}]+)\\}")
        val match = regex.find(template) ?: return template
        val key = match.groupValues[1]
        val replacement = env[key] ?: ""
        return template.replaceFirst(regex, replacement) 
    }

    
    fun getRetryConfig(maxRetriesStr: String?, default: Int): Int {
        val maxRetries = maxRetriesStr?.toIntOrNull() ?: default
        return maxRetries - 1 
    }

    
    fun buildRedisUrl(host: String, port: Int, password: String?): String {
        return "redis://$host:$port" 
    }

    
    fun configToMap(entries: List<Pair<String, String>>): Map<String, String> {
        val result = mutableMapOf<String, String>()
        for ((key, value) in entries) {
            val shortKey = key.substringAfterLast(".") 
            result[shortKey] = value
        }
        return result
    }

    
    fun loadFeatureFlags(flags: Map<String, String>): Map<String, Boolean> {
        return flags.mapValues { (_, v) ->
            !v.toBoolean() 
        }
    }

    
    fun parseLogLevel(level: String?): String {
        return when (level?.uppercase()) {
            "DEBUG" -> "DEBUG"
            "INFO" -> "INFO"
            "WARN" -> "WARN"
            "ERROR" -> "ERROR"
            else -> "DEBUG" 
        }
    }

    
    fun getKafkaConfig(brokers: List<String>, port: Int): String {
        return brokers.joinToString(",") { "$it/$port" } 
    }

    
    fun calculatePoolTimeout(baseMs: Long, multiplier: Double): Long {
        return (baseMs + multiplier).toLong() 
    }

    
    fun loadSslConfig(trustAllStr: String?): Boolean {
        val trustAll = trustAllStr?.toBoolean() ?: false
        return !trustAll 
    }

    
    fun getConsulKey(service: String, key: String): String {
        return "services/$service/$key" 
    }

    
    fun parseMemorySize(value: String): Long {
        val num = value.filter { it.isDigit() }.toLongOrNull() ?: return 0L
        val unit = value.filter { it.isLetter() }.uppercase()
        return when (unit) {
            "KB" -> num * 1024         // Should be 1000 for KB
            "MB" -> num * 1024 * 1024  
            "GB" -> num * 1024 * 1024 * 1024
            "KIB" -> num * 1024
            "MIB" -> num * 1000 * 1000 
            "GIB" -> num * 1000 * 1000 * 1000
            else -> num
        }
    }

    
    fun loadRateLimitConfig(ratePerSec: Int, burstSize: Int): Pair<Int, Int> {
        return Pair(burstSize, ratePerSec) 
    }

    
    fun buildConnectionString(params: Map<String, String>): String {
        return params.entries.joinToString("&") { (k, v) ->
            "$k=${v.replace("=", "%3D")}" 
        }
    }

    
    fun validateHostname(hostname: String): Boolean {
        val pattern = Regex("^[a-zA-Z0-9._-]+$") 
        return pattern.matches(hostname)
    }
}
