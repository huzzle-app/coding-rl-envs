# NexusTrade - Greenfield Implementation Tasks

## Overview

NexusTrade supports three greenfield implementation tasks that require building new microservices from scratch while integrating with the existing trading platform architecture. Each task provides complete interface contracts, data models, and architectural patterns to follow. These tasks test the ability to design and implement production-grade services.

## Environment

- **Language**: Python (FastAPI/Django)
- **Infrastructure**: Kafka, PostgreSQL x3, Redis, Consul
- **Difficulty**: Principal Engineer (20-40 hours per task)

## Tasks

### Task 1: Market Surveillance Engine (Regulatory Compliance)

Implement a real-time market surveillance engine that detects market manipulation patterns in real-time. This service monitors trading activity across all symbols and users, identifying suspicious patterns such as spoofing (large orders placed and cancelled quickly), layering (multiple orders at different price levels), wash trading (self-trading to create artificial volume), and momentum ignition (orders designed to trigger other orders).

**Service Location**: `services/surveillance/`

**Key Components**:
- `SurveillanceEngine` - Main orchestrator for pattern detection
- `PatternDetector` (ABC) - Abstract base for pluggable detectors
- `SurveillanceAlert` - Data model for detected violations
- `TradingProfile` - User/symbol profile for anomaly detection

**Interface Summary**:
```python
class SurveillanceEngine:
    async def process_order_event(event) -> List[SurveillanceAlert]
    async def process_trade_event(event) -> List[SurveillanceAlert]
    async def get_user_profile(user_id, lookback_days) -> Dict
    async def run_historical_scan(start_time, end_time, symbols, users) -> List[SurveillanceAlert]
    def update_thresholds(detector_type, thresholds) -> None
```

**Integration Points**:
- Subscribe to `orders.*` and `trades.*` Kafka topics
- Publish to `surveillance.alerts` topic
- Call Risk service to halt trading on CRITICAL alerts
- Expose REST API for compliance dashboard

**Acceptance Criteria**:
- 30+ unit tests for each detector type
- 15+ integration tests with Kafka and database
- 5+ performance tests (10k events/second without backlog)
- 85%+ line coverage, 80%+ branch coverage
- Historical scan of 1M orders completes in < 60 seconds

---

### Task 2: Portfolio Analytics Service (Risk Management)

Implement a portfolio analytics service that provides real-time and historical risk metrics for user portfolios. The service calculates VaR (Value at Risk), Expected Shortfall, Sharpe Ratio, Beta, correlation matrices, and other portfolio analytics needed for risk management and investment decisions.

**Service Location**: `services/analytics/`

**Key Components**:
- `PortfolioAnalyticsService` - Main service for analytics
- `VaRResult` - Value at Risk calculation result
- `PerformanceMetrics` - Portfolio performance data
- `RiskDecomposition` - Risk breakdown by factors
- `CorrelationMatrix` - Asset correlation data

**Interface Summary**:
```python
class PortfolioAnalyticsService:
    async def get_portfolio_summary(user_id) -> Dict
    async def get_positions(user_id) -> List[PortfolioPosition]
    async def calculate_var(user_id, confidence_level, time_horizon, method) -> VaRResult
    async def get_performance_metrics(user_id, start_date, end_date) -> PerformanceMetrics
    async def get_risk_decomposition(user_id, factors) -> RiskDecomposition
    async def get_correlation_matrix(user_id, symbols, lookback_days) -> CorrelationMatrix
    async def run_stress_test(user_id, scenarios) -> List[Dict]
```

**Integration Points**:
- Subscribe to `trades.*` Kafka topics for position updates
- Call Market Data service for price/return data
- Call Orders service for position data
- Expose REST API for frontend dashboard
- Expose WebSocket for real-time metric updates

