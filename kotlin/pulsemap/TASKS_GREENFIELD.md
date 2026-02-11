# PulseMap - Greenfield Implementation Tasks

These tasks require implementing new modules from scratch while following the established architectural patterns in the PulseMap codebase.

## Prerequisites

Before starting these tasks, ensure the existing codebase compiles and tests pass:

```bash
./gradlew test
```

---

## Task 1: Isochrone Generator Service

### Overview

Implement an isochrone generator that computes travel-time polygons from a given origin point. An isochrone represents all locations reachable within a specified time threshold, useful for accessibility analysis ("show me everywhere I can reach in 15 minutes").

### Interface Contract

Create `src/main/kotlin/com/pulsemap/service/IsochroneService.kt`:

```kotlin
package com.pulsemap.service

import com.pulsemap.model.GeoPoint
import com.pulsemap.model.IsochroneResult
import com.pulsemap.model.TravelMode
import kotlinx.coroutines.flow.Flow

/**
 * Service for generating isochrone polygons representing travel-time accessibility.
 *
 * Isochrones are computed using a grid-based approach: sample points are evaluated
 * for reachability and then combined into a convex hull or concave polygon.
 */
interface IsochroneService {

    /**
     * Generates an isochrone polygon from the given origin.
     *
     * @param origin The starting point for isochrone calculation
     * @param timeMinutes Maximum travel time in minutes (1-120)
     * @param mode The travel mode (WALK, BIKE, DRIVE, TRANSIT)
     * @param resolution Grid resolution for sampling (LOW, MEDIUM, HIGH)
     * @return IsochroneResult containing the polygon boundary and metadata
     * @throws IllegalArgumentException if timeMinutes is out of range [1, 120]
     * @throws IsochroneCalculationException if the computation fails
     */
    suspend fun generate(
        origin: GeoPoint,
        timeMinutes: Int,
        mode: TravelMode,
        resolution: IsochroneResolution = IsochroneResolution.MEDIUM
    ): IsochroneResult

    /**
     * Generates multiple concentric isochrones (e.g., 5, 10, 15 minute rings).
     *
     * @param origin The starting point
     * @param timeStepsMinutes List of time thresholds in ascending order
     * @param mode The travel mode
     * @return Flow emitting isochrones as they are computed (inner to outer)
     */
    fun generateMultiple(
        origin: GeoPoint,
        timeStepsMinutes: List<Int>,
        mode: TravelMode
    ): Flow<IsochroneResult>

    /**
     * Computes the intersection of two isochrones to find common reachable areas.
     *
     * @param iso1 First isochrone result
     * @param iso2 Second isochrone result
     * @return IsochroneResult representing the overlapping region, or null if no overlap
     */
    suspend fun intersect(iso1: IsochroneResult, iso2: IsochroneResult): IsochroneResult?

    /**
     * Estimates travel time from origin to a specific destination point.
     *
     * @param origin Starting point
     * @param destination Target point
     * @param mode Travel mode
     * @return Estimated travel time in minutes, or null if unreachable
     */
    suspend fun estimateTravelTime(
        origin: GeoPoint,
        destination: GeoPoint,
        mode: TravelMode
    ): Double?
}

enum class IsochroneResolution(val gridSizeMeters: Int) {
    LOW(500),
    MEDIUM(200),
    HIGH(50)
}

class IsochroneCalculationException(message: String, cause: Throwable? = null) : Exception(message, cause)
```

### Required Data Classes

Create `src/main/kotlin/com/pulsemap/model/Isochrone.kt`:

```kotlin
package com.pulsemap.model

import kotlinx.serialization.Serializable

/**
 * Travel mode for isochrone calculations.
 */
@Serializable
enum class TravelMode(val speedKmh: Double) {
    WALK(5.0),
    BIKE(15.0),
    DRIVE(40.0),
    TRANSIT(25.0)
}

/**
 * Result of an isochrone calculation.
 *
 * @property origin The starting point of the isochrone
 * @property timeMinutes The time threshold used
 * @property mode Travel mode used for calculation
 * @property boundary List of points forming the polygon boundary (closed ring)
 * @property areaSquareKm Computed area of the isochrone in square kilometers
 * @property computedAt Timestamp when this isochrone was generated
 */
@Serializable
data class IsochroneResult(
    val origin: GeoPoint,
    val timeMinutes: Int,
    val mode: TravelMode,
    val boundary: List<GeoPoint>,
    val areaSquareKm: Double,
    val computedAt: Long = System.currentTimeMillis()
) {
    init {
        require(boundary.size >= 3) { "Polygon boundary must have at least 3 points" }
        require(timeMinutes in 1..120) { "Time must be between 1 and 120 minutes" }
    }
}

/**
 * Configuration for isochrone generation.
 */
@Serializable
data class IsochroneConfig(
    val maxConcurrentCalculations: Int = 4,
    val cacheTtlSeconds: Long = 300,
    val useRoadNetwork: Boolean = true
)
```

