# QuantumCore - Greenfield Implementation Tasks

These tasks require implementing NEW modules from scratch within the QuantumCore trading platform. Each task builds upon existing architectural patterns and integrates with the current microservices infrastructure.

---

## Task 1: Market Data Normalizer Service

### Overview

Create a new `normalizer` service that ingests raw market data from multiple exchange feeds (with different formats) and outputs normalized, validated quotes and trades to the existing `MarketFeed` system.

### Business Context

QuantumCore receives market data from multiple exchanges (NYSE, NASDAQ, CME, etc.), each with different message formats, timestamp conventions, and field names. The normalizer must transform this heterogeneous data into a unified format for downstream consumption.

### Location

Create new service at: `services/normalizer/`

### Trait Contract

```rust
// services/normalizer/src/normalizer.rs

use anyhow::Result;
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Identifies the source exchange for raw market data
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Exchange {
    NYSE,
    NASDAQ,
    CME,
    CBOE,
    ICE,
    Custom(String),
}

/// Raw quote data as received from an exchange (varies by source)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawQuote {
    pub exchange: Exchange,
    pub raw_symbol: String,
    pub raw_bid: String,        // May be in various formats: "100.50", "10050" (cents), etc.
    pub raw_ask: String,
    pub raw_bid_size: String,   // May be lots, shares, or contracts
    pub raw_ask_size: String,
    pub raw_timestamp: String,  // Exchange-specific timestamp format
    pub raw_sequence: Option<String>,
    pub extra_fields: HashMap<String, String>,
}

/// Raw trade data as received from an exchange
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawTrade {
    pub exchange: Exchange,
    pub raw_symbol: String,
    pub raw_price: String,
    pub raw_quantity: String,
    pub raw_side: Option<String>,   // "B"/"S", "BUY"/"SELL", "1"/"2", etc.
    pub raw_timestamp: String,
    pub raw_trade_id: Option<String>,
    pub extra_fields: HashMap<String, String>,
}

/// Normalized quote in QuantumCore's internal format
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NormalizedQuote {
    pub symbol: String,             // Normalized symbol (e.g., "AAPL" not "AAPL.N")
    pub exchange: Exchange,
    pub bid: Decimal,
    pub ask: Decimal,
    pub bid_size: u64,
    pub ask_size: u64,
    pub timestamp: DateTime<Utc>,
    pub sequence: u64,
    pub is_valid: bool,
    pub validation_errors: Vec<ValidationError>,
}

/// Normalized trade in QuantumCore's internal format
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NormalizedTrade {
    pub symbol: String,
    pub exchange: Exchange,
    pub price: Decimal,
    pub quantity: u64,
    pub side: TradeSide,
    pub timestamp: DateTime<Utc>,
    pub trade_id: String,
    pub is_valid: bool,
    pub validation_errors: Vec<ValidationError>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TradeSide {
    Buy,
    Sell,
    Unknown,
}

/// Validation error types for market data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ValidationError {
    InvalidPrice { reason: String },
    InvalidQuantity { reason: String },
    InvalidTimestamp { reason: String },
    StaleData { age_ms: u64, threshold_ms: u64 },
    CrossedMarket { bid: Decimal, ask: Decimal },
    InvalidSymbol { reason: String },
    MissingRequiredField { field: String },
}

/// Configuration for exchange-specific parsing rules
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExchangeConfig {
    pub exchange: Exchange,
    pub symbol_prefix: Option<String>,
    pub symbol_suffix: Option<String>,
    pub price_multiplier: Decimal,      // e.g., 0.01 if prices are in cents
    pub size_multiplier: u64,           // e.g., 100 if sizes are in lots
    pub timestamp_format: String,       // strftime format or "unix_ms", "unix_us"
    pub timezone: String,
    pub stale_threshold_ms: u64,
}

/// Statistics for monitoring normalizer health
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct NormalizerStats {
    pub quotes_processed: u64,
    pub quotes_valid: u64,
    pub quotes_invalid: u64,
    pub trades_processed: u64,
    pub trades_valid: u64,
    pub trades_invalid: u64,
    pub errors_by_type: HashMap<String, u64>,
    pub latency_p50_us: u64,
    pub latency_p99_us: u64,
}

/// Main trait for the market data normalizer
#[async_trait]
pub trait MarketDataNormalizer: Send + Sync {
    /// Normalize a raw quote from an exchange
    ///
    /// Applies exchange-specific parsing rules, validates the result,
    /// and returns a normalized quote. Invalid quotes are still returned
    /// but marked with `is_valid = false` and populated validation errors.
    fn normalize_quote(&self, raw: RawQuote) -> Result<NormalizedQuote>;

    /// Normalize a raw trade from an exchange
    fn normalize_trade(&self, raw: RawTrade) -> Result<NormalizedTrade>;

    /// Register configuration for an exchange
    ///
    /// Must be called before processing data from that exchange.
    fn register_exchange(&mut self, config: ExchangeConfig) -> Result<()>;

    /// Map an exchange-specific symbol to the internal canonical symbol
    ///
    /// e.g., "AAPL.N" -> "AAPL", "ESH24" -> "ES-2024-03"
    fn map_symbol(&self, exchange: &Exchange, raw_symbol: &str) -> Result<String>;

    /// Add a custom symbol mapping for an exchange
    fn add_symbol_mapping(&mut self, exchange: Exchange, raw_symbol: String, canonical_symbol: String);

    /// Validate a normalized quote against business rules
    ///
    /// Checks for: crossed markets, stale timestamps, price limits, etc.
    fn validate_quote(&self, quote: &NormalizedQuote) -> Vec<ValidationError>;

    /// Validate a normalized trade against business rules
    fn validate_trade(&self, trade: &NormalizedTrade) -> Vec<ValidationError>;

    /// Get current statistics for monitoring
    fn get_stats(&self) -> NormalizerStats;

    /// Reset statistics (typically called on monitoring interval)
    fn reset_stats(&mut self);

    /// Process a batch of raw quotes for efficiency
    async fn normalize_quote_batch(&self, quotes: Vec<RawQuote>) -> Vec<Result<NormalizedQuote>>;

    /// Process a batch of raw trades for efficiency
    async fn normalize_trade_batch(&self, trades: Vec<RawTrade>) -> Vec<Result<NormalizedTrade>>;
}
```

