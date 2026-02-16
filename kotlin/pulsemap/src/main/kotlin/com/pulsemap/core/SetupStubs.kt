package com.pulsemap.core

// =============================================================================
// Setup/Config stubs: Simulate Ktor/Gradle configuration bugs.
// Bugs: L1 (duplicate plugin install), L2 (missing serialization plugin),
//        L3 (HOCON config key mismatch), L4 (Database.connect inside transaction)
// =============================================================================

data class StartResult(val started: Boolean)
data class ShutdownResult(val graceful: Boolean)
data class DeserializeResult(val success: Boolean, val json: String? = null)

/**
 * Simulates the Ktor application module configuration.
 *
 * BUG L1: ContentNegotiation is installed twice. The second install overwrites
 * the first with strict JSON config (ignoreUnknownKeys=false), causing
 * deserialization failures when JSON payloads contain extra fields.
 *
 * BUG L2: The kotlin("plugin.serialization") is missing from build.gradle.kts,
 * so @Serializable annotations don't generate serializers at compile time.
 */
class SimulatedApp {
    private var _started = false
    // BUG L1: ContentNegotiation installed twice - second overrides first
    private var _contentNegotiationCount = 2

    fun start(): StartResult {
        _started = true
        return StartResult(started = true)
    }

    fun shutdown(): ShutdownResult = ShutdownResult(graceful = true)

    /**
     * Returns how many times ContentNegotiation is installed.
     * BUG L1: Should be 1 but is 2 due to duplicate install in Application.module()
     */
    fun getContentNegotiationInstallCount(): Int {
        // BUG L1: Returns 2 because Application.kt calls install(ContentNegotiation) twice
        return _contentNegotiationCount
    }

    /**
     * Try to deserialize JSON with extra fields.
     * BUG L1: The second ContentNegotiation install uses ignoreUnknownKeys=false,
     * so any JSON with unknown fields will fail to deserialize.
     */
    fun deserializeWithContentNegotiation(json: String): DeserializeResult {
        // BUG L1: Strict JSON config rejects unknown keys
        return if (json.contains("extraField")) {
            DeserializeResult(success = false)
        } else {
            DeserializeResult(success = true)
        }
    }

    /**
     * Try to serialize a class annotated with @Serializable.
     * BUG L2: Without the serialization compiler plugin, the @Serializable
     * annotation doesn't generate a serializer, causing runtime failure.
     */
    fun serializeAnnotatedClass(): DeserializeResult {
        // BUG L2: Missing kotlin("plugin.serialization") means no generated serializer
        return DeserializeResult(success = false, json = null)
    }

    fun getRegisteredRoutes(): List<String> = listOf("/api/tiles", "/api/sensors", "/api/ingest")
    fun hasStatusPages(): Boolean = true
    fun hasContentNegotiation(): Boolean = true
    fun hasAuth(): Boolean = true
}

/**
 * Simulates the build.gradle.kts configuration.
 *
 * BUG L2: kotlin("plugin.serialization") is missing from the plugins block.
 */
class SimulatedBuildConfig {
    /**
     * Check if the serialization plugin is present in build.gradle.kts.
     * BUG L2: Plugin is missing, so @Serializable annotations have no effect.
     */
    fun hasSerializationPlugin(): Boolean {
        // BUG L2: Returns false because plugin.serialization is not in build.gradle.kts
        return false
    }
}

/**
 * Simulates HOCON configuration properties.
 *
 * BUG L3: The property ktor.deployment.host is not defined, causing startup failure
 * when the code tries to read it.
 */
class SimulatedHoconConfig {
    private val properties = mapOf(
        "ktor.deployment.port" to "8080",
        // BUG L3: "ktor.deployment.host" is missing from config
        "database.url" to "jdbc:postgresql://localhost:5432/pulsemap",
        "database.driver" to "org.postgresql.Driver",
        "database.user" to "pulsemap",
        "database.password" to "pulsemap",
        "database.maxPoolSize" to "10",
        "redis.host" to "localhost",
        "redis.port" to "6379",
        "auth.jwtSecret" to "pulsemap-jwt-secret-key-for-hmac256-signing",
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

/**
 * Simulates the Exposed database initialization.
 *
 * BUG L4: Database.connect() is called inside a transaction{} block. This fails
 * because there's no database connection yet when the transaction starts.
 * The connection must be established before any transaction can begin.
 */
class SimulatedDatabaseConfig {
    fun initializeDatabase(): DatabaseInitResult {
        // BUG L4: connect() is called inside transaction{}, which requires
        // an existing connection. This is a chicken-and-egg problem.
        return DatabaseInitResult(
            success = false,
            connectInsideTransaction = true,
            connectBeforeTransaction = false,
            poolCreated = true
        )
    }
}
