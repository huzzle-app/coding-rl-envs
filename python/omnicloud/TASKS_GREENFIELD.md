# OmniCloud Greenfield Tasks

These tasks require implementing new modules from scratch, following the existing OmniCloud architectural patterns. Each task builds a complete service with models, views/endpoints, and tests.

---

## Task 1: Cost Allocation Service (Type: New Service)

### Description

Implement a **Cost Allocation Service** that tracks and attributes cloud costs to tenants, projects, and individual resources. The service must handle complex multi-dimensional cost attribution, including shared infrastructure costs (control plane, monitoring, logging), reserved capacity amortization, and tag-based cost grouping.

The service needs to integrate with the existing billing service for usage data and produce detailed cost breakdowns. It should support custom allocation rules (e.g., allocate 70% of shared costs by compute usage, 30% by storage usage) and provide historical cost trends for capacity planning. The allocation engine must handle edge cases like new tenants with zero usage, tenants that are deleted mid-billing-period, and resources that change owners.

This service will be consumed by the billing service for invoice generation, the monitor service for cost anomaly alerting, and directly by tenant administrators through the gateway API.

### Interface Contract

```python
# services/cost_allocation/models.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from decimal import Decimal
from enum import Enum
import uuid
import time


class AllocationStrategy(Enum):
    """Strategy for allocating shared costs."""
    PROPORTIONAL = "proportional"      # Split by usage ratio
    EQUAL = "equal"                    # Split equally among tenants
    TIERED = "tiered"                  # Split based on plan tier
    CUSTOM = "custom"                  # Custom weights per tenant


class CostCategory(Enum):
    """Categories of cloud costs."""
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    SHARED = "shared"
    RESERVED = "reserved"
    SUPPORT = "support"


@dataclass
class AllocationRule:
    """A rule for allocating costs to tenants."""
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: CostCategory = CostCategory.SHARED
    strategy: AllocationStrategy = AllocationStrategy.PROPORTIONAL
    weight_by_category: Dict[str, Decimal] = field(default_factory=dict)
    effective_from: float = field(default_factory=time.time)
    effective_until: Optional[float] = None
    is_active: bool = True


@dataclass
class CostAllocationResult:
    """Result of a cost allocation calculation."""
    allocation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    period_start: float = 0.0
    period_end: float = 0.0
    breakdown: Dict[str, Decimal] = field(default_factory=dict)
    total_allocated: Decimal = Decimal("0")
    allocation_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostTag:
    """Tag for resource-level cost grouping."""
    key: str = ""
    value: str = ""


# services/cost_allocation/service.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime


@dataclass
class CostAllocationService:
    """
    Service for allocating cloud costs to tenants and resources.

    Integrates with:
    - billing service: Gets raw usage data and costs
    - tenants service: Gets tenant metadata and quotas
    - monitor service: Publishes cost anomaly events
    """

    def calculate_tenant_allocation(
        self,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
        rules: Optional[List[AllocationRule]] = None,
    ) -> CostAllocationResult:
        """
        Calculate cost allocation for a single tenant.

        Args:
            tenant_id: The tenant to calculate costs for
            period_start: Start of billing period (timezone-aware)
            period_end: End of billing period (timezone-aware)
            rules: Optional custom rules (uses defaults if not provided)

        Returns:
            CostAllocationResult with detailed breakdown by category

        Raises:
            ValueError: If tenant doesn't exist or period is invalid
        """
        ...

    def allocate_shared_costs(
        self,
        shared_cost: Decimal,
        category: CostCategory,
        period_start: datetime,
        period_end: datetime,
        strategy: AllocationStrategy = AllocationStrategy.PROPORTIONAL,
    ) -> Dict[str, Decimal]:
        """
        Allocate shared infrastructure costs across all active tenants.

        Args:
            shared_cost: Total shared cost to allocate
            category: Cost category for this allocation
            period_start: Start of billing period
            period_end: End of billing period
            strategy: Allocation strategy to use

        Returns:
            Dict mapping tenant_id to allocated cost

        Note:
            Sum of all allocations must equal shared_cost (no rounding loss)
        """
        ...

    def calculate_amortized_reserved_costs(
        self,
        tenant_id: str,
        reservation_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Decimal:
        """
        Calculate amortized cost for reserved capacity.

        Reserved capacity is paid upfront but must be amortized over
        the reservation period for accurate cost attribution.

        Args:
            tenant_id: Tenant owning the reservation
            reservation_id: The reservation to amortize
            period_start: Current billing period start
            period_end: Current billing period end

        Returns:
            Decimal amount to attribute for this period
        """
        ...

    def get_cost_by_tags(
        self,
        tenant_id: str,
        tags: List[CostTag],
        period_start: datetime,
        period_end: datetime,
    ) -> Dict[str, Decimal]:
        """
        Get costs grouped by resource tags.

        Enables showback/chargeback to internal teams using tags
        like "team:platform", "environment:production".

        Args:
            tenant_id: Tenant to query
            tags: List of tag key-value pairs to filter/group by
            period_start: Start of period
            period_end: End of period

        Returns:
            Dict mapping tag combination to total cost
        """
        ...

    def detect_cost_anomalies(
        self,
        tenant_id: str,
        current_period_cost: Decimal,
        lookback_periods: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalous cost increases compared to historical baseline.

        Args:
            tenant_id: Tenant to check
            current_period_cost: Cost for current period
            lookback_periods: Number of previous periods to compare against

        Returns:
            List of anomaly records with severity and suggested causes
        """
        ...

    def create_allocation_rule(self, rule: AllocationRule) -> str:
        """
        Create a new cost allocation rule.

        Args:
            rule: The allocation rule to create

        Returns:
            The rule_id of the created rule
        """
        ...

    def get_historical_costs(
        self,
        tenant_id: str,
        periods: int = 12,
        granularity: str = "monthly",
    ) -> List[CostAllocationResult]:
        """
        Get historical cost allocations for trend analysis.

        Args:
            tenant_id: Tenant to query
            periods: Number of periods to retrieve
            granularity: "daily", "weekly", or "monthly"

        Returns:
            List of CostAllocationResult ordered by period (oldest first)
        """
        ...
```