### Required Structs/Enums

All structs and enums are defined in the trait contract above. Additionally, implement:

```rust
/// The main normalizer implementation
pub struct Normalizer {
    configs: HashMap<Exchange, ExchangeConfig>,
    symbol_mappings: HashMap<(Exchange, String), String>,
    stats: Arc<RwLock<NormalizerStats>>,
    stale_threshold_default_ms: u64,
}
```

### Architectural Requirements

1. **Follow existing patterns**: Use `DashMap` for concurrent access (see `services/risk/src/calculator.rs`)
2. **Use `rust_decimal`**: All price calculations must use `Decimal`, never `f64` (see `shared/src/types.rs`)
3. **Error handling**: Use `anyhow::Result` and `thiserror` for custom errors (see `services/matching/src/engine.rs`)
4. **Async patterns**: Use `tokio` and `async-trait` (see `services/market/src/feed.rs`)
5. **Thread safety**: All public types must be `Send + Sync`
6. **Telemetry**: Integrate with `tracing` for structured logging

### Acceptance Criteria

1. **Unit Tests** (minimum 25 tests):
   - Parse prices in various formats (decimal, cents, fractional)
   - Parse timestamps in multiple formats (ISO8601, Unix millis, Unix micros)
   - Symbol normalization for each supported exchange
   - Validation of crossed markets (bid > ask)
   - Validation of stale data
   - Batch processing correctness
   - Thread safety under concurrent access

2. **Integration Points**:
   - Normalized quotes must be compatible with `services/market/src/feed.rs::Quote`
   - Normalized trades must be compatible with `services/market/src/feed.rs::Trade`
   - Stats must be exportable via the gateway service

3. **Performance**:
   - P99 latency < 10 microseconds for single quote normalization
   - Batch processing should be at least 2x faster than individual processing

4. **Test Command**:
   ```bash
   cargo test -p normalizer
   ```

---

## Task 2: Options Greeks Calculator

### Overview

Create a new `greeks` module within the `services/risk` crate that calculates options Greeks (Delta, Gamma, Theta, Vega, Rho) using the Black-Scholes model and provides portfolio-level Greek aggregation.

