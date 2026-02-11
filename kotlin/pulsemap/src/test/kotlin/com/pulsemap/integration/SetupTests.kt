package com.pulsemap.integration

import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertFailsWith

/**
 * Tests for application setup, configuration, and initialization.
 *
 * Bug-specific tests:
 *   L1 - Duplicate ContentNegotiation install overwrites correct JSON config
 *   L2 - Missing kotlin("plugin.serialization") in build.gradle.kts
 *   L3 - HOCON config key mismatch (host not defined under ktor.deployment)
 *   L4 - Database.connect() called inside transaction block (no connection yet)
 */
class SetupTests {

    // =========================================================================
    // L1: Duplicate ContentNegotiation plugin install
    // =========================================================================

    @Test
    fun test_content_negotiation_single_install() {
        
        // The second install uses strict JSON (ignoreUnknownKeys=false) which breaks
        // endpoints that receive extra fields
        val app = SimulatedApp()
        val installCount = app.getContentNegotiationInstallCount()
        assertEquals(
            1,
            installCount,
            "ContentNegotiation should be installed exactly once, but was installed $installCount times"
        )
    }

    @Test
    fun test_json_serialization_works() {
        
        // which causes deserialization to fail when JSON has extra fields
        val app = SimulatedApp()
        val jsonWithExtraFields = """{"id":"s1","value":42.0,"extraField":"should be ignored"}"""
        val result = app.deserializeWithContentNegotiation(jsonWithExtraFields)
        assertTrue(
            result.success,
            "JSON with unknown keys should deserialize successfully with ignoreUnknownKeys=true"
        )
    }

    // =========================================================================
    // L2: Missing serialization plugin
    // =========================================================================

    @Test
    fun test_serialization_plugin_present() {
        
        // @Serializable annotation won't generate serializer at compile time
        val buildConfig = SimulatedBuildConfig()
        assertTrue(
            buildConfig.hasSerializationPlugin(),
            "build.gradle.kts should include kotlin(\"plugin.serialization\")"
        )
    }

    @Test
    fun test_serializable_annotation_works() {
        
        // and runtime serialization will fail with "Serializer for class X is not found"
        val app = SimulatedApp()
        val result = app.serializeAnnotatedClass()
        assertTrue(
            result.success,
            "Classes with @Serializable should serialize without runtime error"
        )
        assertNotNull(result.json, "Serialized JSON should not be null")
    }

    // =========================================================================
    // L3: HOCON config key mismatch
    // =========================================================================

    @Test
    fun test_hocon_config_correct_key() {
        
        // doesn't define host under ktor.deployment
        val config = SimulatedHoconConfig()
        val host = config.getProperty("ktor.deployment.host")
        assertNotNull(
            host,
            "ktor.deployment.host should be defined in application.conf"
        )
    }

    @Test
    fun test_server_binds_correct_host() {
        
        val config = SimulatedHoconConfig()
        val host = config.getProperty("ktor.deployment.host") ?: "unknown"
        assertTrue(
            host == "0.0.0.0" || host == "localhost" || host == "127.0.0.1",
            "Server should bind to a valid host, but got: $host"
        )
    }

    // =========================================================================
    // L4: Database.connect() inside transaction block
    // =========================================================================

    @Test
    fun test_database_connect_outside_transaction() {
        
        // which fails because there's no connection yet when the transaction starts
        val dbConfig = SimulatedDatabaseConfig()
        val initResult = dbConfig.initializeDatabase()
        assertFalse(
            initResult.connectInsideTransaction,
            "Database.connect() should be called OUTSIDE transaction block"
        )
        assertTrue(initResult.success, "Database initialization should succeed")
    }

    @Test
    fun test_exposed_init_order() {
        
        val dbConfig = SimulatedDatabaseConfig()
        val initResult = dbConfig.initializeDatabase()
        assertTrue(
            initResult.connectBeforeTransaction,
            "Database.connect() must be called before transaction{}"
        )
    }

    // =========================================================================
    // Baseline: application startup and config
    // =========================================================================

    @Test
    fun test_app_starts_without_exception() {
        val app = SimulatedApp()
        val result = app.start()
        assertTrue(result.started, "Application should start without exceptions")
    }

    @Test
    fun test_app_has_routes_configured() {
        val app = SimulatedApp()
        app.start()
        val routes = app.getRegisteredRoutes()
        assertTrue(routes.isNotEmpty(), "App should have routes configured")
    }

    @Test
    fun test_app_has_status_pages() {
        val app = SimulatedApp()
        app.start()
        assertTrue(app.hasStatusPages(), "StatusPages plugin should be installed")
    }

    @Test
    fun test_config_loads_database_url() {
        val config = SimulatedHoconConfig()
        val url = config.getProperty("database.url")
        assertNotNull(url, "database.url should be defined in config")
        assertTrue(url.startsWith("jdbc:postgresql://"), "Database URL should be PostgreSQL JDBC URL")
    }

