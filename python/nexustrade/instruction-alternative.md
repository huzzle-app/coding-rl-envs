# NexusTrade - Alternative Tasks

## Overview

NexusTrade supports five realistic alternative engineering tasks that test feature development, refactoring, optimization, and infrastructure migration skills. Each task involves implementing missing functionality, improving code quality, or modernizing the platform's infrastructure while maintaining backward compatibility and passing all existing tests.

## Environment

- **Language**: Python (FastAPI/Django)
- **Infrastructure**: Kafka, PostgreSQL x3, Redis, Consul
- **Difficulty**: Principal Engineer (8-20 hours per task)

## Tasks

### Task 1: Stop-Loss and Take-Profit Order Types (Feature Development)

Implement OCO (One-Cancels-Other) orders that combine stop-loss and take-profit into a single atomic order group. When a position is opened, traders want to simultaneously set a stop-loss below the entry price and a take-profit above it. When either condition triggers, the other order must be automatically cancelled. This requires coordination between the order service, matching engine, and risk management to ensure atomic execution semantics and proper margin reservation for both legs of the order.

The implementation must handle edge cases such as gap opens (where price moves through both trigger levels), partial fills on the take-profit leg, and proper event sequencing in the audit trail. The system must also account for T+2 settlement implications when calculating available margin for OCO orders.

### Task 2: Decimal Precision Unification (Refactoring)

Conduct a comprehensive refactoring to unify all numeric precision handling across services. Different services use a mix of Python `float`, `Decimal`, and database-level `FloatField` vs `DecimalField`, causing subtle rounding errors that accumulate over time. This results in penny discrepancies in settlement reconciliation. Refactor all monetary calculations to use `Decimal` with explicit precision rules while maintaining backward-compatible API contracts.

Special attention must be paid to serialization boundaries (JSON encoding/decoding) and Kafka event payloads where numeric values cross service boundaries. The refactoring should establish clear precision rules: 8 decimal places for quantities, 2 decimal places for USD amounts, and 4 decimal places for per-share prices.

### Task 3: Order Book Snapshot Caching (Performance Optimization)

Implement a robust caching strategy for market data service order book snapshots with staggered TTLs, probabilistic early expiration, and request coalescing. The current implementation suffers from cache stampede issues where cache expiration causes all clients to simultaneously hit the matching engine for fresh data. During a cache miss, only one request should fetch from the source while other concurrent requests wait for that result.

The optimization must maintain data freshness guarantees (order book snapshots no older than 100ms for tier-1 symbols) while reducing load on the matching engine by 90% during peak periods. Implement a tiered caching strategy where actively traded symbols (AAPL, GOOGL, MSFT, AMZN) have different refresh policies than less liquid instruments.

### Task 4: FIX Protocol Gateway (API Extension)

Extend the gateway service to accept FIX (Financial Information eXchange) protocol messages for order entry, execution reports, and order status queries. Institutional clients require connectivity via this industry standard protocol. The FIX gateway must translate between FIX message format and the internal order representation, handling field mappings for order types (FIX OrdType to internal order_type), time-in-force values, and execution report generation.

The gateway must maintain FIX session state including sequence number management and heartbeat monitoring. Special consideration is needed for handling FIX-specific features like order amendments (Cancel/Replace), mass cancellation requests, and execution report acknowledgments. The gateway must also implement proper FIX session recovery, replaying missed messages when a client reconnects after a disconnect.

### Task 5: PostgreSQL to TimescaleDB Migration (Migration)

Migrate the event sourcing storage from standard PostgreSQL to TimescaleDB, taking advantage of automatic partitioning by time (hypertables) and built-in compression for historical data. The order events table has grown to billions of rows, and query performance for historical analysis has degraded significantly.

The migration must be performed with zero downtime, implementing a dual-write strategy during the transition period. Configure appropriate chunk intervals (1 day for recent data, compressed weekly chunks for data older than 30 days), and implement continuous aggregates for common query patterns like daily volume summaries and per-symbol event counts. The migration must preserve event ordering guarantees and maintain exactly-once semantics during the dual-write phase.

## Getting Started

```bash
# Start all services
docker compose up -d

# Run tests
python -m pytest tests/ -v
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md), with all tests passing and no performance regressions.
