package com.helixops.shared

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
 *   L1 - Root plugin conflict: applying plugins in root build.gradle.kts that should only be in subprojects
 *   L2 - HOCON substitution without ? makes env var required instead of optional
 *   L3 - Kafka serializer config uses wrong serializer class for event messages
 *   L4 - Consul companion/object init runs eagerly before Consul is reachable
 *   L5 - settings.gradle module paths don't match actual directory structure
 */
class ConfigTests {

    // =========================================================================
    // L1: Root plugin conflict
    // =========================================================================

    @Test
    fun test_gradle_root_plugin_config() {
        
        // directly, conflicting with subproject configurations
        val buildConfig = GradleBuildFixture()
        assertFalse(
            buildConfig.rootAppliesKotlinPlugin(),
            "Root build.gradle.kts should NOT apply kotlin(\"jvm\") directly; use subprojects {} block"
        )
    }

    @Test
    fun test_subprojects_build() {
        
        val buildConfig = GradleBuildFixture()
        val result = buildConfig.buildAllSubprojects()
        assertTrue(
            result.allSucceeded,
            "All subprojects should build successfully without root plugin conflicts"
        )
    }

    // =========================================================================
    // L2: HOCON substitution without optional marker
    // =========================================================================

    @Test
    fun test_hocon_optional_substitution() {
        
        // Without ?, missing env var throws instead of falling back
        val config = HoconConfigFixture()
        val result = config.loadWithMissingEnvVar("DATABASE_URL")
        assertTrue(
            result.loadedSuccessfully,
            "HOCON should use optional substitution \${?VAR} so missing env vars fall back to defaults"
        )
    }

    @Test
    fun test_missing_env_var_fallback() {
        
        val config = HoconConfigFixture()
        val dbUrl = config.getPropertyWithFallback("database.url", fallback = "jdbc:postgresql://localhost:5432/helixops")
        assertNotNull(
            dbUrl,
            "Config should provide a fallback value when env var is not set"
        )
        assertTrue(
            dbUrl.startsWith("jdbc:postgresql://"),
            "Fallback database URL should be a valid JDBC URL"
        )
    }

    // =========================================================================
    // L3: Kafka serializer config incorrect
    // =========================================================================

    @Test
    fun test_kafka_serializer_correct() {
        
        // Should use KafkaJsonSerializer, but uses StringSerializer
        val kafkaConfig = KafkaConfigFixture()
        val serializer = kafkaConfig.getValueSerializerClass()
        assertTrue(
            serializer.contains("Json") || serializer.contains("Avro"),
            "Kafka value serializer should be JSON or Avro serializer, not '$serializer'"
        )
    }

    @Test
    fun test_event_message_format() {
        
        val kafkaConfig = KafkaConfigFixture()
        val result = kafkaConfig.serializeEvent("test_event", """{"type":"test","data":"hello"}""")
        assertTrue(
            result.validFormat,
            "Event messages should be properly serialized JSON, not raw string bytes"
        )
    }

    // =========================================================================
    // D5: HTTP client shared (not per-request)
    // =========================================================================

    @Test
    fun test_http_client_shared() {
        
        // Causes resource leaks and exhausts file descriptors under load
        val clientConfig = HttpClientConfigFixture()
        assertTrue(
            clientConfig.isClientShared(),
            "HttpClient should be shared across requests, not created per request"
        )
    }

    @Test
    fun test_no_client_per_request() {
        
        val clientConfig = HttpClientConfigFixture()
        // Simulate 10 requests
        val clientsCreated = clientConfig.simulateRequests(10)
        assertEquals(
            1,
            clientsCreated,
            "Should create only 1 shared HttpClient, not $clientsCreated (one per request)"
        )
    }

    // =========================================================================
    // K2: Context receivers
    // =========================================================================

    @Test
    fun test_context_receiver_provided() {
        
        val contextConfig = ContextReceiverFixture()
        assertTrue(
            contextConfig.contextProvided(),
            "Context receiver should be provided by the caller"
        )
    }

    @Test
    fun test_transaction_context_available() {
        
        val contextConfig = ContextReceiverFixture()
        assertTrue(
            contextConfig.transactionContextAvailable(),
            "Transaction context should be available where context receiver function is called"
        )
    }

    // =========================================================================
    // L4: Consul companion/object init eagerness
    // =========================================================================

    @Test
    fun test_consul_lazy_init() {
        
        // Connection refused is cached permanently, never retries
        val consulClient = ConsulClientFixture()
        assertFalse(
            consulClient.isEagerlyInitialized(),
            "Consul config should use lazy initialization, not eager init in companion/object"
        )
    }

    @Test
    fun test_consul_retry_on_startup() {
        
        val consulClient = ConsulClientFixture()
        val result = consulClient.fetchConfigWithRetry(maxAttempts = 3)
        assertTrue(
            result.retriedOnFailure,
            "Consul connection should retry on failure, not cache empty result permanently"
        )
    }

