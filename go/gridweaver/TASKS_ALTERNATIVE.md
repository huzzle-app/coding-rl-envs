# GridWeaver Alternative Tasks

This document contains alternative tasks for the GridWeaver distributed smart-grid orchestration platform. Each task focuses on extending or improving the platform's capabilities in realistic ways that grid operators might request.

---

## Task 1: Feature Development - Multi-Region Cascade Dispatch

### Description

Grid operators have requested the ability to perform cascade dispatch operations across multiple interconnected regions. When a region experiences a generation shortfall that exceeds its local demand response capacity, the system should automatically attempt to source supplemental power from neighboring regions through the topology graph.

Currently, dispatch planning operates on a single-region basis with `BuildPlan` and `ApplyConstraint`. The new feature should evaluate cross-regional power transfer opportunities by traversing the topology graph to find regions with surplus capacity. The cascade should respect transmission line capacity constraints, account for transfer losses based on distance, and prioritize transfers from regions with the lowest transfer cost.

The implementation must integrate with the existing consensus mechanism to ensure only the elected leader node initiates cascade operations, preventing split-brain scenarios where multiple nodes attempt conflicting inter-regional transfers simultaneously.

### Acceptance Criteria

- Implement a `CascadeDispatch` function that accepts a region identifier and shortfall amount, returning a slice of transfer orders from neighboring regions
- The function must traverse the topology graph using `FindPath` to identify viable source regions with available capacity
- Transfer amounts must respect edge capacity constraints via `ValidateTransfer` and `RemainingCapacity`
- Calculate transfer costs using distance-based loss factors and prioritize lowest-cost sources
- Integrate leader election check via `HasQuorum` and `DetermineLeader` before initiating transfers
- Emit events to the pipeline for each transfer decision with proper sequencing
- Return an error if total available transfers cannot meet the shortfall threshold

### Test Command

```bash
go test -v ./...
```

---

## Task 2: Refactoring - Unified Event Pipeline with Back-Pressure

### Description

The current event handling in GridWeaver is fragmented across multiple packages. The `internal/events` package provides basic filtering, deduplication, and windowing, while `internal/concurrency` offers pipeline primitives like `Pipeline` and `MergeChannels`. The workflow orchestrator uses its own ad-hoc event collection via `BatchProcess`. This leads to inconsistent event handling semantics and makes it difficult to implement system-wide back-pressure when downstream consumers are overwhelmed.

Refactor the event infrastructure to create a unified event pipeline that all grid operations flow through. The refactored design should provide a single entry point for event submission, consistent deduplication based on event ID and sequence, configurable window sizes for event batching, and built-in back-pressure signaling when the pipeline buffer fills.

The refactoring must preserve backward compatibility with existing code that uses `FilterByType`, `FilterByRegion`, `WindowEvents`, and `SortBySequence`. These functions should become pipeline stages that can be composed into custom processing flows.

### Acceptance Criteria

- Create a `UnifiedPipeline` struct that wraps the existing channel-based primitives with buffer management
- Implement a `Submit(event Event) error` method that returns `ErrBackPressure` when the buffer is full
- Refactor `FilterByType`, `FilterByRegion`, and `WindowEvents` to return pipeline stage functions compatible with method chaining
- Add a `WithDeduplication(windowSize int64)` option that applies `DeduplicateEvents` logic inline
- Ensure `SortBySequence` can be applied as a terminal operation before consumption
- Preserve the existing function signatures for backward compatibility (original functions call into the new unified pipeline)
- Add metrics hooks for tracking events submitted, filtered, deduplicated, and delivered

### Test Command

```bash
go test -v ./...
```

---

## Task 3: Performance Optimization - Parallel Topology Analysis

### Description

Large grid topologies with thousands of nodes and edges are causing performance bottlenecks during real-time analysis. The current `Graph` implementation uses a single mutex for all read/write operations, and path-finding via `FindPath` is single-threaded. During peak load, topology queries for capacity validation and path analysis become a bottleneck, increasing dispatch latency beyond acceptable SLA thresholds.

Optimize the topology analysis subsystem to support parallel operations. The graph structure should use fine-grained locking or lock-free data structures to allow concurrent reads. Path-finding should be parallelized to explore multiple candidate routes simultaneously and return the first viable path. Capacity calculations like `TotalCapacity` and `ValidateTopology` should leverage the worker pool from `internal/concurrency`.

