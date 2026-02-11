# QuantumCore - Alternative Tasks

This document contains alternative tasks for the QuantumCore high-frequency trading platform. Each task focuses on a different aspect of trading system development.

---

## Task 1: Multi-Leg Order Support (Feature Development)

### Description

QuantumCore currently supports single-leg orders (individual buy/sell orders for a single instrument). Institutional clients require multi-leg order functionality to execute complex trading strategies such as spreads, straddles, and butterfly options. A multi-leg order atomically executes multiple child orders as a single unit - either all legs fill or none do.

The implementation must handle price ratio constraints between legs, support both simultaneous and sequential leg execution modes, and integrate with the existing risk management system. Multi-leg orders present unique challenges for the matching engine since partial fills on one leg may require unwinding fills on other legs if the complete order cannot be satisfied.

Risk calculations must account for the combined exposure of all legs, and margin requirements should reflect the hedged nature of spread positions (typically lower margin than individual legs combined). The order lifecycle events must track all legs while maintaining a unified parent order status.

### Acceptance Criteria

- Multi-leg orders with 2-4 legs can be created via the order service API
- Atomic execution ensures all legs fill at acceptable prices or the entire order is rejected
- Price ratio constraints (e.g., "leg A price must be within 0.5% of leg B price") are validated before execution
- Risk service calculates margin for multi-leg positions using spread margin rules (reduced margin for hedged positions)
- Order events track individual leg fills while maintaining parent order status
- Partial fills on one leg correctly trigger attempted fills on remaining legs
- Cancellation of a multi-leg order cancels all unfilled legs atomically
- Position tracking aggregates P&L across all legs of a multi-leg order

### Test Command

```bash
cargo test --workspace
```

---

## Task 2: Order Book Data Structure Optimization (Refactoring)

### Description

The current order book implementation uses `BTreeMap<Decimal, VecDeque<Order>>` for both bid and ask sides. While correct, this structure has suboptimal cache locality and excessive memory allocations during high-frequency trading scenarios. Each price level modification requires map operations, and the VecDeque at each level causes pointer chasing that hurts L1/L2 cache performance.

The order book should be refactored to use a more cache-friendly structure. Consider arena-based allocation for orders, contiguous memory layouts for price levels near the top of book, and reduced allocations during the order matching hot path. The structure should maintain O(log n) price level lookup while improving constants for typical market maker workloads where most activity occurs within a few ticks of the best bid/ask.

The refactored implementation must maintain identical semantics for all existing order book operations including add, cancel, modify, and match. Thread safety requirements remain unchanged - the order book is protected by an external mutex during modification.

### Acceptance Criteria

- Order book uses arena allocation or similar technique to reduce per-order heap allocations
- Top-of-book operations (best bid/ask lookup, matching at best price) complete without pointer chasing
- Memory layout keeps frequently-accessed price levels in contiguous memory
- Add order hot path performs zero heap allocations for typical order sizes
- All existing order book tests pass without modification
- Benchmark shows measurable latency reduction for add/match/cancel operations
- Memory usage per order is reduced compared to current implementation
- Price-time priority is correctly maintained across the refactored structure

### Test Command

```bash
cargo test --workspace
```

---

## Task 3: Market Data Feed Latency Reduction (Performance Optimization)

### Description

The market data feed currently distributes quotes using Tokio broadcast channels with a configurable buffer size. Under high message rates, the feed experiences increased latency due to channel contention, excessive cloning of quote structures, and suboptimal wake patterns for subscribers. The P99 latency target for quote distribution is 10 microseconds from receipt to all subscriber notification.

The feed architecture should be optimized to minimize latency for the critical path from quote ingestion to subscriber notification. Consider lock-free data structures for the latest quote cache, batch notification of multiple subscribers, and reduced copying of quote data. The optimization should maintain the current API contract while significantly reducing distribution latency.

Subscribers include the matching engine (which needs every quote), the risk service (which can tolerate some staleness), and WebSocket connections to clients (which may be slower consumers). The solution should handle slow consumers without blocking fast consumers or dropping critical updates.

### Acceptance Criteria

- Quote distribution P99 latency is under 10 microseconds for up to 1000 concurrent subscribers
- Lock-free data structure for latest quote lookup eliminates reader contention
- Quote data is shared via Arc or similar to avoid cloning in the hot path
- Slow consumers do not block fast consumers or the ingestion path
- No quotes are dropped for matching engine subscribers (critical path)
- Risk service receives quotes with bounded staleness (configurable, default 100ms max age)
- WebSocket clients receive updates at a configurable throttled rate
- Memory usage remains bounded regardless of message rate

### Test Command

```bash
cargo test --workspace
```

---

## Task 4: FIX Protocol Gateway (API Extension)

### Description

QuantumCore currently exposes a REST API and WebSocket interface for order management. Many institutional clients use the FIX (Financial Information eXchange) protocol, the industry standard for trading communication. A FIX 4.4 gateway must be implemented to accept inbound order flow and publish execution reports.

The FIX gateway should handle session management (logon, logout, heartbeat, sequence number synchronization), translate FIX messages to internal order representations, and generate compliant execution reports for fills, partial fills, cancellations, and rejections. The gateway must maintain message sequence numbers and support session recovery after disconnection.

Performance requirements include sub-millisecond message parsing, support for 10,000+ messages per second per session, and proper handling of gap fill scenarios. The gateway must validate FIX message syntax and reject malformed messages with appropriate FIX reject messages.

### Acceptance Criteria

- FIX 4.4 session management with configurable sender/target comp IDs
- Logon/Logout sequences properly authenticated using username/password or certificate
- Heartbeat monitoring with configurable interval and automatic session termination on timeout
- NewOrderSingle (D) messages translated to internal CreateOrderRequest
- OrderCancelRequest (F) messages translated to cancel operations
- ExecutionReport (8) messages generated for all order state transitions
- Sequence number tracking with persistent storage for session recovery
- Gap fill requests handled correctly on session reconnection
- Message rate limiting per session with configurable thresholds
- Reject (3) messages sent for malformed or invalid FIX messages

### Test Command

```bash
cargo test --workspace
```

---

## Task 5: Event Sourcing Migration (Migration)

### Description

The current order and position services use in-memory state with ad-hoc event logging. This approach has limitations for audit compliance, disaster recovery, and debugging production issues. The system should be migrated to full event sourcing where all state changes are derived from an immutable event log.

The migration involves defining a comprehensive event schema for all domain events (order created, filled, cancelled; position opened, updated, closed; margin reserved, released), implementing event stores with append-only semantics, and building projection logic to materialize current state from events. The event store should support snapshotting to bound recovery time.

Particular attention is needed for the transition period where both old and new systems must run in parallel. Events must be idempotent to handle replay during recovery, and the migration must not introduce additional latency on the critical order path. Consider using separate event stores per aggregate (order, position, account) for scalability.

### Acceptance Criteria

- Event schema defined for all order lifecycle events with version field for schema evolution
- Event schema defined for all position changes including realized/unrealized P&L updates
- Event store implementation with append-only writes and sequential read support
- Projection logic rebuilds current order state from event history correctly
- Projection logic rebuilds current position state from event history correctly
- Snapshots created periodically to bound recovery time (configurable, default every 1000 events)
- Recovery from snapshot + subsequent events produces identical state to full replay
- Event replay is idempotent - replaying the same events produces identical state
- Dual-write mode during migration writes to both old and new systems
- Latency impact on order submission is less than 100 microseconds P99
- Event log supports retention policies for compliance (configurable, default 7 years)

### Test Command

```bash
cargo test --workspace
```
