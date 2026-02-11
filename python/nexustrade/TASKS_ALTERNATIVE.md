# NexusTrade - Alternative Task Specifications

This document contains alternative task specifications for the NexusTrade distributed trading platform. Each task represents a realistic feature development, refactoring, or enhancement scenario that a trading platform engineering team might encounter.

---

## Task 1: Stop-Loss and Take-Profit Order Types (Feature Development)

### Description

The NexusTrade matching engine currently supports basic order types (market, limit, stop, stop_limit), but institutional clients are requesting advanced conditional order types. Implement OCO (One-Cancels-Other) orders that combine a stop-loss and take-profit into a single atomic order group.

When a position is opened, traders want to simultaneously set a stop-loss below the entry price and a take-profit above it. When either condition triggers, the other order must be automatically cancelled. This requires coordination between the order service, matching engine, and risk management to ensure atomic execution semantics and proper margin reservation for both legs of the order.

The implementation must handle edge cases such as gap opens (where price moves through both trigger levels), partial fills on the take-profit leg, and proper event sequencing in the audit trail. The system must also account for T+2 settlement implications when calculating available margin for OCO orders.

### Acceptance Criteria

- OCO orders can be created with linked stop-loss and take-profit price levels
- When one leg executes, the other leg is automatically cancelled within 100ms
- Gap scenarios (price moves through both levels) execute the more favorable leg first
- Partial fills on one leg reduce the quantity on the other leg proportionally
- OCO orders correctly reserve margin for the maximum potential exposure (not both legs)
- Event sourcing captures the complete lifecycle with proper sequencing
- Risk service validates both legs against user position limits before acceptance
- Audit logs capture the linkage between OCO leg orders

### Test Command

```bash
python -m pytest tests/ -v -k "oco or stop_loss or take_profit"
```

---

## Task 2: Decimal Precision Unification (Refactoring)

### Description

The NexusTrade platform has accumulated technical debt around numeric precision handling. Different services use a mix of Python `float`, `Decimal`, and database-level `FloatField` vs `DecimalField`. This inconsistency causes subtle rounding errors that accumulate over time, resulting in penny discrepancies in settlement reconciliation.

Conduct a comprehensive refactoring to unify all monetary calculations on `Decimal` with explicit precision rules. This includes order prices, fill quantities, commissions, margin calculations, VaR computations, and P&L tracking. The refactoring must be backward-compatible with existing API contracts while ensuring internal calculations use consistent precision.

Special attention must be paid to the serialization boundaries where JSON encoding/decoding occurs, as well as the Kafka event payloads where numeric values cross service boundaries. The refactoring should establish clear precision rules: 8 decimal places for quantities, 2 decimal places for USD amounts, and 4 decimal places for per-share prices.

### Acceptance Criteria

- All monetary calculations use `Decimal` type internally, never `float`
- Database models use `DecimalField` with explicit `max_digits` and `decimal_places`
- JSON serialization preserves precision using string representation for decimals
- Kafka events encode decimal values as strings with explicit precision
- Commission calculations accumulate without rounding errors over 10,000+ trades
- Settlement reconciliation matches to the penny after full trading day simulation
- VaR calculations handle extreme values without floating-point overflow
- API responses maintain backward compatibility (numeric JSON values still accepted)

### Test Command

```bash
python -m pytest tests/ -v -k "decimal or precision or rounding or commission"
```

---

## Task 3: Order Book Snapshot Caching (Performance Optimization)

### Description

The market data service experiences severe performance degradation during high-volatility periods when many clients simultaneously request order book snapshots. The current implementation suffers from cache stampede issues where cache expiration causes all clients to simultaneously hit the matching engine for fresh data.

Implement a robust caching strategy with staggered TTLs, probabilistic early expiration, and request coalescing. The solution should ensure that during a cache miss, only one request fetches from the source while other concurrent requests wait for that result. Additionally, implement a warm-up mechanism that pre-populates cache for actively traded symbols before market open.

