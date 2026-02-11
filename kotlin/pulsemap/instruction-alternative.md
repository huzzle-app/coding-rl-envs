# PulseMap - Alternative Tasks

## Overview

These 5 alternative tasks focus on extending and improving the PulseMap geospatial analytics platform. Each task requires understanding of the existing codebase architecture and geospatial domain concepts, testing skills in feature development, refactoring, performance optimization, API design, and infrastructure migration.

## Environment

- **Language**: Kotlin 1.9
- **Framework**: Ktor 2.3, Exposed ORM
- **Infrastructure**: PostgreSQL 16 + PostGIS, Redis 7
- **Difficulty**: Senior
- **Tests**: 125+

## Tasks

### Task 1: Implement Tile Layer Compositing (Feature Development)

PulseMap currently serves individual map tiles, but customers need to overlay multiple data layers (sensor heatmaps, boundary polygons, traffic data) into a single composited tile for efficient rendering. The platform needs a tile compositing service that merges multiple tile sources while respecting layer ordering and opacity settings.

The compositing system should accept a list of layer specifications with z-order and opacity values, fetch tiles from each source (cached or generated), and blend them into a single output tile using alpha compositing. The service must handle missing layers gracefully, support different tile formats (PNG for raster, MVT for vector), and cache composited results with proper invalidation when underlying layers update.

### Task 2: Refactor Geometry Processing to Use Visitor Pattern (Refactoring)

The current geometry handling uses a `when` expression over a sealed class in `GeometryType.kt`, which requires updating every location that processes geometries whenever a new type is added. This pattern has already caused issues with `MultiPolygon` support. The codebase needs refactoring to use the Visitor pattern for geometry operations.

The refactoring should introduce a `GeometryVisitor<T>` interface that geometry types accept, allowing new operations to be added without modifying the sealed class. Existing operations like `area()`, `centroid()`, and `boundingBox()` should be migrated to visitor implementations. This will make the geometry processing more extensible and ensure compile-time completeness checking for all geometry types.

### Task 3: Optimize Spatial Aggregation with Quadtree Indexing (Performance Optimization)

The `SpatialAggregationService` currently iterates through all sensor readings linearly when computing heatmaps and spatial aggregations. For large datasets (100K+ sensors), this causes timeouts on tile requests. The service needs optimization using a quadtree spatial index for efficient range queries and point aggregation.

The quadtree implementation should support dynamic insertion as new sensor readings arrive, efficient bounding box queries for tile generation, and configurable node capacity for memory/query tradeoff tuning. The index must be thread-safe for concurrent reads during tile generation while allowing background updates from the ingestion pipeline.

### Task 4: Add GeoJSON Import/Export API Endpoints (API Extension)

The current ingestion API only accepts proprietary sensor reading formats. Customers need to import existing datasets in standard GeoJSON format and export query results as GeoJSON for use in other GIS tools. The platform requires new API endpoints that handle GeoJSON Feature and FeatureCollection parsing with proper coordinate reference system handling.

The import endpoint should validate GeoJSON structure, extract geometry and properties, map them to internal sensor readings, and handle coordinate transformations between common projections (WGS84, Web Mercator). The export endpoint should support filtering by bounding box, time range, and sensor type, with pagination for large result sets.

### Task 5: Migrate from In-Memory Cache to Redis Cluster (Migration)

PulseMap currently uses an in-memory `mutableMapOf` for tile caching in `TileService`. This limits horizontal scaling since each instance maintains its own cache, causing cache misses when load balancers route requests to different instances. The caching layer needs migration to Redis Cluster to enable shared caching across all application instances.

The migration should introduce a `TileCache` interface to abstract cache operations, implement both in-memory and Redis backends, and configure the Redis client with proper connection pooling, retry logic, and circuit breaker patterns. The migration must be backwards-compatible, allowing gradual rollout with feature flags to switch between cache backends.

## Getting Started

```bash
cd /Users/amit/projects/terminal-bench-envs/kotlin/pulsemap
docker compose up -d
./gradlew test --no-daemon
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