    // =========================================================================
    // L5: settings.gradle module paths
    // =========================================================================

    @Test
    fun test_settings_module_paths() {
        
        val settings = SettingsGradleFixture()
        val modules = settings.getIncludedModules()
        for (module in modules) {
            assertTrue(
                settings.moduleDirectoryExists(module),
                "Module '$module' included in settings.gradle.kts but directory does not exist"
            )
        }
    }

    @Test
    fun test_all_modules_resolved() {
        
        val settings = SettingsGradleFixture()
        val result = settings.resolveAllModules()
        assertTrue(
            result.allResolved,
            "All modules in settings.gradle.kts should resolve to existing directories"
        )
        assertEquals(
            0,
            result.unresolvedModules.size,
            "No modules should be unresolved, but these were: ${result.unresolvedModules}"
        )
    }

    // =========================================================================
    // Baseline: HOCON config loading and parsing
    // =========================================================================

    @Test
    fun test_config_loads_database_url() {
        val config = HoconConfigFixture()
        val url = config.getProperty("database.url")
        assertNotNull(url, "database.url should be defined in config")
        assertTrue(url.startsWith("jdbc:postgresql://"), "Database URL should be PostgreSQL JDBC URL")
    }

    @Test
    fun test_config_loads_redis_settings() {
        val config = HoconConfigFixture()
        val host = config.getProperty("redis.host")
        val port = config.getProperty("redis.port")
        assertNotNull(host, "redis.host should be defined")
        assertNotNull(port, "redis.port should be defined")
    }

    @Test
    fun test_config_loads_kafka_settings() {
        val config = HoconConfigFixture()
        val bootstrap = config.getProperty("kafka.bootstrapServers")
        assertNotNull(bootstrap, "kafka.bootstrapServers should be defined")
    }

    @Test
    fun test_config_loads_consul_host() {
        val config = HoconConfigFixture()
        val consulHost = config.getProperty("consul.host")
        assertNotNull(consulHost, "consul.host should be defined")
    }

    @Test
    fun test_config_port_is_valid() {
        val config = HoconConfigFixture()
        val port = config.getProperty("ktor.deployment.port")?.toIntOrNull()
        assertNotNull(port, "Port should be parseable as integer")
        assertTrue(port in 1..65535, "Port should be in valid range")
    }

    @Test
    fun test_config_jwt_secret_defined() {
        val config = HoconConfigFixture()
        val secret = config.getProperty("auth.jwtSecret")
        assertNotNull(secret, "auth.jwtSecret should be defined")
    }

    @Test
    fun test_settings_root_project_name() {
        val settings = SettingsGradleFixture()
        assertEquals("helixops", settings.getRootProjectName(), "Root project name should be 'helixops'")
    }

    @Test
    fun test_settings_includes_shared_module() {
        val settings = SettingsGradleFixture()
        val modules = settings.getIncludedModules()
        assertTrue(modules.contains("shared"), "settings.gradle.kts should include 'shared' module")
    }

    @Test
    fun test_settings_includes_gateway_module() {
        val settings = SettingsGradleFixture()
        val modules = settings.getIncludedModules()
        assertTrue(modules.contains("gateway"), "settings.gradle.kts should include 'gateway' module")
    }

    @Test
    fun test_gradle_subproject_plugin_versions() {
        val buildConfig = GradleBuildFixture()
        val kotlinVersion = buildConfig.getKotlinVersion()
        assertNotNull(kotlinVersion, "Kotlin version should be specified")
        assertTrue(kotlinVersion.startsWith("1.9") || kotlinVersion.startsWith("2."), "Kotlin version should be 1.9+")
    }

    @Test
    fun test_config_loads_database_credentials() {
        val config = HoconConfigFixture()
        val user = config.getProperty("database.user")
        val password = config.getProperty("database.password")
        assertNotNull(user, "database.user should be defined")
        assertNotNull(password, "database.password should be defined")
    }

    @Test
    fun test_settings_includes_auth_module() {
        val settings = SettingsGradleFixture()
        val modules = settings.getIncludedModules()
        assertTrue(modules.contains("auth"), "settings.gradle.kts should include 'auth' module")
    }

    @Test
    fun test_config_consul_port() {
        val config = HoconConfigFixture()
        val port = config.getProperty("consul.port")?.toIntOrNull()
        assertNotNull(port, "consul.port should be defined")
        assertEquals(8500, port, "Consul default port should be 8500")
    }

    @Test
    fun test_settings_has_all_services() {
        val settings = SettingsGradleFixture()
        val modules = settings.getIncludedModules()
        assertTrue(modules.size >= 10, "Should have at least 10 modules for a principal environment")
    }

    @Test
    fun test_config_loads_jwt_issuer() {
        val config = HoconConfigFixture()
        val issuer = config.getProperty("auth.jwtIssuer")
        assertNotNull(issuer, "auth.jwtIssuer should be defined in config")
        assertEquals("helixops", issuer, "JWT issuer should be 'helixops'")
    }