### Required Models

1. **AllocationRule** - Defines how costs are split among tenants
2. **CostAllocationResult** - Result of an allocation calculation
3. **CostTag** - For tag-based cost grouping
4. **CostCategory** (Enum) - Categories: compute, storage, network, shared, reserved, support
5. **AllocationStrategy** (Enum) - Strategies: proportional, equal, tiered, custom
6. **CostAnomaly** - Detected cost spike with severity and metadata

### Acceptance Criteria

- [ ] Service correctly allocates shared costs with zero rounding loss (sum of allocations == shared_cost)
- [ ] Handles edge case of new tenant with zero usage (should not divide by zero)
- [ ] Handles mid-period tenant deletion (prorated allocation)
- [ ] Reserved capacity amortization spreads cost evenly across reservation period
- [ ] Tag-based grouping supports multiple tags with AND semantics
- [ ] Cost anomaly detection uses statistical thresholds (>2 std dev from mean)
- [ ] All monetary calculations use Decimal, not float
- [ ] Integrates with billing service via ServiceClient pattern (shared/clients/base.py)
- [ ] Unit tests cover all edge cases (min 60 tests)
- [ ] Integration tests verify billing service integration

### Test Command

```bash
python -m pytest tests/unit/test_cost_allocation.py tests/integration/test_cost_allocation_billing.py -v
```

---

## Task 2: Infrastructure Drift Detector (Type: New Module in shared/infra/)

### Description

Implement an **Infrastructure Drift Detector** module that detects configuration drift between the desired state (defined in infrastructure-as-code) and actual state (observed from cloud providers). This module extends the existing `shared/infra/state.py` StateManager to provide advanced drift detection, categorization, and remediation recommendations.

