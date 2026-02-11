# QuantumCore - Greenfield Implementation Tasks

## Overview

QuantumCore provides 3 greenfield implementation tasks requiring new services and modules built from scratch. Each task integrates with the existing microservices architecture using established design patterns and communication channels.

## Environment

- **Language**: Rust
- **Infrastructure**: NATS 2.10, PostgreSQL 15, Redis 7, InfluxDB 2, etcd 3.5
- **Difficulty**: Principal (8-16 hours)

## Tasks

### Task 1: Market Data Normalizer Service

Create a new `normalizer` service that ingests raw market data from multiple exchanges (NYSE, NASDAQ, CME, CBOE, ICE) with heterogeneous formats and outputs normalized, validated quotes and trades to the market data feed.

**Key Components**:
- `Exchange` enum identifying source exchanges
- `RawQuote`/`RawTrade` structs for heterogeneous input formats
- `NormalizedQuote`/`NormalizedTrade` for unified internal format
- `ExchangeConfig` for exchange-specific parsing rules
- `MarketDataNormalizer` trait with quote/trade normalization, symbol mapping, and validation
- Statistics collection for health monitoring

**Integration Points**: Normalized quotes must be compatible with the existing `MarketFeed` system (see `services/market/src/feed.rs`).

### Task 2: Options Greeks Calculator

Create a new `greeks` module within the risk service that calculates options Greeks (Delta, Gamma, Theta, Vega, Rho) using the Black-Scholes model with portfolio-level aggregation.

**Key Components**:
- `OptionContract` and `OptionMarketData` for option specifications
- `OptionGreeks` for individual option Greeks
- `PositionGreeks` for position-level Greeks (scaled by quantity)
- `PortfolioGreeks` for aggregated portfolio exposure
- `BlackScholesCalculator` implementing the `GreeksCalculator` trait
- Implied volatility calculation using Newton-Raphson or bisection

**Integration Points**: Must integrate with the existing `RiskCalculator` in `services/risk/src/calculator.rs` and store results compatible with the positions service.

### Task 3: Trade Execution Reporter

Create a new `reporter` service that generates regulatory reports (FIX execution reports), calculates execution quality metrics, and produces settlement files for compliance.

**Key Components**:
- `ExecutedTrade` input structure with venue and routing metadata
- `ExecutionReport` in FIX 4.4 format with tags 17, 37, 11, 150, 39, 55, 54, etc.
- `ExecutionQualityMetrics` for real-time metrics and SEC Rule 606 reporting
- `SettlementRecord` for settlement files (CSV/Fixed-width/DTCC formats)
- `TradeReporter` trait with recording, report generation, quality calculation, and settlement

**Integration Points**: Trades from matching engine, execution reports publishable via NATS, settlement files compatible with DTCC formats.

## Getting Started

```bash
# Start infrastructure
docker compose up -d

# Build and test new services
cargo test --workspace

# Test specific service
cargo test -p normalizer
cargo test -p reporter
cargo test -p risk --lib greeks
```

## Success Criteria

Each task has 25-30+ unit tests demonstrating functional correctness, performance targets (sub-microsecond calculations), and integration with existing components. See [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) for detailed acceptance criteria per task.