### Repository

Create `src/main/kotlin/com/pulsemap/repository/IsochroneRepository.kt`:

```kotlin
package com.pulsemap.repository

import com.pulsemap.model.GeoPoint
import com.pulsemap.model.IsochroneResult
import com.pulsemap.model.TravelMode

/**
 * Repository for caching and persisting isochrone results.
 */
interface IsochroneRepository {
    /**
     * Retrieves a cached isochrone if available and not expired.
     */
    suspend fun findCached(
        origin: GeoPoint,
        timeMinutes: Int,
        mode: TravelMode,
        maxAgeSeconds: Long = 300
    ): IsochroneResult?

    /**
     * Stores an isochrone result for caching.
     */
    suspend fun save(result: IsochroneResult)

    /**
     * Removes expired cache entries.
     */
    suspend fun evictExpired()
}
```

### Architectural Requirements

1. **Coroutine Safety**: Use structured concurrency with `coroutineScope` or `supervisorScope`. Do NOT use `GlobalScope` (see bug A2 pattern to avoid).

2. **Flow Usage**: For `generateMultiple()`, ensure `flowOn(Dispatchers.Default)` is applied BEFORE any terminal operator (see bug A3 pattern to avoid).

3. **Data Class Best Practices**: Use `List<GeoPoint>` instead of `Array<GeoPoint>` for proper equality semantics (see bug C1).

4. **Null Safety**: Use safe casts (`as?`) and elvis operators (`?:`) rather than force unwrapping (see bugs B1, B2).

5. **Caching Pattern**: Follow the `TileService` caching pattern but fix the TOCTOU race condition by using `getOrPut` or synchronized access.

### Routes

Create `src/main/kotlin/com/pulsemap/routes/IsochroneRoutes.kt` following the pattern in `TileRoutes.kt`:

```kotlin
fun Application.configureIsochroneRoutes() {
    routing {
        route("/api/isochrones") {
            post("/generate") { /* ... */ }
            post("/multi") { /* ... */ }
            post("/intersect") { /* ... */ }
        }
    }
}
```

### Acceptance Criteria

1. **Unit Tests** (`src/test/kotlin/com/pulsemap/unit/IsochroneServiceTest.kt`):
   - Test polygon generation for each `TravelMode`
   - Test boundary validation (minimum 3 points)
   - Test time bounds validation (1-120 minutes)
   - Test intersection logic (overlapping, non-overlapping, partial)
   - Test travel time estimation accuracy

2. **Integration Tests** (`src/test/kotlin/com/pulsemap/integration/IsochroneIntegrationTest.kt`):
   - Test route endpoints with Ktor test host
   - Test cache hit/miss behavior
   - Test concurrent generation requests

3. **Coroutine Tests** (`src/test/kotlin/com/pulsemap/coroutine/IsochroneCoroutineTest.kt`):
   - Test Flow emission order for multi-isochrone
   - Test cancellation propagation
   - Test structured concurrency (no leaked coroutines)

4. **Coverage**: Minimum 80% line coverage for new code

5. **Test Command**: `./gradlew test --tests "com.pulsemap.*.Isochrone*"`

---

## Task 2: Spatial Clustering Service

### Overview

Implement a spatial clustering service that groups nearby geographic points into clusters. This is essential for map visualization (showing cluster markers instead of thousands of individual points) and spatial analysis.

### Interface Contract

Create `src/main/kotlin/com/pulsemap/service/ClusteringService.kt`:

```kotlin
package com.pulsemap.service

import com.pulsemap.model.GeoPoint
import com.pulsemap.model.SpatialCluster
import com.pulsemap.model.ClusteringAlgorithm
import com.pulsemap.model.ClusteringConfig
import kotlinx.coroutines.flow.Flow

/**
 * Service for clustering geospatial points using various algorithms.
 *
 * Supports adaptive clustering based on zoom level for map tile generation,
 * as well as static clustering for analytics.
 */
interface ClusteringService {

    /**
     * Clusters a collection of points using the specified algorithm.
     *
     * @param points The points to cluster
     * @param algorithm The clustering algorithm to use
     * @param config Algorithm-specific configuration
     * @return List of clusters, each containing its member points
     */
    suspend fun cluster(
        points: List<GeoPoint>,
        algorithm: ClusteringAlgorithm,
        config: ClusteringConfig
    ): List<SpatialCluster>

    /**
     * Performs adaptive clustering based on map zoom level.
     *
     * At low zoom (world view), points are aggressively clustered.
     * At high zoom (street level), clusters are expanded or eliminated.
     *
     * @param points The points to cluster
     * @param zoomLevel Map zoom level (0-22)
     * @param viewportBounds Optional viewport to limit clustering
     * @return Clusters appropriate for the given zoom level
     */
    suspend fun clusterForZoom(
        points: List<GeoPoint>,
        zoomLevel: Int,
        viewportBounds: ViewportBounds? = null
    ): List<SpatialCluster>

    /**
     * Streams clustering results as they are computed (for large datasets).
     *
     * @param points Flow of input points
     * @param algorithm Clustering algorithm
     * @param config Configuration
     * @return Flow of clusters, emitted incrementally
     */
    fun clusterStreaming(
        points: Flow<GeoPoint>,
        algorithm: ClusteringAlgorithm,
        config: ClusteringConfig
    ): Flow<SpatialCluster>

    /**
     * Finds the optimal number of clusters for the given points.
     *
     * Uses the elbow method or silhouette analysis.
     *
     * @param points Points to analyze
     * @param minClusters Minimum clusters to consider
     * @param maxClusters Maximum clusters to consider
     * @return Recommended number of clusters and analysis metrics
     */
    suspend fun findOptimalClusterCount(
        points: List<GeoPoint>,
        minClusters: Int = 2,
        maxClusters: Int = 20
    ): ClusterAnalysis

    /**
     * Merges two clusters into one, recomputing the centroid.
     */
    fun mergeClusters(c1: SpatialCluster, c2: SpatialCluster): SpatialCluster

    /**
     * Computes the silhouette coefficient for a clustering result.
     * Returns value between -1 (poor) and 1 (excellent).
     */
    suspend fun silhouetteCoefficient(
        points: List<GeoPoint>,
        clusters: List<SpatialCluster>
    ): Double
}

data class ViewportBounds(
    val minLat: Double,
    val minLng: Double,
    val maxLat: Double,
    val maxLng: Double
)
```

### Required Data Classes

Create `src/main/kotlin/com/pulsemap/model/Cluster.kt`:

```kotlin
package com.pulsemap.model

import kotlinx.serialization.Serializable

/**
 * Clustering algorithm selection.
 */
@Serializable
enum class ClusteringAlgorithm {
    /** K-Means clustering - fast, requires predefined K */
    KMEANS,
    /** DBSCAN - density-based, discovers K automatically */
    DBSCAN,
    /** Hierarchical agglomerative clustering */
    HIERARCHICAL,
    /** Grid-based clustering for map tiles */
    GRID_BASED
}

/**
 * Configuration for clustering algorithms.
 */
@Serializable
data class ClusteringConfig(
    /** For KMEANS: number of clusters */
    val k: Int? = null,
    /** For DBSCAN: maximum distance between points in a cluster (meters) */
    val epsilonMeters: Double? = null,
    /** For DBSCAN: minimum points to form a cluster */
    val minPoints: Int? = null,
    /** For GRID_BASED: cell size in meters */
    val gridCellSizeMeters: Double? = null,
    /** Maximum iterations for iterative algorithms */
    val maxIterations: Int = 100,
    /** Convergence threshold */
    val convergenceThreshold: Double = 0.001
)

/**
 * A spatial cluster containing grouped points.
 */
@Serializable
data class SpatialCluster(
    val id: String,
    val centroid: GeoPoint,
    val members: List<GeoPoint>,
    val radiusMeters: Double,
    val density: Double
) {
    val size: Int get() = members.size

    init {
        require(members.isNotEmpty()) { "Cluster must have at least one member" }
    }
}

/**
 * Result of cluster count optimization analysis.
 */
@Serializable
data class ClusterAnalysis(
    val optimalK: Int,
    val silhouetteScores: Map<Int, Double>,
    val inertiaValues: Map<Int, Double>,
    val recommendation: String
)
```