### Business Context

QuantumCore supports options trading, and risk management requires real-time Greeks calculations. The calculator must handle both individual option positions and aggregate Greeks across portfolios for hedging and exposure monitoring.

### Location

Create new module at: `services/risk/src/greeks.rs` (and update `services/risk/src/lib.rs`)

### Trait Contract

```rust
// services/risk/src/greeks.rs

use anyhow::Result;
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Option type (Call or Put)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum OptionType {
    Call,
    Put,
}

/// Option style (American or European)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum OptionStyle {
    American,
    European,
}

/// Represents an option contract
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptionContract {
    pub symbol: String,                 // Option symbol (e.g., "AAPL230120C00150000")
    pub underlying: String,             // Underlying symbol (e.g., "AAPL")
    pub option_type: OptionType,
    pub option_style: OptionStyle,
    pub strike: Decimal,
    pub expiration: DateTime<Utc>,
    pub multiplier: u32,                // Typically 100 for equity options
}

/// Market data required for Greeks calculation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptionMarketData {
    pub underlying_price: Decimal,
    pub option_price: Decimal,
    pub risk_free_rate: Decimal,        // Annualized (e.g., 0.05 for 5%)
    pub dividend_yield: Decimal,        // Annualized
    pub implied_volatility: Option<Decimal>,  // If known, otherwise calculated
    pub timestamp: DateTime<Utc>,
}

/// Greeks for a single option
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptionGreeks {
    pub delta: Decimal,     // Rate of change of option price w.r.t. underlying price
    pub gamma: Decimal,     // Rate of change of delta w.r.t. underlying price
    pub theta: Decimal,     // Rate of change of option price w.r.t. time (per day)
    pub vega: Decimal,      // Rate of change of option price w.r.t. volatility (per 1%)
    pub rho: Decimal,       // Rate of change of option price w.r.t. interest rate (per 1%)
    pub implied_volatility: Decimal,
    pub calculated_at: DateTime<Utc>,
}

/// Position-level Greeks (Greeks * position size)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PositionGreeks {
    pub symbol: String,
    pub quantity: i64,              // Positive = long, negative = short
    pub notional: Decimal,          // quantity * multiplier * underlying_price
    pub delta_dollars: Decimal,     // Delta exposure in dollar terms
    pub gamma_dollars: Decimal,     // Gamma exposure in dollar terms
    pub theta_dollars: Decimal,     // Daily theta P&L
    pub vega_dollars: Decimal,      // Vega exposure per 1% vol move
    pub rho_dollars: Decimal,       // Rho exposure per 1% rate move
    pub underlying_greeks: OptionGreeks,
}

/// Portfolio-level aggregated Greeks
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortfolioGreeks {
    pub account_id: String,
    pub total_delta_dollars: Decimal,
    pub total_gamma_dollars: Decimal,
    pub total_theta_dollars: Decimal,
    pub total_vega_dollars: Decimal,
    pub total_rho_dollars: Decimal,
    pub by_underlying: HashMap<String, UnderlyingGreeks>,
    pub positions: Vec<PositionGreeks>,
    pub calculated_at: DateTime<Utc>,
}

/// Greeks aggregated by underlying
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UnderlyingGreeks {
    pub underlying: String,
    pub delta_equivalent_shares: Decimal,   // Net delta in share-equivalent terms
    pub gamma_dollars: Decimal,
    pub theta_dollars: Decimal,
    pub vega_dollars: Decimal,
    pub net_position: i64,                  // Sum of all option positions (for this underlying)
}

/// Input for portfolio Greeks calculation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortfolioPosition {
    pub contract: OptionContract,
    pub quantity: i64,
    pub market_data: OptionMarketData,
}

/// Configuration for the Greeks calculator
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GreeksConfig {
    pub iv_calculation_method: IVMethod,
    pub days_per_year: Decimal,             // 252 for trading days, 365 for calendar
    pub iv_precision: u32,                  // Decimal places for IV iteration
    pub iv_max_iterations: u32,             // Max iterations for Newton-Raphson
    pub min_time_to_expiry_days: Decimal,   // Below this, use intrinsic value only
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum IVMethod {
    NewtonRaphson,
    Bisection,
    BrentDekker,
}

/// Error types for Greeks calculation
#[derive(Debug, Clone, thiserror::Error, Serialize, Deserialize)]
pub enum GreeksError {
    #[error("Option has expired")]
    Expired,
    #[error("Invalid strike price: {0}")]
    InvalidStrike(String),
    #[error("Invalid underlying price: {0}")]
    InvalidUnderlyingPrice(String),
    #[error("IV calculation failed to converge after {iterations} iterations")]
    IVConvergenceFailed { iterations: u32 },
    #[error("Negative time to expiry: {days} days")]
    NegativeTimeToExpiry { days: i64 },
    #[error("Market data missing: {field}")]
    MissingMarketData { field: String },
}

/// Main trait for the Greeks calculator
#[async_trait]
pub trait GreeksCalculator: Send + Sync {
    /// Calculate Greeks for a single option
    ///
    /// Uses Black-Scholes model for European options.
    /// For American options, applies early exercise adjustment.
    fn calculate_greeks(
        &self,
        contract: &OptionContract,
        market_data: &OptionMarketData,
    ) -> Result<OptionGreeks, GreeksError>;

    /// Calculate implied volatility from option price
    ///
    /// Uses iterative method (Newton-Raphson or bisection) to find IV
    /// that produces the given option price.
    fn calculate_implied_volatility(
        &self,
        contract: &OptionContract,
        market_data: &OptionMarketData,
    ) -> Result<Decimal, GreeksError>;

    /// Calculate theoretical option price given volatility
    fn calculate_option_price(
        &self,
        contract: &OptionContract,
        underlying_price: Decimal,
        volatility: Decimal,
        risk_free_rate: Decimal,
        dividend_yield: Decimal,
        time_to_expiry_years: Decimal,
    ) -> Result<Decimal, GreeksError>;

    /// Calculate position-level Greeks (scaled by position size)
    fn calculate_position_greeks(
        &self,
        contract: &OptionContract,
        quantity: i64,
        market_data: &OptionMarketData,
    ) -> Result<PositionGreeks, GreeksError>;

    /// Calculate portfolio-level aggregated Greeks
    ///
    /// Aggregates Greeks across all positions, grouped by underlying.
    async fn calculate_portfolio_greeks(
        &self,
        account_id: &str,
        positions: Vec<PortfolioPosition>,
    ) -> Result<PortfolioGreeks>;

    /// Calculate time to expiry in years
    fn time_to_expiry_years(
        &self,
        expiration: DateTime<Utc>,
        as_of: DateTime<Utc>,
    ) -> Result<Decimal, GreeksError>;

    /// Update calculator configuration
    fn update_config(&mut self, config: GreeksConfig);

    /// Get current configuration
    fn get_config(&self) -> GreeksConfig;
}
```