The optimization must maintain data freshness guarantees (order book snapshots no older than 100ms for tier-1 symbols) while reducing load on the matching engine by 90% during peak periods. Consider implementing a tiered caching strategy where actively traded symbols have different refresh policies than less liquid instruments.

### Acceptance Criteria

- Cache stampede eliminated: concurrent misses result in single source fetch
- TTLs randomized with jitter to prevent synchronized expiration
- Request coalescing deduplicates identical in-flight requests
- Tier-1 symbols (AAPL, GOOGL, MSFT, AMZN) maintain sub-100ms freshness
- Pre-market warm-up populates cache 5 minutes before market open
- Matching engine load reduced by 90% during simulated volatility spike
- Stale-while-revalidate pattern serves slightly stale data during refresh
- Hot symbol detection automatically promotes frequently accessed symbols

### Test Command

```bash
python -m pytest tests/ -v -k "cache or stampede or orderbook or performance"
```

---

## Task 4: FIX Protocol Gateway (API Extension)

### Description

Institutional clients require connectivity via the FIX (Financial Information eXchange) protocol, the industry standard for electronic trading. Extend the gateway service to accept FIX 4.4 messages for order entry, execution reports, and order status queries.

The FIX gateway must translate between FIX message format and the internal order representation, handling field mappings for order types (FIX OrdType to internal order_type), time-in-force values (FIX TimeInForce to internal TIF), and execution report generation. The gateway must maintain FIX session state including sequence number management and heartbeat monitoring.

Special consideration is needed for handling FIX-specific features like order amendments (via Cancel/Replace), mass cancellation requests, and execution report acknowledgments. The gateway must also implement proper FIX session recovery, replaying missed messages when a client reconnects after a disconnect.

### Acceptance Criteria

- FIX 4.4 Logon/Logout handshake with sequence number validation
- NewOrderSingle (D) messages create orders in the matching engine
- ExecutionReport (8) messages generated for all order state transitions
- OrderCancelRequest (F) and OrderCancelReplaceRequest (G) supported
- OrderStatusRequest (H) returns current order state
- Heartbeat (0) and TestRequest (1) maintain session liveness
- Session recovery replays messages from specified sequence number
- FIX field validation rejects malformed messages with appropriate reject reason
- Concurrent FIX sessions supported with independent sequence numbers

### Test Command

```bash
python -m pytest tests/ -v -k "fix or protocol or gateway or session"
```

---

## Task 5: PostgreSQL to TimescaleDB Migration (Migration)

### Description

The order events table has grown to billions of rows, and query performance for historical analysis has degraded significantly. Migrate the event sourcing storage from standard PostgreSQL to TimescaleDB, taking advantage of automatic partitioning by time (hypertables) and built-in compression for historical data.

The migration must be performed with zero downtime, implementing a dual-write strategy during the transition period. New events are written to both the old and new storage, while a background process migrates historical data. Once migration is verified complete, reads are switched to TimescaleDB and the dual-write is disabled.

Configure appropriate chunk intervals (1 day for recent data, compressed weekly chunks for data older than 30 days), and implement continuous aggregates for common query patterns like daily volume summaries and per-symbol event counts. The migration must preserve event ordering guarantees and maintain exactly-once semantics during the dual-write phase.

### Acceptance Criteria

- TimescaleDB hypertable created with time-based partitioning on event timestamp
- Dual-write mechanism ensures no events lost during migration window
- Historical data migrated with verified row counts and checksum validation
- Chunk compression enabled for data older than 30 days
- Continuous aggregates pre-compute daily volume and trade count summaries
- Event ordering preserved: sequence numbers monotonically increasing per aggregate
- Query performance improved 10x for time-range queries on historical data
- Rollback procedure documented and tested for migration failure scenarios

### Test Command

```bash
python -m pytest tests/ -v -k "timescale or migration or event_store or hypertable"
```

---

## General Notes

- All tasks should maintain backward compatibility with existing API contracts
- Changes must pass the existing test suite before new functionality is validated
- Event sourcing patterns must be preserved for audit compliance
- Performance changes require before/after benchmarks in the PR description
- Security-sensitive changes require review from the platform security team