### Architectural Requirements

1. **Algorithm Strategy Pattern**: Use a sealed interface or strategy pattern for algorithm implementations:

```kotlin
sealed interface ClusteringStrategy {
    suspend fun execute(points: List<GeoPoint>, config: ClusteringConfig): List<SpatialCluster>

    class KMeans : ClusteringStrategy { /* ... */ }
    class DBSCAN : ClusteringStrategy { /* ... */ }
    class Hierarchical : ClusteringStrategy { /* ... */ }
    class GridBased : ClusteringStrategy { /* ... */ }
}
```

2. **Serialization**: Register all sealed class subtypes in `SerializationConfig.kt` if using polymorphic serialization (see bug C4).

3. **Memory Efficiency**: For large datasets, use `Sequence` or `Flow` to avoid loading all points into memory.

4. **Distance Calculations**: Use the Haversine formula from `SpatialUtils` for accurate geographic distance.

### Repository

Create `src/main/kotlin/com/pulsemap/repository/ClusterRepository.kt`:

```kotlin
package com.pulsemap.repository

import com.pulsemap.model.SpatialCluster
import org.jetbrains.exposed.sql.Table

object ClustersTable : Table("clusters") {
    val id = varchar("id", 50)
    val centroidLat = double("centroid_lat")
    val centroidLng = double("centroid_lng")
    val memberCount = integer("member_count")
    val radiusMeters = double("radius_meters")
    val zoomLevel = integer("zoom_level")
    val createdAt = long("created_at")
    override val primaryKey = PrimaryKey(id)
}

interface ClusterRepository {
    suspend fun save(cluster: SpatialCluster, zoomLevel: Int)
    suspend fun findByZoomAndBounds(
        zoomLevel: Int,
        minLat: Double,
        minLng: Double,
        maxLat: Double,
        maxLng: Double
    ): List<SpatialCluster>
    suspend fun deleteByZoom(zoomLevel: Int)
}
```

### Routes

Create `src/main/kotlin/com/pulsemap/routes/ClusterRoutes.kt`:

```kotlin
fun Application.configureClusterRoutes() {
    routing {
        route("/api/clusters") {
            post("/compute") { /* ... */ }
            get("/zoom/{level}") { /* ... */ }
            post("/analyze") { /* ... */ }
        }
    }
}
```

### Acceptance Criteria

1. **Unit Tests** (`src/test/kotlin/com/pulsemap/unit/ClusteringServiceTest.kt`):
   - Test each algorithm produces valid clusters
   - Test empty input handling
   - Test single-point edge case
   - Test cluster merge logic
   - Test silhouette coefficient bounds [-1, 1]

2. **Integration Tests** (`src/test/kotlin/com/pulsemap/integration/ClusteringIntegrationTest.kt`):
   - Test zoom-level adaptive clustering
   - Test repository persistence
   - Test API endpoints

3. **Performance Tests**:
   - Cluster 10,000 points in under 2 seconds
   - Streaming clustering maintains bounded memory

4. **Coverage**: Minimum 80% line coverage

5. **Test Command**: `./gradlew test --tests "com.pulsemap.*.Cluster*"`

---

## Task 3: Address Autocomplete Engine

### Overview

Implement an address autocomplete service that provides real-time suggestions as users type. The service must be fast (sub-100ms response), support fuzzy matching, and handle international addresses.

### Interface Contract

Create `src/main/kotlin/com/pulsemap/service/AutocompleteService.kt`:

```kotlin
package com.pulsemap.service

import com.pulsemap.model.GeoPoint
import com.pulsemap.model.AddressSuggestion
import com.pulsemap.model.AutocompleteConfig
import kotlinx.coroutines.flow.Flow

/**
 * Service for address autocomplete with fuzzy matching and geographic biasing.
 *
 * Designed for real-time search-as-you-type with sub-100ms latency requirements.
 */
interface AutocompleteService {

    /**
     * Returns address suggestions matching the query prefix.
     *
     * @param query Partial address text (minimum 2 characters)
     * @param limit Maximum suggestions to return (1-20)
     * @param biasLocation Optional location to bias results toward
     * @param biasRadiusKm Radius for location bias in kilometers
     * @param config Additional configuration options
     * @return List of suggestions ordered by relevance
     */
    suspend fun suggest(
        query: String,
        limit: Int = 5,
        biasLocation: GeoPoint? = null,
        biasRadiusKm: Double? = null,
        config: AutocompleteConfig = AutocompleteConfig()
    ): List<AddressSuggestion>

    /**
     * Streams suggestions as the user types, with debouncing.
     *
     * @param queryFlow Flow of query strings as user types
     * @param debounceMs Debounce interval in milliseconds
     * @param config Configuration options
     * @return Flow of suggestion lists
     */
    fun suggestStreaming(
        queryFlow: Flow<String>,
        debounceMs: Long = 150,
        config: AutocompleteConfig = AutocompleteConfig()
    ): Flow<List<AddressSuggestion>>

    /**
     * Resolves a suggestion to its full address details.
     *
     * @param suggestionId The ID of a previously returned suggestion
     * @return Full address details, or null if not found
     */
    suspend fun resolve(suggestionId: String): AddressDetails?

    /**
     * Indexes a new address for future suggestions.
     *
     * @param address The address to index
     * @return The generated suggestion ID
     */
    suspend fun indexAddress(address: AddressDetails): String

    /**
     * Bulk indexes addresses for initial data load.
     *
     * @param addresses Flow of addresses to index
     * @return Count of successfully indexed addresses
     */
    suspend fun bulkIndex(addresses: Flow<AddressDetails>): Int

    /**
     * Updates the search index configuration.
     */
    suspend fun reindex(config: IndexConfig)
}

/**
 * Configuration for indexing behavior.
 */
data class IndexConfig(
    val ngramMinLength: Int = 2,
    val ngramMaxLength: Int = 5,
    val enablePhoneticMatching: Boolean = true,
    val maxIndexSizeBytes: Long = 100_000_000
)
```

### Required Data Classes

Create `src/main/kotlin/com/pulsemap/model/Address.kt`:

```kotlin
package com.pulsemap.model

import kotlinx.serialization.Serializable

/**
 * A suggestion returned by the autocomplete service.
 */
@Serializable
data class AddressSuggestion(
    val id: String,
    val displayText: String,
    val matchedText: String,
    val highlightRanges: List<IntRange>,
    val score: Double,
    val location: GeoPoint?,
    val addressType: AddressType
) {
    init {
        require(score in 0.0..1.0) { "Score must be between 0 and 1" }
    }
}

/**
 * Type of address for categorization.
 */
@Serializable
enum class AddressType {
    STREET_ADDRESS,
    CITY,
    POSTAL_CODE,
    POI,           // Point of Interest
    INTERSECTION,
    REGION
}

/**
 * Full address details after resolution.
 */
@Serializable
data class AddressDetails(
    val id: String,
    val formattedAddress: String,
    val streetNumber: String?,
    val streetName: String?,
    val city: String?,
    val state: String?,
    val postalCode: String?,
    val country: String,
    val countryCode: String,
    val location: GeoPoint,
    val placeId: String?,
    val metadata: Map<String, String> = emptyMap()
)

/**
 * Configuration for autocomplete behavior.
 */
@Serializable
data class AutocompleteConfig(
    val fuzzyMatchEnabled: Boolean = true,
    val fuzzyMaxEdits: Int = 2,
    val includePostalCodes: Boolean = true,
    val includePOIs: Boolean = true,
    val languageCode: String = "en",
    val countryFilter: List<String>? = null
)
```

### Architectural Requirements

1. **Trie or Inverted Index**: Implement a prefix trie or inverted index for fast lookups:

```kotlin
class AddressTrie {
    private val root = TrieNode()

    fun insert(address: AddressDetails, ngramConfig: IndexConfig) { /* ... */ }
    fun search(prefix: String, limit: Int): List<AddressSuggestion> { /* ... */ }
    fun fuzzySearch(query: String, maxEdits: Int): List<AddressSuggestion> { /* ... */ }
}

private class TrieNode {
    val children = mutableMapOf<Char, TrieNode>()
    val addresses = mutableListOf<String>() // Address IDs
}
```

2. **Thread Safety**: The trie must support concurrent reads with `ReentrantReadWriteLock` or use immutable data structures.

3. **Flow Debouncing**: Use `debounce()` operator for streaming suggestions (follow proper Flow patterns, avoiding bug A3).

4. **Levenshtein Distance**: Implement edit distance for fuzzy matching:

```kotlin
fun levenshteinDistance(s1: String, s2: String): Int { /* ... */ }
```