### Required Structs/Enums

All structs and enums are defined in the trait contract above. Additionally, implement:

```rust
/// The main Greeks calculator implementation
pub struct BlackScholesCalculator {
    config: GreeksConfig,
}

impl BlackScholesCalculator {
    /// Standard normal CDF (cumulative distribution function)
    fn norm_cdf(&self, x: Decimal) -> Decimal;

    /// Standard normal PDF (probability density function)
    fn norm_pdf(&self, x: Decimal) -> Decimal;

    /// Calculate d1 and d2 for Black-Scholes
    fn calculate_d1_d2(
        &self,
        spot: Decimal,
        strike: Decimal,
        time: Decimal,
        rate: Decimal,
        dividend: Decimal,
        volatility: Decimal,
    ) -> (Decimal, Decimal);
}
```

### Architectural Requirements

1. **Precision**: All calculations must use `rust_decimal::Decimal` with at least 8 decimal places
2. **No floating point**: Never convert to/from `f64` for financial calculations
3. **Thread safety**: Calculator must be `Send + Sync` for use across async tasks
4. **Integration**: Must integrate with existing `RiskCalculator` in `services/risk/src/calculator.rs`
5. **Caching**: Consider caching frequently calculated values (e.g., `d1`, `d2`)
6. **Validation**: Validate all inputs before calculation

### Acceptance Criteria