**Acceptance Criteria**:
- 40+ unit tests for each calculator type (VaR, Sharpe, correlation)
- 20+ integration tests with external services
- 5+ performance tests (100-position portfolio VaR < 500ms)
- 90%+ line coverage, 85%+ branch coverage
- Decimal precision throughout (no float accumulation errors)

---

### Task 3: Smart Order Router (Best Execution)

Implement a smart order router that optimizes order execution across multiple venues (internal matching engine, external exchanges). The SOR analyzes liquidity, fees, and execution probability to route orders for best execution while maintaining regulatory compliance with SEC Rule 606 and MiFID II.

**Service Location**: `services/routing/`

**Key Components**:
- `SmartOrderRouter` - Main routing orchestrator
- `ExecutionVenue` (ABC) - Abstract base for venue implementations
- `RoutingDecision` - Decision data with rationale and alternatives
- `ExecutionReport` - Execution result with quality metrics
- `VenueStats` - Venue performance statistics

**Interface Summary**:
```python
class SmartOrderRouter:
    async def route_order(order_id, user_id, symbol, side, quantity, price, strategy) -> RoutingDecision
    async def route_and_execute(order_id, user_id, symbol, side, quantity, price) -> ExecutionReport
    async def split_order(order_id, user_id, symbol, side, quantity, max_venues) -> List[Tuple]
    async def get_nbbo(symbol) -> Dict
    async def get_venue_rankings(symbol, side, quantity) -> List[Dict]
    def register_venue(venue) -> None
    async def update_venue_stats(execution_report) -> None
```

**Routing Strategies**:
- `BEST_PRICE` - Prioritize price improvement
- `FASTEST` - Prioritize execution speed
- `LOWEST_COST` - Minimize total cost (fees + spread)
- `SMART` - Adaptive based on order characteristics
- `INTERNALIZE_FIRST` - Try internal matching first
- `EXTERNAL_ONLY` - Route to external venues only

**Integration Points**:
- Call internal Matching Engine for internalization
- Receive orders from Orders service
- Publish to `routing.decisions` and `routing.executions` Kafka topics
- Subscribe to market data for quote updates
- Expose REST API for routing statistics (SEC Rule 606 reporting)

**Acceptance Criteria**:
- 35+ unit tests for each routing strategy
- 15+ integration tests with venue communication
- 5+ performance tests (routing decision < 5ms, NBBO < 2ms)
- 90%+ line coverage, 85%+ branch coverage
- Handle 1000 routing requests/second without degradation

---

## Architectural Patterns to Follow

### Event Consumption
Follow the pattern in `services/matching/main.py` for Kafka consumer setup. Subscribe to relevant topics and process events asynchronously.

### Service Client Pattern
Use `shared/clients/base.py` pattern for inter-service communication. Implement circuit breakers for fault tolerance.

### Event Publishing
Use `shared/events/base.py` for event schema definition. Publish events to Kafka topics for audit trails and inter-service notification.

### Caching Strategy
Follow Redis caching patterns but avoid staleness bugs present in `services/risk/views.py`. Implement proper cache invalidation on data changes.

### Django Models
Follow model patterns in `services/orders/models.py`. Use proper indexing and unique constraints. Use `DecimalField` for financial values.

### API Views
Follow REST API patterns in `services/risk/views.py`. Implement proper pagination, filtering, and error handling.

## Code Quality Requirements

- Follow PEP 8 and include type hints throughout
- Use `Decimal` for all financial calculations (avoid float precision bugs)
- Implement proper error handling with specific exception types
- Include comprehensive docstrings for all public methods
- Use pytest with fixtures for test data
- Mock external services in unit tests
- Use test containers for integration tests

## General Notes

- All tasks should maintain backward compatibility with existing API contracts
- Changes must pass the existing test suite before new functionality is validated
- Event sourcing patterns must be preserved for audit compliance
- Performance changes require before/after benchmarks in documentation
- Security-sensitive changes require attention to input validation and access control

For detailed acceptance criteria and interface contracts, refer to [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
