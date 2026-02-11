# QuantumCore - Alternative Tasks

## Overview

QuantumCore supports 5 alternative task types beyond the core debugging challenge: feature development, refactoring for performance, optimization of critical paths, API extensions, and system-wide migrations. Each task focuses on a different aspect of building a high-frequency trading platform.

## Environment

- **Language**: Rust
- **Infrastructure**: NATS 2.10, PostgreSQL 15, Redis 7, InfluxDB 2, etcd 3.5
- **Difficulty**: Principal (8-16 hours)

## Tasks

### Task 1: Multi-Leg Order Support (Feature Development)

Extend QuantumCore's order service to handle multi-leg orders (spreads, straddles, butterfly options). Implement atomic execution where all legs fill at acceptable prices or the entire order is rejected. Integrate risk calculations for spread margin rules and track order lifecycle events across all legs.

### Task 2: Order Book Data Structure Optimization (Refactoring)

Refactor the matching engine's order book from BTreeMap to a more cache-friendly structure using arena allocation or contiguous memory layout. Maintain O(log n) lookups while improving performance for top-of-book operations and reducing per-order heap allocations.

### Task 3: Market Data Feed Latency Reduction (Performance Optimization)

Optimize the market data feed to achieve sub-10-microsecond P99 quote distribution latency. Use lock-free data structures for quote caching, batch notification, and Arc-based sharing to minimize cloning while handling slow consumers without blocking fast consumers.

### Task 4: FIX Protocol Gateway (API Extension)

Implement a FIX 4.4 gateway accepting institutional order flow with session management, message parsing, and execution report generation. Handle logon/logout sequences, sequence number tracking, and sub-millisecond message throughput supporting 10,000+ messages per second.

### Task 5: Event Sourcing Migration (Migration)

Migrate the order and position services from in-memory state to full event sourcing. Define comprehensive event schemas, implement append-only event stores with snapshotting, build projection logic for state materialization, and handle the dual-write period with minimal latency impact.

## Getting Started

```bash
# Start infrastructure
docker compose up -d

# Run tests
cargo test --workspace
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