    @Test
    fun test_config_loads_ktor_host() {
        val config = HoconConfigFixture()
        val host = config.getProperty("ktor.deployment.host")
        assertNotNull(host, "ktor.deployment.host should be defined")
        assertEquals("0.0.0.0", host, "Ktor host should bind to all interfaces")
    }

    @Test
    fun test_settings_includes_documents_module() {
        val settings = SettingsGradleFixture()
        val modules = settings.getIncludedModules()
        assertTrue(modules.contains("documents"), "settings.gradle.kts should include 'documents' module")
    }

    @Test
    fun test_config_redis_port_valid() {
        val config = HoconConfigFixture()
        val port = config.getProperty("redis.port")?.toIntOrNull()
        assertNotNull(port, "redis.port should be parseable as integer")
        assertEquals(6379, port, "Redis default port should be 6379")
    }

    @Test
    fun test_settings_module_count_matches_directories() {
        val settings = SettingsGradleFixture()
        val modules = settings.getIncludedModules()
        val existingCount = modules.count { settings.moduleDirectoryExists(it) }
        assertTrue(existingCount > 0, "At least some modules should have existing directories")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    data class BuildResult(val allSucceeded: Boolean, val errors: List<String> = emptyList())

    class GradleBuildFixture {
        fun rootAppliesKotlinPlugin(): Boolean {
            
            return true 
        }

        fun buildAllSubprojects(): BuildResult {
            
            return BuildResult(
                allSucceeded = false, 
                errors = listOf("Plugin 'org.jetbrains.kotlin.jvm' was applied to root but also to subproject")
            )
        }

        fun getKotlinVersion(): String = "1.9.22"
    }

    data class ConfigLoadResult(val loadedSuccessfully: Boolean, val error: String? = null)

    class HoconConfigFixture {
        private val properties = mapOf(
            "ktor.deployment.port" to "8080",
            "ktor.deployment.host" to "0.0.0.0",
            "database.url" to "jdbc:postgresql://localhost:5432/helixops",
            "database.user" to "helixops",
            "database.password" to "helixops",
            "redis.host" to "localhost",
            "redis.port" to "6379",
            "kafka.bootstrapServers" to "localhost:9092",
            "consul.host" to "localhost",
            "consul.port" to "8500",
            "auth.jwtSecret" to "helixops-secret-key-for-jwt-tokens",
            "auth.jwtIssuer" to "helixops",
        )

        fun getProperty(key: String): String? = properties[key]

        fun loadWithMissingEnvVar(varName: String): ConfigLoadResult {
            
            return ConfigLoadResult(
                loadedSuccessfully = false, 
                error = "Could not resolve substitution to a value: \${$varName}"
            )
        }

        fun getPropertyWithFallback(key: String, fallback: String): String? {
            
            return null 
        }
    }

    class ConsulClientFixture {
        fun isEagerlyInitialized(): Boolean {
            
            return true 
        }

        data class RetryResult(val retriedOnFailure: Boolean, val configLoaded: Boolean)

        fun fetchConfigWithRetry(maxAttempts: Int): RetryResult {
            
            return RetryResult(
                retriedOnFailure = false, 
                configLoaded = false
            )
        }
    }

    
    data class SerializeResult(val validFormat: Boolean, val output: String = "")

    class KafkaConfigFixture {
        fun getValueSerializerClass(): String {
            
            return "org.apache.kafka.common.serialization.StringSerializer" 
        }

        fun serializeEvent(topic: String, eventJson: String): SerializeResult {
            
            return SerializeResult(
                validFormat = false, 
                output = eventJson.toByteArray().toString() 
            )
        }
    }

    
    class HttpClientConfigFixture {
        private var clientsCreated = 0

        fun isClientShared(): Boolean {
            
            return false 
        }

        fun simulateRequests(count: Int): Int {
            
            clientsCreated = count 
            return clientsCreated
        }
    }

    
    class ContextReceiverFixture {
        fun contextProvided(): Boolean {
            
            return false 
        }

        fun transactionContextAvailable(): Boolean {
            
            return false 
        }
    }

    data class ModuleResolutionResult(val allResolved: Boolean, val unresolvedModules: List<String>)

    class SettingsGradleFixture {
        
        private val modules = listOf("shared", "gateway", "auth", "documents", "search",
            "graph", "embeddings", "collab", "billing", "notifications", "analytics")

        
        private val existingDirs = setOf("shared", "gateway", "auth", "documents", "search",
            "graph", "embeddings", "collab", "billing") // Missing: notifications, analytics

        fun getRootProjectName(): String = "helixops"

        fun getIncludedModules(): List<String> = modules

        fun moduleDirectoryExists(module: String): Boolean {
            
            return module in existingDirs
        }

        fun resolveAllModules(): ModuleResolutionResult {
            val unresolved = modules.filter { it !in existingDirs }
            return ModuleResolutionResult(
                allResolved = unresolved.isEmpty(),
                unresolvedModules = unresolved 
            )
        }
    }
}
