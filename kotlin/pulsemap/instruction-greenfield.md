# PulseMap - Greenfield Implementation Tasks

## Overview

These 3 greenfield implementation tasks require building new modules from scratch while following the established architectural patterns in the PulseMap codebase. Each task provides detailed interface contracts, data class specifications, and architectural guidelines to ensure consistency with existing code.

## Environment

- **Language**: Kotlin 1.9
- **Framework**: Ktor 2.3, Exposed ORM
- **Infrastructure**: PostgreSQL 16 + PostGIS, Redis 7
- **Difficulty**: Senior
- **Tests**: 125+

## Tasks

### Task 1: Isochrone Generator Service (Spatial Analysis)

Implement an isochrone generator that computes travel-time polygons from a given origin point. An isochrone represents all locations reachable within a specified time threshold, useful for accessibility analysis ("show me everywhere I can reach in 15 minutes").

**Interface Highlights**:
- `generate()` — Generates single isochrone polygon from origin point with configurable travel mode (WALK, BIKE, DRIVE, TRANSIT) and time threshold (1-120 minutes)
- `generateMultiple()` — Streams concentric isochrones for multiple time thresholds
- `intersect()` — Computes common reachable areas between two isochrones
- `estimateTravelTime()` — Estimates travel time between two points

**Key Data Structures**:
- `IsochroneResult` — Contains origin, time threshold, mode, polygon boundary, computed area, and timestamp
- `TravelMode` — Enum with WALK (5 km/h), BIKE (15 km/h), DRIVE (40 km/h), TRANSIT (25 km/h)
- `IsochroneResolution` — Grid resolution for sampling: LOW (500m), MEDIUM (200m), HIGH (50m)

**Repository Pattern**:
- `IsochroneRepository` interface with `findCached()`, `save()`, and `evictExpired()` methods for caching results

**Architectural Requirements**:
- Use structured concurrency with `coroutineScope` (avoid `GlobalScope`)
- Apply `flowOn(Dispatchers.Default)` before terminal operators on Flows
- Use `List<GeoPoint>` for proper equality semantics
- Implement TOCTOU-safe caching with `getOrPut` or synchronized access
- Add routes in `src/main/kotlin/com/pulsemap/routes/IsochroneRoutes.kt`

### Task 2: Spatial Clustering Service (Data Analysis)

Implement a spatial clustering service that groups nearby geographic points into clusters. This is essential for map visualization (showing cluster markers instead of thousands of individual points) and spatial analysis.

**Interface Highlights**:
- `cluster()` — Groups points using specified algorithm (KMEANS, DBSCAN, HIERARCHICAL, GRID_BASED)
- `clusterForZoom()` — Adaptive clustering based on map zoom level (0-22)
- `clusterStreaming()` — Streams clustering results incrementally for large datasets
- `findOptimalClusterCount()` — Determines optimal number of clusters using elbow method or silhouette analysis
- `mergeClusters()` — Merges two clusters with recomputed centroid
- `silhouetteCoefficient()` — Computes clustering quality metric [-1, 1]

**Key Data Structures**:
- `SpatialCluster` — Contains id, centroid, member points, radius, and density metrics
- `ClusteringAlgorithm` — Enum selecting algorithm implementation
- `ClusteringConfig` — Algorithm-specific parameters (k for KMEANS, epsilon for DBSCAN, cell size for GRID_BASED)
- `ClusterAnalysis` — Result with optimal K, silhouette scores, inertia values, and recommendations
- `ViewportBounds` — Geographic bounds for limiting clustering scope

**Repository Pattern**:
- `ClusterRepository` interface with `save()`, `findByZoomAndBounds()`, and `deleteByZoom()` methods
- `ClustersTable` — Exposed ORM mapping with zoom level and bounding box indices

**Architectural Requirements**:
- Use sealed interface or strategy pattern for algorithm implementations
- Register polymorphic serialization subtypes in `SerializationConfig.kt`
- Use `Sequence` or `Flow` for large datasets to avoid loading all data into memory
- Apply Haversine formula from `SpatialUtils` for accurate geographic distance
- Add routes in `src/main/kotlin/com/pulsemap/routes/ClusterRoutes.kt`

### Task 3: Address Autocomplete Engine (Search & Indexing)

Implement an address autocomplete service that provides real-time suggestions as users type. The service must be fast (sub-100ms response), support fuzzy matching, and handle international addresses.

**Interface Highlights**:
- `suggest()` — Returns address suggestions matching query prefix with geographic biasing
- `suggestStreaming()` — Streams suggestions with debouncing as user types (debounce default 150ms)
- `resolve()` — Resolves suggestion ID to full address details
- `indexAddress()` — Indexes single address for future suggestions
- `bulkIndex()` — Bulk indexes Flow of addresses for initial data load
- `reindex()` — Updates search index configuration (ngram lengths, phonetic matching)

**Key Data Structures**:
- `AddressSuggestion` — Contains id, displayText, matchedText, highlightRanges, relevance score [0, 1], location, and addressType
- `AddressDetails` — Full address information (street, city, state, postal code, country, location, metadata)
- `AddressType` — Enum: STREET_ADDRESS, CITY, POSTAL_CODE, POI, INTERSECTION, REGION
- `AutocompleteConfig` — Flags for fuzzy matching, postal codes, POIs, language, and country filtering
- `IndexConfig` — Tuning parameters (ngram min/max length, phonetic matching, max index size)

**Repository Pattern**:
- `AddressRepository` interface with `save()`, `findById()`, `searchByPrefix()`, `findNearby()`, and `count()` methods
- `AddressesTable` — Exposed ORM mapping with address components and geographic location

**Architectural Requirements**:
- Implement prefix trie or inverted index for fast lookups
- Use `ReentrantReadWriteLock` or immutable data structures for thread-safe concurrent reads
- Apply `debounce()` operator properly in Flow pipelines (avoiding bug A3 pattern)
- Implement Levenshtein distance for fuzzy matching with configurable max edits
- Apply geographic biasing: boost score based on proximity to bias location
- Add routes in `src/main/kotlin/com/pulsemap/routes/AutocompleteRoutes.kt`

## Getting Started

```bash
cd /Users/amit/projects/terminal-bench-envs/kotlin/pulsemap
docker compose up -d
./gradlew test --no-daemon
```

## Success Criteria

Implementations meet the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md):
- All unit tests passing (minimum 80% line coverage per task)
- All integration tests passing
- All performance requirements met
- Coroutine tests validating proper Flow handling and concurrency
- No memory leaks or resource leaks
