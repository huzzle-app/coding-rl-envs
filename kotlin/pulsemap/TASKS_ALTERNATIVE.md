# PulseMap - Alternative Development Tasks

These alternative tasks focus on extending and improving the PulseMap geospatial analytics platform. Each task requires understanding of the existing codebase architecture and geospatial domain concepts.

---

## Task 1: Implement Tile Layer Compositing (Feature Development)

PulseMap currently serves individual map tiles, but customers need to overlay multiple data layers (sensor heatmaps, boundary polygons, traffic data) into a single composited tile for efficient rendering. The platform needs a tile compositing service that merges multiple tile sources while respecting layer ordering and opacity settings.

The compositing system should accept a list of layer specifications with z-order and opacity values, fetch tiles from each source (cached or generated), and blend them into a single output tile using alpha compositing. The service must handle missing layers gracefully, support different tile formats (PNG for raster, MVT for vector), and cache composited results with proper invalidation when underlying layers update.

### Acceptance Criteria

- Implement a `TileCompositingService` that accepts layer specifications with z-order and opacity
- Support blending up to 8 layers with configurable opacity (0.0 to 1.0) per layer
- Handle cache coherency: composited tiles must invalidate when any source layer updates
- Return appropriate errors when required layers are unavailable (404 vs 503 semantics)
- Ensure thread-safe access to the layer registry and compositing cache
- Support both synchronous and async compositing modes for different latency requirements
- Composited tiles must include proper cache headers based on the minimum TTL of source layers

### Test Command

```bash
./gradlew test
```

---

## Task 2: Refactor Geometry Processing to Use Visitor Pattern (Refactoring)

The current geometry handling uses a `when` expression over a sealed class in `GeometryType.kt`, which requires updating every location that processes geometries whenever a new type is added. This pattern has already caused issues with `MultiPolygon` support. The codebase needs refactoring to use the Visitor pattern for geometry operations.

The refactoring should introduce a `GeometryVisitor<T>` interface that geometry types accept, allowing new operations to be added without modifying the sealed class. Existing operations like `area()`, `centroid()`, and `boundingBox()` should be migrated to visitor implementations. This will make the geometry processing more extensible and ensure compile-time completeness checking for all geometry types.

### Acceptance Criteria

- Define a `GeometryVisitor<T>` interface with visit methods for each geometry type
- Add `accept(visitor: GeometryVisitor<T>): T` method to the `GeometryType` sealed class
- Migrate `area()` calculation to an `AreaVisitor` implementation
- Migrate `boundingBox()` computation to a `BoundingBoxVisitor` implementation
- Implement a new `CentroidVisitor` for calculating geometry centroids
- All existing geometry-related tests must continue to pass
- Remove the `else` branch anti-pattern from geometry processing code

### Test Command

```bash
./gradlew test
```

---

## Task 3: Optimize Spatial Aggregation with Quadtree Indexing (Performance Optimization)

The `SpatialAggregationService` currently iterates through all sensor readings linearly when computing heatmaps and spatial aggregations. For large datasets (100K+ sensors), this causes timeouts on tile requests. The service needs optimization using a quadtree spatial index for efficient range queries and point aggregation.

The quadtree implementation should support dynamic insertion as new sensor readings arrive, efficient bounding box queries for tile generation, and configurable node capacity for memory/query tradeoff tuning. The index must be thread-safe for concurrent reads during tile generation while allowing background updates from the ingestion pipeline.

### Acceptance Criteria

- Implement a `SpatialQuadtree<T>` generic class with configurable max depth and node capacity
- Support `insert(point: GeoPoint, data: T)` and `queryBoundingBox(box: BoundingBox): List<T>` operations
- Achieve O(log n) average case for point queries instead of O(n)
- Implement concurrent read access during tile generation without blocking ingestion
- Add `rebalance()` method for periodic index optimization
- Memory overhead must not exceed 2x the raw data size for typical sensor distributions
- Heatmap generation for a single tile must complete within 50ms for 100K indexed sensors

### Test Command

```bash
./gradlew test
```

---

## Task 4: Add GeoJSON Import/Export API Endpoints (API Extension)

The current ingestion API only accepts proprietary sensor reading formats. Customers need to import existing datasets in standard GeoJSON format and export query results as GeoJSON for use in other GIS tools. The platform requires new API endpoints that handle GeoJSON Feature and FeatureCollection parsing with proper coordinate reference system handling.

The import endpoint should validate GeoJSON structure, extract geometry and properties, map them to internal sensor readings, and handle coordinate transformations between common projections (WGS84, Web Mercator). The export endpoint should support filtering by bounding box, time range, and sensor type, with pagination for large result sets.

### Acceptance Criteria

- Add `POST /api/v1/import/geojson` endpoint accepting GeoJSON FeatureCollection
- Add `GET /api/v1/export/geojson` endpoint with bbox, timeRange, and sensorType query parameters
- Support coordinate reference system transformations between EPSG:4326 and EPSG:3857
- Validate GeoJSON structure and return detailed error messages for malformed input
- Implement pagination using cursor-based navigation for exports exceeding 10K features
- Handle geometry type mapping between GeoJSON and internal `GeometryType` sealed class
- Include proper Content-Type headers (`application/geo+json`) per RFC 7946

### Test Command

```bash
./gradlew test
```

---

## Task 5: Migrate from In-Memory Cache to Redis Cluster (Migration)

PulseMap currently uses an in-memory `mutableMapOf` for tile caching in `TileService`. This limits horizontal scaling since each instance maintains its own cache, causing cache misses when load balancers route requests to different instances. The caching layer needs migration to Redis Cluster to enable shared caching across all application instances.

The migration should introduce a `TileCache` interface to abstract cache operations, implement both in-memory and Redis backends, and configure the Redis client with proper connection pooling, retry logic, and circuit breaker patterns. The migration must be backwards-compatible, allowing gradual rollout with feature flags to switch between cache backends.

### Acceptance Criteria

- Define a `TileCache` interface with `get`, `put`, `invalidate`, and `invalidatePattern` operations
- Implement `InMemoryTileCache` and `RedisTileCache` classes implementing the interface
- Configure Redis Lettuce client with connection pooling (min 2, max 10 connections per node)
- Add circuit breaker that falls back to in-memory cache when Redis is unavailable
- Support cache key prefixing for multi-tenant deployments
- Implement TTL-based expiration with configurable defaults per tile zoom level
- Add metrics for cache hit/miss rates and Redis operation latencies

### Test Command

```bash
./gradlew test
```