The optimization must maintain correctness under concurrent access, passing all race detection tests. Memory allocation should be minimized in hot paths to reduce GC pressure during high-frequency dispatch cycles.

### Acceptance Criteria

- Replace the single `sync.RWMutex` with a sharded lock strategy based on node ID hash for `AddEdge` and `Neighbors`
- Implement `ParallelFindPath` that spawns multiple BFS workers exploring different branches and terminates early on first path found
- Refactor `TotalCapacity` to use `FanOut` from the concurrency package for parallel edge summation
- Optimize `ValidateTopology` to check edges concurrently using the worker pool, collecting violations thread-safely
- Reduce allocations in `FindPath` by reusing visited maps and path buffers via `sync.Pool`
- All operations must pass `go test -race` without data race warnings
- Benchmark results should show at least 3x improvement for graphs with 1000+ nodes

### Test Command

```bash
go test -race -v ./...
```

---

## Task 4: API Extension - Real-Time Demand Response Bidding

### Description

Market operators have requested an API extension to support real-time demand response bidding. Currently, the `demandresponse` package manages program capacity with simple commit/dispatch operations. The new feature should allow external participants to submit bids for demand reduction, with the system evaluating and accepting bids based on price, reliability history, and timing constraints.

The bidding API should support bid submission with price per MW, minimum/maximum reduction amounts, and availability windows. A bid evaluation engine should rank bids by cost-effectiveness, considering participant reliability scores from historical performance. Accepted bids should integrate with the existing `Program` structure, updating committed capacity and generating audit entries for compliance.

The API must handle concurrent bid submissions safely, ensure fair evaluation ordering, and provide real-time feedback on bid status (pending, accepted, rejected, expired).

### Acceptance Criteria

- Define a `Bid` struct with fields for participant ID, price per MW, min/max MW, start/end timestamps, and reliability score
- Implement `SubmitBid(bid Bid) (string, error)` returning a bid ID and validating bid parameters
- Create `EvaluateBids(program Program, windowStart, windowEnd int64) []AcceptedBid` that ranks and selects optimal bids
- Bid ranking must factor price (lower is better), reliability score (higher is better), and timing flexibility
- Integrate with `ApplyDispatch` to update program committed capacity for accepted bids
- Generate `AuditEntry` records for each bid evaluation decision via the audit service
- Ensure thread-safe bid submission using appropriate synchronization from the concurrency package
- Add bid expiration handling that automatically rejects bids past their availability window

### Test Command

```bash
go test -v ./...
```

---

## Task 5: Migration - Event Sourcing for Dispatch History

### Description

The grid operations team requires full audit trail capabilities for dispatch decisions to meet regulatory compliance requirements. Currently, dispatch state is computed on-demand without historical record. The platform needs to migrate to an event-sourcing architecture where all dispatch operations are recorded as immutable events, and current state can be reconstructed by replaying the event log.

The migration should introduce event types for all dispatch operations: plan creation, constraint application, demand response activation, and curtailment decisions. Each event must capture the full context needed to reproduce the decision, including inputs, intermediate calculations, and outputs. A projection mechanism should rebuild current dispatch state from the event stream for any point in time.

The migration must be backward compatible, allowing the existing synchronous dispatch API to continue working while events are captured in the background. A replay mechanism should support state reconstruction for debugging and compliance audits.

### Acceptance Criteria

- Define event types: `DispatchPlanCreated`, `ConstraintApplied`, `DemandResponseActivated`, `CurtailmentRecorded`
- Each event must include timestamp, correlation ID, actor, region, and all input/output values
- Implement `EventStore` interface with `Append(event)`, `ReadFrom(sequence int64)`, and `ReadByCorrelation(id string)` methods
- Create `DispatchProjection` that maintains current state by processing events sequentially
- Add `ReplayTo(timestamp int64)` that reconstructs state at any historical point
- Modify `BuildPlan`, `ApplyConstraint`, and demand response functions to emit events via the store
- Ensure events are properly sequenced using the existing `Sequence` field from the events package
- Provide migration utility that generates synthetic events from any existing state snapshots

### Test Command

```bash
go test -v ./...
```

---

## Notes

- All tasks should integrate with the existing infrastructure (NATS JetStream, PostgreSQL, Redis, InfluxDB, etcd) as appropriate
- Maintain consistency with the existing code style and package organization
- Ensure all new code passes race detection: `go test -race -v ./...`
- Follow the existing patterns for error handling, logging, and metrics