Unlike the simple `detect_drift()` method in StateManager that uses naive dict comparison, this detector must handle semantic equivalence (e.g., "8080" == 8080 for ports), ordered vs unordered collections (e.g., security group rules order doesn't matter), and nested object comparison. It should categorize drift by severity (cosmetic, functional, security-impacting) and provide actionable remediation steps.

The detector integrates with the reconciler (shared/infra/reconciler.py) to trigger automatic remediation for low-severity drifts while escalating security-impacting drifts to the compliance service for human review.

### Interface Contract

```python
# shared/infra/drift_detector.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from enum import Enum
import uuid
import time


class DriftSeverity(Enum):
    """Severity classification for detected drift."""
    COSMETIC = "cosmetic"          # Naming, tags only - no functional impact
    FUNCTIONAL = "functional"       # Affects behavior but not security
    SECURITY = "security"           # Security-impacting drift (missing firewall rules, etc.)
    CRITICAL = "critical"           # Immediate action required (exposed secrets, etc.)


class DriftType(Enum):
    """Type of configuration drift."""
    VALUE_CHANGED = "value_changed"
    KEY_ADDED = "key_added"
    KEY_REMOVED = "key_removed"
    TYPE_MISMATCH = "type_mismatch"
    RESOURCE_MISSING = "resource_missing"
    RESOURCE_EXTRA = "resource_extra"


@dataclass
class DriftRecord:
    """Record of a single configuration drift."""
    drift_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_type: str = ""
    tenant_id: str = ""
    drift_type: DriftType = DriftType.VALUE_CHANGED
    severity: DriftSeverity = DriftSeverity.FUNCTIONAL
    config_path: str = ""  # e.g., "security_groups[0].rules[2].port"
    desired_value: Any = None
    actual_value: Any = None
    detected_at: float = field(default_factory=time.time)
    remediation_action: str = ""
    auto_remediable: bool = False


@dataclass
class DriftReport:
    """Complete drift report for a resource or tenant."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    resource_ids: List[str] = field(default_factory=list)
    drifts: List[DriftRecord] = field(default_factory=list)
    scan_started_at: float = 0.0
    scan_completed_at: float = 0.0
    summary: Dict[str, int] = field(default_factory=dict)  # Counts by severity


@dataclass
class DriftDetector:
    """
    Detects and categorizes configuration drift.

    Integrates with:
    - shared/infra/state.py: Gets desired vs actual state
    - shared/infra/reconciler.py: Triggers auto-remediation
    - services/compliance: Escalates security drifts
    """

    # Custom comparators for semantic equivalence
    comparators: Dict[str, Callable[[Any, Any], bool]] = field(default_factory=dict)
    # Fields where order doesn't matter (treat as sets)
    unordered_fields: Set[str] = field(default_factory=set)
    # Severity classification rules
    severity_rules: Dict[str, DriftSeverity] = field(default_factory=dict)

    def detect_resource_drift(
        self,
        resource_id: str,
        desired_config: Dict[str, Any],
        actual_config: Dict[str, Any],
    ) -> List[DriftRecord]:
        """
        Detect drift between desired and actual configuration.

        Handles:
        - Type coercion (string "8080" == int 8080)
        - Unordered collections (security group rules)
        - Nested object comparison
        - None vs missing key distinction

        Args:
            resource_id: ID of the resource being checked
            desired_config: Expected configuration from IaC
            actual_config: Observed configuration from provider

        Returns:
            List of DriftRecord for each detected difference
        """
        ...

    def scan_tenant_resources(
        self,
        tenant_id: str,
        resource_types: Optional[List[str]] = None,
    ) -> DriftReport:
        """
        Scan all resources for a tenant and generate drift report.

        Args:
            tenant_id: Tenant to scan
            resource_types: Optional filter for specific resource types

        Returns:
            DriftReport with all detected drifts
        """
        ...

    def classify_drift_severity(
        self,
        drift: DriftRecord,
    ) -> DriftSeverity:
        """
        Classify the severity of a detected drift.

        Uses rules like:
        - Port changes on security groups -> SECURITY
        - Tag-only changes -> COSMETIC
        - Instance type changes -> FUNCTIONAL
        - Ingress 0.0.0.0/0 added -> CRITICAL

        Args:
            drift: The drift record to classify

        Returns:
            Appropriate DriftSeverity level
        """
        ...

    def generate_remediation_plan(
        self,
        drifts: List[DriftRecord],
    ) -> List[Dict[str, Any]]:
        """
        Generate remediation actions for detected drifts.

        Args:
            drifts: List of drifts to remediate

        Returns:
            List of remediation action objects with:
            - action_type: "update", "delete", "create"
            - resource_id: Target resource
            - config_changes: Dict of changes to apply
            - requires_approval: bool for security-impacting changes
        """
        ...

    def register_comparator(
        self,
        field_pattern: str,
        comparator: Callable[[Any, Any], bool],
    ) -> None:
        """
        Register a custom comparator for semantic equivalence.

        Example: Register comparator for ports that treats "8080" == 8080

        Args:
            field_pattern: Glob pattern for field paths (e.g., "*.port")
            comparator: Function (desired, actual) -> bool (True if equivalent)
        """
        ...

    def mark_field_unordered(self, field_pattern: str) -> None:
        """
        Mark a field as unordered (compare as set, not list).

        Args:
            field_pattern: Glob pattern for field paths (e.g., "*.rules")
        """
        ...

    def add_severity_rule(
        self,
        resource_type: str,
        field_pattern: str,
        severity: DriftSeverity,
    ) -> None:
        """
        Add a rule for classifying drift severity.

        Args:
            resource_type: Resource type this rule applies to
            field_pattern: Field pattern (e.g., "ingress_rules.*.cidr")
            severity: Severity to assign when this field drifts
        """
        ...

    def get_drift_history(
        self,
        resource_id: str,
        since: Optional[float] = None,
    ) -> List[DriftRecord]:
        """
        Get historical drift records for a resource.

        Args:
            resource_id: Resource to query
            since: Optional timestamp to filter (only drifts after this time)

        Returns:
            List of historical drift records, newest first
        """
        ...
```

### Required Models

1. **DriftRecord** - Individual drift occurrence with path, values, severity
2. **DriftReport** - Aggregated report for tenant/resource scan
3. **DriftSeverity** (Enum) - cosmetic, functional, security, critical
4. **DriftType** (Enum) - value_changed, key_added, key_removed, type_mismatch, resource_missing, resource_extra
5. **RemediationAction** - Action to fix drift with approval requirements

### Acceptance Criteria

- [ ] Semantic comparison handles type coercion (string/int ports, bool "true"/True)
- [ ] Unordered field comparison treats lists as sets (security group rules)
- [ ] Nested object drift reports full path (e.g., "network.subnets[0].cidr")
- [ ] None vs missing key treated as distinct drift types
- [ ] Severity classification uses configurable rules
- [ ] Security-impacting drifts (ingress 0.0.0.0/0) classified as CRITICAL
- [ ] Remediation plan marks security changes as requiring approval
- [ ] Integrates with existing StateManager.detect_drift() as enhanced replacement
- [ ] Drift history persisted for audit trail
- [ ] Unit tests cover all comparison edge cases (min 80 tests)

### Test Command

```bash
python -m pytest tests/unit/test_drift_detector.py tests/integration/test_drift_reconciler.py -v
```

---

## Task 3: Capacity Forecasting Engine (Type: New Service)

### Description

Implement a **Capacity Forecasting Engine** that predicts future resource needs based on historical usage patterns. The engine uses time-series analysis to forecast compute, storage, and network capacity requirements, enabling proactive scaling decisions and reserved capacity planning.

The engine must handle multiple forecasting scenarios: organic growth projections, seasonal pattern detection (e.g., e-commerce holiday spikes), and what-if analysis for new product launches. It should integrate with the compute service's scheduler to provide capacity recommendations and with the billing service to estimate future costs.

The forecasting models should support configurable confidence intervals (e.g., P50, P90, P99 predictions) and automatically detect regime changes (e.g., post-migration usage patterns differ from pre-migration). The engine publishes forecasts to the monitor service for capacity alert generation.

### Interface Contract

```python
# services/capacity_forecast/models.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from enum import Enum
import uuid
import time


class ResourceMetric(Enum):
    """Metrics that can be forecasted."""
    CPU_UTILIZATION = "cpu_utilization"
    MEMORY_UTILIZATION = "memory_utilization"
    STORAGE_USED_GB = "storage_used_gb"
    NETWORK_BANDWIDTH_MBPS = "network_bandwidth_mbps"
    INSTANCE_COUNT = "instance_count"
    REQUEST_RATE = "request_rate"


class ForecastGranularity(Enum):
    """Time granularity for forecasts."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class SeasonalityType(Enum):
    """Types of seasonal patterns."""
    NONE = "none"
    DAILY = "daily"           # Intra-day patterns (peak hours)
    WEEKLY = "weekly"         # Day-of-week patterns
    MONTHLY = "monthly"       # Monthly cycles
    YEARLY = "yearly"         # Annual patterns (holidays)


@dataclass
class UsageDataPoint:
    """A single usage measurement."""
    timestamp: float = 0.0
    value: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ForecastResult:
    """Result of a capacity forecast."""
    forecast_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    metric: ResourceMetric = ResourceMetric.CPU_UTILIZATION
    granularity: ForecastGranularity = ForecastGranularity.DAILY

    # Forecast data points
    predictions: List[Tuple[float, float]] = field(default_factory=list)  # (timestamp, value)

    # Confidence intervals
    lower_bound_p10: List[float] = field(default_factory=list)
    upper_bound_p90: List[float] = field(default_factory=list)

    # Metadata
    model_type: str = ""
    seasonality_detected: SeasonalityType = SeasonalityType.NONE
    confidence_score: float = 0.0  # 0.0 to 1.0
    generated_at: float = field(default_factory=time.time)


@dataclass
class CapacityRecommendation:
    """Recommendation for capacity changes."""
    recommendation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    resource_type: str = ""
    current_capacity: float = 0.0
    recommended_capacity: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    projected_exhaustion_date: Optional[float] = None
    estimated_monthly_cost_delta: Decimal = Decimal("0")


# services/capacity_forecast/engine.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal


@dataclass
class CapacityForecastEngine:
    """
    Engine for forecasting capacity needs.

    Integrates with:
    - services/compute: Gets current capacity and usage data
    - services/billing: Estimates cost impact of recommendations
    - services/monitor: Publishes capacity alerts
    """

    # Model configuration
    default_lookback_days: int = 90
    default_forecast_days: int = 30
    confidence_levels: List[float] = field(default_factory=lambda: [0.1, 0.5, 0.9])

    def forecast_metric(
        self,
        tenant_id: str,
        metric: ResourceMetric,
        horizon_days: int = 30,
        granularity: ForecastGranularity = ForecastGranularity.DAILY,
    ) -> ForecastResult:
        """
        Generate a forecast for a specific metric.

        Args:
            tenant_id: Tenant to forecast for
            metric: The metric to forecast
            horizon_days: How far into the future to predict
            granularity: Time granularity for predictions

        Returns:
            ForecastResult with predictions and confidence intervals

        Raises:
            ValueError: If insufficient historical data (<14 days)
        """
        ...

    def detect_seasonality(
        self,
        data_points: List[UsageDataPoint],
    ) -> Tuple[SeasonalityType, float]:
        """
        Detect seasonal patterns in usage data.

        Uses autocorrelation to detect periodic patterns at
        daily, weekly, monthly, and yearly intervals.

        Args:
            data_points: Historical usage data

        Returns:
            Tuple of (detected seasonality type, confidence score)
        """
        ...

    def detect_regime_change(
        self,
        data_points: List[UsageDataPoint],
        sensitivity: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """
        Detect significant changes in usage patterns.

        Identifies points where the underlying data distribution
        changed (e.g., post-migration, new feature launch).

        Args:
            data_points: Historical usage data
            sensitivity: Detection sensitivity (0.0 to 1.0)

        Returns:
            List of regime change events with timestamp and magnitude
        """
        ...

    def generate_capacity_recommendations(
        self,
        tenant_id: str,
        forecast: ForecastResult,
        headroom_percent: float = 20.0,
    ) -> List[CapacityRecommendation]:
        """
        Generate actionable capacity recommendations.

        Args:
            tenant_id: Tenant to recommend for
            forecast: The forecast to base recommendations on
            headroom_percent: Buffer above predicted usage

        Returns:
            List of CapacityRecommendation ordered by urgency
        """
        ...

    def project_capacity_exhaustion(
        self,
        tenant_id: str,
        metric: ResourceMetric,
        current_capacity: float,
    ) -> Optional[float]:
        """
        Project when current capacity will be exhausted.

        Args:
            tenant_id: Tenant to project for
            metric: The metric to analyze
            current_capacity: Current maximum capacity

        Returns:
            Timestamp when capacity will be exhausted, or None if never
        """
        ...

    def run_what_if_scenario(
        self,
        tenant_id: str,
        scenario: Dict[str, Any],
    ) -> Dict[str, ForecastResult]:
        """
        Run a what-if scenario for capacity planning.

        Scenarios can include:
        - {"traffic_multiplier": 2.0} - Double current traffic
        - {"new_workload": {"cpu": 100, "memory_gb": 500}} - Add workload
        - {"remove_workload_id": "xyz"} - Remove existing workload

        Args:
            tenant_id: Tenant for scenario
            scenario: Scenario parameters

        Returns:
            Dict mapping metric to modified forecast
        """
        ...

    def estimate_reserved_capacity_savings(
        self,
        tenant_id: str,
        reservation_term_months: int = 12,
    ) -> Dict[str, Any]:
        """
        Estimate savings from purchasing reserved capacity.

        Compares on-demand costs to reserved pricing based on
        forecasted stable baseline usage.

        Args:
            tenant_id: Tenant to analyze
            reservation_term_months: Commitment term (12 or 36)

        Returns:
            Dict with:
            - recommended_reserved_units: Amount to reserve
            - estimated_savings: Decimal savings vs on-demand
            - break_even_utilization: Utilization needed to break even
        """
        ...

    def get_historical_accuracy(
        self,
        tenant_id: str,
        metric: ResourceMetric,
        lookback_forecasts: int = 10,
    ) -> Dict[str, float]:
        """
        Calculate historical forecast accuracy metrics.

        Args:
            tenant_id: Tenant to analyze
            metric: Metric to check accuracy for
            lookback_forecasts: Number of past forecasts to evaluate

        Returns:
            Dict with MAPE, RMSE, and bias metrics
        """
        ...

    def train_custom_model(
        self,
        tenant_id: str,
        metric: ResourceMetric,
        training_data: List[UsageDataPoint],
        model_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Train a custom forecasting model for a tenant.

        Allows tenants with unique patterns to have specialized models.

        Args:
            tenant_id: Tenant to train model for
            metric: Metric this model will forecast
            training_data: Historical data for training
            model_config: Optional model hyperparameters

        Returns:
            model_id of the trained model
        """
        ...
```

### Required Models

1. **UsageDataPoint** - Single usage measurement with timestamp and value
2. **ForecastResult** - Predictions with confidence intervals
3. **CapacityRecommendation** - Actionable recommendation with cost impact
4. **ResourceMetric** (Enum) - cpu_utilization, memory_utilization, storage_used_gb, network_bandwidth_mbps, instance_count, request_rate
5. **ForecastGranularity** (Enum) - hourly, daily, weekly, monthly
6. **SeasonalityType** (Enum) - none, daily, weekly, monthly, yearly
7. **RegimeChangeEvent** - Detected pattern shift with timestamp and magnitude

### Acceptance Criteria

- [ ] Forecasts use at least 14 days of historical data (error if insufficient)
- [ ] Seasonality detection correctly identifies daily/weekly patterns
- [ ] Regime change detection identifies significant distribution shifts
- [ ] Confidence intervals widen appropriately for longer horizons
- [ ] Capacity exhaustion projection uses P90 forecast (conservative)
- [ ] What-if scenarios correctly modify baseline forecast
- [ ] Reserved capacity recommendations include break-even analysis
- [ ] Historical accuracy tracking enables model quality monitoring
- [ ] Integrates with compute scheduler via ServiceClient pattern
- [ ] Cost estimates use billing service rates (Decimal precision)
- [ ] Unit tests cover edge cases and model accuracy (min 70 tests)
- [ ] Integration tests verify compute and billing service integration

### Test Command

```bash
python -m pytest tests/unit/test_capacity_forecast.py tests/integration/test_capacity_compute.py -v
```

---

## Implementation Notes

### Architectural Patterns to Follow

1. **Service Structure**: Each service should mirror existing services (e.g., `services/billing/`):
   - `models.py` - Data classes with `@dataclass` decorator
   - `views.py` or `main.py` - FastAPI endpoints (if API exposed)
   - `settings.py` - Service configuration
   - `__init__.py` - Package initialization

2. **Shared Module Structure**: Modules in `shared/infra/` follow:
   - Single responsibility classes with `@dataclass`
   - Type hints on all methods
   - Docstrings explaining bugs/edge cases (for debug environment)

3. **Inter-Service Communication**: Use `ServiceClient` from `shared/clients/base.py`:
   - Circuit breaker pattern for resilience
   - Correlation ID propagation for tracing
   - Tenant ID in headers for multi-tenancy

4. **Monetary Calculations**: Always use `Decimal` from Python's decimal module:
   - Never use `float` for money
   - Explicit rounding with `quantize()`

5. **Time Handling**: Use timezone-aware datetimes:
   - `datetime.now(timezone.utc)` not `datetime.now()`
   - Store timestamps as floats (Unix epoch) for consistency

### Test Patterns

Follow existing test patterns in `tests/unit/`:
- Use `pytest` with fixtures
- Class-based test organization by feature
- Descriptive test names explaining the scenario
- Mock external services with `unittest.mock.patch`