5. **Geographic Biasing**: Score boost based on distance to bias location:

```kotlin
fun biasScore(baseScore: Double, distance: Double, biasRadiusKm: Double): Double {
    return if (distance <= biasRadiusKm) {
        baseScore * (1.0 + (biasRadiusKm - distance) / biasRadiusKm * 0.5)
    } else {
        baseScore
    }
}
```

### Repository

Create `src/main/kotlin/com/pulsemap/repository/AddressRepository.kt`:

```kotlin
package com.pulsemap.repository

import com.pulsemap.model.AddressDetails
import org.jetbrains.exposed.sql.Table

object AddressesTable : Table("addresses") {
    val id = varchar("id", 50)
    val formattedAddress = text("formatted_address")
    val streetNumber = varchar("street_number", 20).nullable()
    val streetName = varchar("street_name", 255).nullable()
    val city = varchar("city", 100).nullable()
    val state = varchar("state", 100).nullable()
    val postalCode = varchar("postal_code", 20).nullable()
    val country = varchar("country", 100)
    val countryCode = varchar("country_code", 2)
    val latitude = double("latitude")
    val longitude = double("longitude")
    val placeId = varchar("place_id", 100).nullable()
    val indexedAt = long("indexed_at")
    override val primaryKey = PrimaryKey(id)
}

interface AddressRepository {
    suspend fun save(address: AddressDetails)
    suspend fun findById(id: String): AddressDetails?
    suspend fun searchByPrefix(prefix: String, limit: Int): List<AddressDetails>
    suspend fun findNearby(location: GeoPoint, radiusKm: Double, limit: Int): List<AddressDetails>
    suspend fun count(): Long
}
```

### Routes

Create `src/main/kotlin/com/pulsemap/routes/AutocompleteRoutes.kt`:

```kotlin
fun Application.configureAutocompleteRoutes() {
    routing {
        route("/api/autocomplete") {
            get("/suggest") { /* ... */ }
            get("/resolve/{id}") { /* ... */ }
            post("/index") { /* ... */ }
            post("/bulk-index") { /* ... */ }
        }
    }
}
```

### Acceptance Criteria

1. **Unit Tests** (`src/test/kotlin/com/pulsemap/unit/AutocompleteServiceTest.kt`):
   - Test prefix matching accuracy
   - Test fuzzy matching with typos ("Manhatan" -> "Manhattan")
   - Test geographic bias scoring
   - Test highlight range calculation
   - Test minimum query length validation

2. **Integration Tests** (`src/test/kotlin/com/pulsemap/integration/AutocompleteIntegrationTest.kt`):
   - Test API endpoints
   - Test bulk indexing
   - Test concurrent search operations

3. **Performance Tests**:
   - Search 100,000 indexed addresses in under 50ms
   - Index 10,000 addresses in under 5 seconds
   - Streaming suggestions with proper debouncing

4. **Coroutine Tests** (`src/test/kotlin/com/pulsemap/coroutine/AutocompleteCoroutineTest.kt`):
   - Test Flow debouncing behavior
   - Test cancellation during bulk indexing
   - Test concurrent index updates

5. **Coverage**: Minimum 80% line coverage

6. **Test Command**: `./gradlew test --tests "com.pulsemap.*.Autocomplete*"`

---

## General Requirements for All Tasks

### Code Style

- Follow existing patterns in the codebase
- Use `suspend` functions for all async operations
- Prefer `Flow` over callbacks for streaming data
- Use `@Serializable` for all data classes exposed via API

### Documentation

- All public interfaces must have KDoc comments
- Document parameter constraints and exceptions
- Include usage examples in interface KDoc

### Error Handling

- Define domain-specific exceptions
- Use `Result<T>` or sealed classes for expected failures
- Let unexpected exceptions propagate for proper error reporting

### Testing

Run all tests with:

```bash
./gradlew test
```

Run specific task tests:

```bash
# Isochrone tests
./gradlew test --tests "com.pulsemap.*.Isochrone*"

# Clustering tests
./gradlew test --tests "com.pulsemap.*.Cluster*"

# Autocomplete tests
./gradlew test --tests "com.pulsemap.*.Autocomplete*"
```

### Integration Points

Each new module should integrate with:

1. **Application.kt**: Register routes in `module()` function
2. **SerializationConfig.kt**: Register any sealed class subtypes
3. **Existing services**: Reuse `GeocodingService`, `SpatialUtils`, etc. where applicable