1. **Unit Tests** (minimum 30 tests):
   - Black-Scholes pricing accuracy (compare against known values)
   - Greeks accuracy for calls and puts
   - IV calculation convergence
   - Edge cases: at-the-money, deep in/out of the money
   - Edge cases: near expiration
   - Portfolio aggregation correctness
   - Put-call parity validation

2. **Integration Points**:
   - `PositionGreeks` must be storable in the positions service
   - `PortfolioGreeks` must integrate with `RiskMetrics` in the risk service
   - Greeks should be publishable to the market data feed

3. **Performance**:
   - Single option Greeks: < 50 microseconds
   - IV calculation: < 100 microseconds (within 20 iterations)
   - Portfolio of 1000 options: < 50 milliseconds

4. **Mathematical Accuracy**:
   - Greeks must match Bloomberg/Reuters within 0.01%
   - IV must converge to within 0.0001 (0.01%)

5. **Test Command**:
   ```bash
   cargo test -p risk-service --lib greeks
   ```

---

## Task 3: Trade Execution Reporter

### Overview

Create a new `reporter` service that generates regulatory trade reports (FIX-style), aggregates execution quality metrics, and produces end-of-day settlement files.

### Business Context

Trading platforms must generate various reports for regulatory compliance (SEC Rule 606, FINRA), client reporting (execution quality), and operations (settlement files). The reporter service collects trade data and produces formatted output.

### Location

Create new service at: `services/reporter/`

### Trait Contract

