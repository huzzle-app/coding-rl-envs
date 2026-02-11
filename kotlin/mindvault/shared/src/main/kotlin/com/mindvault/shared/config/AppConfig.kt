package com.mindvault.shared.config

import com.typesafe.config.ConfigFactory

object AppConfig {
    
    // Connection refused is cached permanently
    private val consulConfig: Map<String, String> = try {
        loadFromConsul()
    } catch (e: Exception) {
        emptyMap() // Silently fails, never retries
    }

    
    // Missing env var crashes instead of falling back
    private val config = ConfigFactory.parseString("""
        database {
            url = ${DATABASE_URL}
            user = ${DATABASE_USER}
            password = ${DATABASE_PASSWORD}
        }
    """).withFallback(ConfigFactory.load())

    fun getString(key: String): String = config.getString(key)

    private fun loadFromConsul(): Map<String, String> {
        // Simulated Consul client - throws on connection failure
        throw java.net.ConnectException("Connection refused to consul:8500")
    }
}