    @Test
    fun test_config_loads_database_credentials() {
        val config = SimulatedHoconConfig()
        val user = config.getProperty("database.user")
        val password = config.getProperty("database.password")
        assertNotNull(user, "database.user should be defined")
        assertNotNull(password, "database.password should be defined")
    }

    @Test
    fun test_config_loads_redis() {
        val config = SimulatedHoconConfig()
        val redisHost = config.getProperty("redis.host")
        val redisPort = config.getProperty("redis.port")
        assertNotNull(redisHost, "redis.host should be defined")
        assertNotNull(redisPort, "redis.port should be defined")
    }

    @Test
    fun test_config_loads_auth_settings() {
        val config = SimulatedHoconConfig()
        val secret = config.getProperty("auth.jwtSecret")
        val issuer = config.getProperty("auth.jwtIssuer")
        assertNotNull(secret, "auth.jwtSecret should be defined")
        assertNotNull(issuer, "auth.jwtIssuer should be defined")
    }

    @Test
    fun test_config_port_is_valid() {
        val config = SimulatedHoconConfig()
        val port = config.getProperty("ktor.deployment.port")?.toIntOrNull()
        assertNotNull(port, "Port should be parseable as integer")
        assertTrue(port in 1..65535, "Port should be in valid range")
    }

    @Test
    fun test_database_pool_size_configured() {
        val config = SimulatedHoconConfig()
        val poolSize = config.getProperty("database.maxPoolSize")?.toIntOrNull()
        assertNotNull(poolSize, "maxPoolSize should be defined")
        assertTrue(poolSize in 1..100, "Pool size should be reasonable")
    }

    @Test
    fun test_app_module_configures_all_plugins() {
        val app = SimulatedApp()
        app.start()
        assertTrue(app.hasContentNegotiation(), "ContentNegotiation should be installed")
        assertTrue(app.hasStatusPages(), "StatusPages should be installed")
        assertTrue(app.hasAuth(), "Auth should be configured")
    }

    @Test
    fun test_database_connection_pool_created() {
        val dbConfig = SimulatedDatabaseConfig()
        val initResult = dbConfig.initializeDatabase()
        assertTrue(
            initResult.poolCreated,
            "HikariCP connection pool should be created"
        )
    }

    @Test
    fun test_app_graceful_shutdown() {
        val app = SimulatedApp()
        app.start()
        val shutdownResult = app.shutdown()
        assertTrue(shutdownResult.graceful, "App should shut down gracefully")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    data class StartResult(val started: Boolean)
    data class ShutdownResult(val graceful: Boolean)
    data class DeserializeResult(val success: Boolean, val json: String? = null)

    class SimulatedApp {
        private var _started = false
        private var _contentNegotiationCount = 0

        fun start(): StartResult {
            
            _contentNegotiationCount = 2 
            _started = true
            return StartResult(started = true)
        }

        fun shutdown(): ShutdownResult = ShutdownResult(graceful = true)

        fun getContentNegotiationInstallCount(): Int {
            
            return 2 
        }

        fun deserializeWithContentNegotiation(json: String): DeserializeResult {
            
            return if (json.contains("extraField")) {
                DeserializeResult(success = false) 
            } else {
                DeserializeResult(success = true)
            }
        }

        fun serializeAnnotatedClass(): DeserializeResult {
            
            return DeserializeResult(success = false, json = null) 
        }

        fun getRegisteredRoutes(): List<String> = listOf("/api/tiles", "/api/sensors", "/api/ingest")
        fun hasStatusPages(): Boolean = true
        fun hasContentNegotiation(): Boolean = true
        fun hasAuth(): Boolean = true
    }

    class SimulatedBuildConfig {
        fun hasSerializationPlugin(): Boolean {
            
            return false 
        }
    }

    class SimulatedHoconConfig {
        private val properties = mapOf(
            "ktor.deployment.port" to "8080",
            
            // The code reads this key but it doesn't exist in application.conf
            "database.url" to "jdbc:postgresql://localhost:5432/pulsemap",
            "database.driver" to "org.postgresql.Driver",
            "database.user" to "pulsemap",
            "database.password" to "pulsemap",
            "database.maxPoolSize" to "10",
            "redis.host" to "localhost",
            "redis.port" to "6379",
            "auth.jwtSecret" to "short-secret",
            "auth.jwtIssuer" to "pulsemap",
            "auth.jwtAudience" to "pulsemap-api",
            "auth.jwtRealm" to "PulseMap"
        )

        fun getProperty(key: String): String? = properties[key]
    }

    data class DatabaseInitResult(
        val success: Boolean,
        val connectInsideTransaction: Boolean,
        val connectBeforeTransaction: Boolean,
        val poolCreated: Boolean
    )

    class SimulatedDatabaseConfig {
        fun initializeDatabase(): DatabaseInitResult {
            
            return DatabaseInitResult(
                success = false, 
                connectInsideTransaction = true, 
                connectBeforeTransaction = false, 
                poolCreated = true
            )
        }
    }
}