```rust
// services/reporter/src/reporter.rs

use anyhow::Result;
use async_trait::async_trait;
use chrono::{DateTime, NaiveDate, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Execution venue where trade was executed
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Venue {
    Exchange(String),       // e.g., "NYSE", "NASDAQ"
    DarkPool(String),       // e.g., "SIGMA-X", "CROSSFINDER"
    Internalized,           // Broker-dealer internalization
    ATS(String),            // Alternative Trading System
}

/// Order routing decision
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RoutingDecision {
    BestExecution,
    ClientDirected,
    PaymentForOrderFlow { venue: String },
    Internalized { reason: String },
}

/// Trade execution details (input to reporter)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutedTrade {
    pub trade_id: String,
    pub order_id: String,
    pub account_id: String,
    pub symbol: String,
    pub side: TradeSide,
    pub quantity: u64,
    pub price: Decimal,
    pub venue: Venue,
    pub execution_time: DateTime<Utc>,
    pub order_received_time: DateTime<Utc>,
    pub routing_decision: RoutingDecision,
    pub is_principal: bool,         // Principal vs agency trade
    pub liquidity_flag: LiquidityFlag,
    pub fees: TradeFees,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TradeSide {
    Buy,
    Sell,
    SellShort,
    SellShortExempt,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum LiquidityFlag {
    Added,          // Passive order that added liquidity
    Removed,        // Aggressive order that removed liquidity
    Routed,         // Routed to another venue
    Auction,        // Executed in auction
    Unknown,
}

/// Fee breakdown for a trade
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TradeFees {
    pub exchange_fee: Decimal,
    pub clearing_fee: Decimal,
    pub sec_fee: Decimal,
    pub taf_fee: Decimal,           // Trading Activity Fee
    pub commission: Decimal,
    pub total: Decimal,
}

/// FIX-style execution report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionReport {
    pub exec_id: String,            // FIX tag 17
    pub order_id: String,           // FIX tag 37
    pub cl_ord_id: String,          // FIX tag 11 (client order ID)
    pub exec_type: ExecType,        // FIX tag 150
    pub ord_status: OrdStatus,      // FIX tag 39
    pub symbol: String,             // FIX tag 55
    pub side: char,                 // FIX tag 54 ('1' = Buy, '2' = Sell)
    pub last_qty: u64,              // FIX tag 32
    pub last_px: Decimal,           // FIX tag 31
    pub cum_qty: u64,               // FIX tag 14
    pub avg_px: Decimal,            // FIX tag 6
    pub transact_time: String,      // FIX tag 60 (UTC timestamp)
    pub exec_venue: String,         // FIX tag 30
    pub text: Option<String>,       // FIX tag 58
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum ExecType {
    New,            // '0'
    PartialFill,    // '1'
    Fill,           // '2'
    Canceled,       // '4'
    Replaced,       // '5'
    Rejected,       // '8'
    Trade,          // 'F'
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum OrdStatus {
    New,            // '0'
    PartiallyFilled,// '1'
    Filled,         // '2'
    Canceled,       // '4'
    Rejected,       // '8'
}

/// Execution quality metrics for a symbol
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionQualityMetrics {
    pub symbol: String,
    pub period_start: DateTime<Utc>,
    pub period_end: DateTime<Utc>,
    pub total_orders: u64,
    pub total_shares: u64,
    pub total_notional: Decimal,
    pub avg_fill_rate: Decimal,         // Percentage of order filled
    pub avg_execution_time_ms: u64,     // Order-to-fill time
    pub price_improvement_rate: Decimal,// Orders with price improvement
    pub avg_price_improvement_bps: Decimal,
    pub effective_spread_bps: Decimal,  // Actual spread paid vs quoted
    pub realized_spread_bps: Decimal,   // Spread after 5-min mark-out
    pub venue_breakdown: HashMap<String, VenueStats>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VenueStats {
    pub venue: String,
    pub order_count: u64,
    pub share_volume: u64,
    pub notional: Decimal,
    pub fill_rate: Decimal,
    pub avg_execution_time_ms: u64,
}

/// SEC Rule 606 quarterly report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Rule606Report {
    pub quarter: String,            // e.g., "2024-Q1"
    pub broker_dealer: String,
    pub s_and_p_500_nms: Vec<Rule606VenueStats>,
    pub other_nms: Vec<Rule606VenueStats>,
    pub options: Vec<Rule606VenueStats>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Rule606VenueStats {
    pub venue: String,
    pub order_pct: Decimal,
    pub net_payment_per_100_shares: Decimal,
    pub material_aspects: String,
}

/// Settlement file record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettlementRecord {
    pub trade_date: NaiveDate,
    pub settlement_date: NaiveDate,
    pub account_id: String,
    pub symbol: String,
    pub cusip: String,
    pub side: char,                 // 'B' or 'S'
    pub quantity: i64,              // Signed: positive = buy, negative = sell
    pub price: Decimal,
    pub gross_amount: Decimal,
    pub net_amount: Decimal,
    pub fees: Decimal,
    pub dtc_settlement_id: Option<String>,
    pub contra_broker: Option<String>,
}

/// Settlement file format
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum SettlementFormat {
    CSV,
    FixedWidth,
    DTCC,           // Depository Trust & Clearing Corporation format
}

/// Report generation options
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReportOptions {
    pub include_header: bool,
    pub date_format: String,        // strftime format
    pub decimal_places: u32,
    pub field_delimiter: Option<char>,
    pub record_delimiter: Option<String>,
}

/// Main trait for the trade execution reporter
#[async_trait]
pub trait TradeReporter: Send + Sync {
    /// Record an executed trade
    ///
    /// Stores the trade for later report generation.
    /// Returns the generated execution report.
    async fn record_trade(&self, trade: ExecutedTrade) -> Result<ExecutionReport>;

    /// Generate FIX-style execution report for a trade
    fn generate_execution_report(&self, trade: &ExecutedTrade) -> ExecutionReport;

    /// Calculate execution quality metrics for a symbol
    ///
    /// Aggregates trades within the specified time range.
    async fn calculate_execution_quality(
        &self,
        symbol: &str,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> Result<ExecutionQualityMetrics>;

    /// Calculate execution quality for all symbols in time range
    async fn calculate_all_execution_quality(
        &self,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> Result<Vec<ExecutionQualityMetrics>>;

    /// Generate SEC Rule 606 quarterly report
    async fn generate_rule_606_report(&self, quarter: &str) -> Result<Rule606Report>;

    /// Generate settlement file for a trade date
    async fn generate_settlement_file(
        &self,
        trade_date: NaiveDate,
        format: SettlementFormat,
        options: ReportOptions,
    ) -> Result<Vec<u8>>;

    /// Get all trades for an account in time range
    async fn get_account_trades(
        &self,
        account_id: &str,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> Result<Vec<ExecutedTrade>>;

    /// Calculate price improvement for a trade
    ///
    /// Compares execution price to NBBO at time of execution.
    fn calculate_price_improvement(
        &self,
        trade: &ExecutedTrade,
        nbbo_bid: Decimal,
        nbbo_ask: Decimal,
    ) -> Decimal;

    /// Get settlement date for a trade (T+1, T+2, etc.)
    fn calculate_settlement_date(&self, trade_date: NaiveDate, security_type: &str) -> NaiveDate;

    /// Subscribe to real-time execution reports
    async fn subscribe_executions(&self) -> tokio::sync::broadcast::Receiver<ExecutionReport>;

    /// Get statistics for the reporter
    fn get_stats(&self) -> ReporterStats;
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ReporterStats {
    pub trades_recorded: u64,
    pub reports_generated: u64,
    pub settlement_files_generated: u64,
    pub errors: u64,
}
```

### Required Structs/Enums

All structs and enums are defined in the trait contract above. Additionally, implement:

```rust
/// The main reporter implementation
pub struct ExecutionReporter {
    trades: DashMap<String, ExecutedTrade>,         // trade_id -> trade
    account_trades: DashMap<String, Vec<String>>,   // account_id -> trade_ids
    symbol_trades: DashMap<String, Vec<String>>,    // symbol -> trade_ids
    exec_broadcast: tokio::sync::broadcast::Sender<ExecutionReport>,
    stats: Arc<RwLock<ReporterStats>>,
    cusip_mapping: HashMap<String, String>,         // symbol -> CUSIP
}
```

### Architectural Requirements

1. **Follow existing patterns**: Use `DashMap` for concurrent trade storage
2. **Use `rust_decimal`**: All monetary calculations must use `Decimal`
3. **Async patterns**: Settlement file generation should be async for large datasets
4. **Broadcast**: Use `tokio::sync::broadcast` for real-time execution reports
5. **Efficiency**: Settlement file generation should stream, not buffer entire file
6. **Time zones**: All timestamps should be UTC internally, formatted on output

### Acceptance Criteria

1. **Unit Tests** (minimum 25 tests):
   - FIX execution report formatting
   - Price improvement calculation
   - Settlement date calculation (handle weekends, holidays)
   - Execution quality metrics aggregation
   - CSV and fixed-width file generation
   - Rule 606 report structure

2. **Integration Points**:
   - Trades must be receivable from the matching engine
   - Settlement files must be compatible with DTCC formats
   - Execution reports must be publishable via NATS

3. **Performance**:
   - Trade recording: < 100 microseconds
   - Execution quality for 10,000 trades: < 100 milliseconds
   - Settlement file for 100,000 trades: < 5 seconds

4. **Compliance**:
   - FIX message format must be valid FIX 4.4
   - Rule 606 report must match SEC specifications
   - Settlement dates must account for market holidays

5. **Test Command**:
   ```bash
   cargo test -p reporter
   ```

---

## General Implementation Guidelines

### Directory Structure (for new services)

```
services/<service_name>/
  Cargo.toml
  src/
    lib.rs          # Module declarations and re-exports
    <module>.rs     # Main implementation
    tests.rs        # Unit tests (or tests/ directory for larger test suites)
```

### Cargo.toml Template

```toml
[package]
name = "<service-name>"
version.workspace = true
edition.workspace = true

[dependencies]
tokio.workspace = true
serde.workspace = true
serde_json.workspace = true
rust_decimal.workspace = true
rust_decimal_macros.workspace = true
tracing.workspace = true
anyhow.workspace = true
thiserror.workspace = true
chrono.workspace = true
dashmap.workspace = true
uuid.workspace = true
async-trait.workspace = true
parking_lot.workspace = true

# Local dependencies
shared = { path = "../../shared" }

[dev-dependencies]
tokio-test = "0.4"
```

### Testing Patterns

Follow the testing patterns in existing services (e.g., `services/matching/src/tests.rs`):

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_feature_name() {
        // Arrange
        let service = Service::new();

        // Act
        let result = service.method().await;

        // Assert
        assert!(result.is_ok());
    }
}
```

### Documentation

Each public type and method must have doc comments explaining:
- Purpose
- Parameters
- Return value
- Error conditions
- Example usage (where helpful)
