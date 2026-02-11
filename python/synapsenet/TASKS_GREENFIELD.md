# SynapseNet Greenfield Tasks

This document defines greenfield implementation tasks for SynapseNet, an ML/AI Model Serving & Training Platform. Each task requires implementing a new module from scratch while following the existing architectural patterns.

---

## Task 1: Model A/B Testing Service (Canary Deployments)

### Overview

Implement a dedicated A/B Testing and Canary Deployment service that manages controlled model rollouts with traffic splitting, statistical significance tracking, and automatic rollback capabilities. This service extends the basic `ABTestingRouter` in the inference service with a full-featured experimentation platform.

### Location

Create the new service at: `services/abtesting/`

### Required Files

```
services/abtesting/
    __init__.py
    main.py          # FastAPI application with endpoints
    models.py        # Data models for experiments and variants
    engine.py        # Core A/B testing logic
    statistics.py    # Statistical significance calculations
    rollback.py      # Automatic rollback on degradation
```

### Python Interface Contract

```python
# services/abtesting/models.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
from decimal import Decimal


class ExperimentStatus(Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    CONCLUDED = "concluded"
    ROLLED_BACK = "rolled_back"


class TrafficAllocationStrategy(Enum):
    PERCENTAGE = "percentage"      # Fixed percentage split
    RAMPING = "ramping"            # Gradual ramp-up over time
    MULTI_ARMED_BANDIT = "mab"     # Dynamic allocation based on performance


@dataclass
class ModelVariant:
    """A model variant in an A/B test experiment."""
    variant_id: str
    model_id: str
    model_version: str
    traffic_weight: Decimal          # Use Decimal to avoid float precision issues
    is_control: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExperimentMetrics:
    """Aggregated metrics for an experiment variant."""
    variant_id: str
    request_count: int
    success_count: int
    error_count: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    conversion_rate: Optional[float] = None
    custom_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class Experiment:
    """An A/B test experiment configuration."""
    experiment_id: str
    name: str
    description: str
    variants: List[ModelVariant]
    status: ExperimentStatus
    allocation_strategy: TrafficAllocationStrategy
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    minimum_sample_size: int = 1000
    confidence_level: float = 0.95
    primary_metric: str = "conversion_rate"
    guardrail_metrics: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

```python
# services/abtesting/engine.py

from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from datetime import datetime

from .models import (
    Experiment,
    ModelVariant,
    ExperimentMetrics,
    ExperimentStatus,
    TrafficAllocationStrategy
)


class ABTestingEngine:
    """
    Core A/B testing engine for model experiments.

    Manages experiment lifecycle, traffic routing, and metric collection.
    Integrates with the inference service for model predictions and the
    monitoring service for metric collection.
    """

    def __init__(self, inference_client, monitoring_client, event_bus):
        """
        Initialize the A/B testing engine.

        Args:
            inference_client: Client for the inference service
            monitoring_client: Client for the monitoring service
            event_bus: EventBus instance for publishing experiment events
        """
        pass

    def create_experiment(
        self,
        name: str,
        description: str,
        variants: List[Dict[str, Any]],
        allocation_strategy: TrafficAllocationStrategy = TrafficAllocationStrategy.PERCENTAGE,
        minimum_sample_size: int = 1000,
        confidence_level: float = 0.95,
        primary_metric: str = "conversion_rate",
        guardrail_metrics: Optional[List[str]] = None,
    ) -> Experiment:
        """
        Create a new A/B test experiment.

        Args:
            name: Human-readable experiment name
            description: Detailed description of the experiment hypothesis
            variants: List of variant configurations with model_id, version, and traffic_weight
            allocation_strategy: How to allocate traffic between variants
            minimum_sample_size: Minimum requests per variant before significance testing
            confidence_level: Statistical confidence level (e.g., 0.95 for 95%)
            primary_metric: The main metric to optimize for
            guardrail_metrics: Metrics that must not degrade (e.g., latency, error_rate)

        Returns:
            The created Experiment object

        Raises:
            ValueError: If variant weights don't sum to 1.0 or if variants are invalid
        """
        pass

    def start_experiment(self, experiment_id: str) -> Experiment:
        """
        Start an experiment, enabling traffic routing.

        Args:
            experiment_id: The experiment to start

        Returns:
            Updated Experiment with status=RUNNING

        Raises:
            ValueError: If experiment doesn't exist or is already running
        """
        pass

    def pause_experiment(self, experiment_id: str) -> Experiment:
        """
        Pause an experiment, routing all traffic to control.

        Args:
            experiment_id: The experiment to pause

        Returns:
            Updated Experiment with status=PAUSED
        """
        pass

    def route_request(
        self,
        experiment_id: str,
        request_id: str,
        user_id: Optional[str] = None,
        sticky: bool = True,
    ) -> Tuple[str, str]:
        """
        Route a request to a model variant.

        Uses consistent hashing for sticky sessions and Decimal arithmetic
        for precise traffic splitting.

        Args:
            experiment_id: The experiment to route for
            request_id: Unique request identifier
            user_id: Optional user ID for sticky routing
            sticky: If True, same user always gets same variant

        Returns:
            Tuple of (variant_id, model_version)

        Raises:
            ValueError: If experiment doesn't exist or is not running
        """
        pass

    def record_outcome(
        self,
        experiment_id: str,
        variant_id: str,
        request_id: str,
        success: bool,
        latency_ms: float,
        custom_metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Record the outcome of a request for metric aggregation.

        Args:
            experiment_id: The experiment this outcome belongs to
            variant_id: The variant that served this request
            request_id: The request identifier
            success: Whether the request was successful
            latency_ms: Request latency in milliseconds
            custom_metrics: Optional additional metrics to track
        """
        pass

    def get_experiment_metrics(
        self,
        experiment_id: str,
    ) -> Dict[str, ExperimentMetrics]:
        """
        Get aggregated metrics for all variants in an experiment.

        Args:
            experiment_id: The experiment to get metrics for

        Returns:
            Dict mapping variant_id to ExperimentMetrics
        """
        pass

    def conclude_experiment(
        self,
        experiment_id: str,
        winning_variant_id: Optional[str] = None,
    ) -> Experiment:
        """
        Conclude an experiment and optionally promote the winner.

        Args:
            experiment_id: The experiment to conclude
            winning_variant_id: The variant to promote to 100% traffic

        Returns:
            Updated Experiment with status=CONCLUDED
        """
        pass
```

```python
# services/abtesting/statistics.py

from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from .models import ExperimentMetrics


@dataclass
class SignificanceResult:
    """Result of a statistical significance test."""
    is_significant: bool
    p_value: float
    confidence_interval: Tuple[float, float]
    effect_size: float
    sample_size_adequate: bool
    recommended_action: str  # "continue", "conclude_winner", "conclude_no_difference"


class StatisticalAnalyzer:
    """
    Statistical analysis for A/B test experiments.

    Implements frequentist hypothesis testing for comparing model variants.
    Uses scipy for statistical calculations.
    """

    def __init__(self, confidence_level: float = 0.95):
        """
        Initialize the statistical analyzer.

        Args:
            confidence_level: The confidence level for significance tests
        """
        pass

    def calculate_significance(
        self,
        control_metrics: ExperimentMetrics,
        treatment_metrics: ExperimentMetrics,
        metric_name: str = "conversion_rate",
    ) -> SignificanceResult:
        """
        Calculate statistical significance between control and treatment.

        Uses a two-proportion z-test for conversion rates and Welch's t-test
        for continuous metrics.

        Args:
            control_metrics: Metrics from the control variant
            treatment_metrics: Metrics from the treatment variant
            metric_name: The metric to analyze

        Returns:
            SignificanceResult with p-value, confidence interval, and recommendation
        """
        pass

    def calculate_sample_size_requirement(
        self,
        baseline_rate: float,
        minimum_detectable_effect: float,
        confidence_level: float = 0.95,
        power: float = 0.80,
    ) -> int:
        """
        Calculate required sample size for detecting an effect.

        Args:
            baseline_rate: The baseline conversion/success rate
            minimum_detectable_effect: The minimum relative effect to detect (e.g., 0.05 for 5%)
            confidence_level: Desired confidence level
            power: Statistical power (1 - Type II error rate)

        Returns:
            Required sample size per variant
        """
        pass

    def check_guardrail_metrics(
        self,
        control_metrics: ExperimentMetrics,
        treatment_metrics: ExperimentMetrics,
        guardrail_names: list,
        degradation_threshold: float = 0.10,
    ) -> Dict[str, bool]:
        """
        Check if any guardrail metrics have degraded beyond threshold.

        Args:
            control_metrics: Metrics from the control variant
            treatment_metrics: Metrics from the treatment variant
            guardrail_names: List of metric names to check
            degradation_threshold: Maximum allowed degradation (e.g., 0.10 for 10%)

        Returns:
            Dict mapping metric name to whether it passed the guardrail check
        """
        pass
```

```python
# services/abtesting/rollback.py

from typing import Optional, Callable
from datetime import datetime, timedelta

from .models import Experiment, ExperimentMetrics
from .engine import ABTestingEngine
from .statistics import StatisticalAnalyzer


class AutoRollbackManager:
    """
    Automatic rollback manager for canary deployments.

    Monitors experiment health and automatically rolls back to control
    if guardrail metrics degrade or error rates spike.
    """

    def __init__(
        self,
        engine: ABTestingEngine,
        analyzer: StatisticalAnalyzer,
        check_interval_seconds: int = 60,
    ):
        """
        Initialize the rollback manager.

        Args:
            engine: The A/B testing engine
            analyzer: Statistical analyzer for metric comparison
            check_interval_seconds: How often to check for rollback conditions
        """
        pass

    def register_experiment(
        self,
        experiment_id: str,
        error_rate_threshold: float = 0.05,
        latency_degradation_threshold: float = 0.20,
        min_requests_before_rollback: int = 100,
        on_rollback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """
        Register an experiment for automatic rollback monitoring.

        Args:
            experiment_id: The experiment to monitor
            error_rate_threshold: Maximum error rate before rollback
            latency_degradation_threshold: Maximum latency increase vs control
            min_requests_before_rollback: Minimum requests before rollback can trigger
            on_rollback: Optional callback when rollback occurs
        """
        pass

    def check_rollback_conditions(
        self,
        experiment_id: str,
    ) -> Optional[str]:
        """
        Check if rollback conditions are met.

        Args:
            experiment_id: The experiment to check

        Returns:
            Reason for rollback if conditions are met, None otherwise
        """
        pass

    def execute_rollback(
        self,
        experiment_id: str,
        reason: str,
    ) -> Experiment:
        """
        Execute a rollback to the control variant.

        Args:
            experiment_id: The experiment to roll back
            reason: The reason for the rollback

        Returns:
            Updated Experiment with status=ROLLED_BACK
        """
        pass

    def start_monitoring(self) -> None:
        """Start the background monitoring thread."""
        pass

    def stop_monitoring(self) -> None:
        """Stop the background monitoring thread."""
        pass
```

### Integration Points

1. **Inference Service** (`services/inference/main.py`): Replace the simple `ABTestingRouter` with calls to the new A/B Testing service for experiment routing
2. **Monitoring Service** (`services/monitoring/main.py`): Send experiment metrics for aggregation and alerting
3. **Registry Service** (`services/registry/`): Query model versions and promote winning variants
4. **Event Bus** (`shared/events/base.py`): Publish experiment lifecycle events (started, concluded, rolled_back)
5. **Gateway** (`services/gateway/main.py`): Add endpoints for experiment management API

### Acceptance Criteria

1. **Unit Tests** (in `tests/unit/test_abtesting.py`):
   - Test experiment creation with valid/invalid configurations
   - Test traffic routing with sticky sessions
   - Test Decimal arithmetic for precise traffic splitting
   - Test statistical significance calculations
   - Test guardrail metric checking

2. **Integration Tests** (in `tests/integration/test_abtesting_integration.py`):
   - Test end-to-end experiment lifecycle
   - Test integration with inference service
   - Test automatic rollback on error rate spike
   - Test event publishing for experiment state changes

3. **Coverage Requirements**:
   - Minimum 85% line coverage for all new modules
   - 100% coverage for traffic routing logic

4. **Architectural Compliance**:
   - Follow the `ServiceClient` pattern from `shared/clients/base.py`
   - Use `EventBus` from `shared/events/base.py` for inter-service events
   - Use `Decimal` for all traffic weight calculations (avoid float precision bugs)
   - Use timezone-aware `datetime` objects (fix the pattern bug seen in existing code)

---

## Task 2: Training Data Versioning System (Dataset Lineage Tracking)

### Overview

Implement a Training Data Versioning system that tracks dataset versions, maintains lineage across transformations, supports point-in-time dataset reconstruction, and integrates with the experiment tracking service for reproducibility.

### Location

Create the new module at: `services/dataversion/`

### Required Files

```
services/dataversion/
    __init__.py
    main.py           # FastAPI application with endpoints
    models.py         # Data models for datasets and versions
    versioning.py     # Core versioning logic with DAG tracking
    lineage.py        # Lineage graph and provenance tracking
    storage.py        # Integration with MinIO for artifact storage
    reconstruction.py # Point-in-time dataset reconstruction
```

### Python Interface Contract

```python
# services/dataversion/models.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set
from enum import Enum
import hashlib


class DatasetFormat(Enum):
    PARQUET = "parquet"
    CSV = "csv"
    JSON = "json"
    TFRECORD = "tfrecord"
    NUMPY = "numpy"
    PICKLE = "pickle"  # Note: Should warn about security implications


class TransformationType(Enum):
    FILTER = "filter"
    MAP = "map"
    JOIN = "join"
    AGGREGATE = "aggregate"
    SAMPLE = "sample"
    SPLIT = "split"
    FEATURE_ENGINEERING = "feature_engineering"
    NORMALIZATION = "normalization"
    AUGMENTATION = "augmentation"


@dataclass
class DatasetSchema:
    """Schema definition for a dataset."""
    columns: Dict[str, str]  # column_name -> data_type
    primary_key: Optional[List[str]] = None
    partition_keys: Optional[List[str]] = None
    schema_version: int = 1

    def compute_hash(self) -> str:
        """Compute a hash of the schema for change detection."""
        pass


@dataclass
class DatasetVersion:
    """A specific version of a dataset."""
    version_id: str
    dataset_id: str
    version_number: int
    artifact_path: str          # Path in MinIO
    schema: DatasetSchema
    row_count: int
    size_bytes: int
    content_hash: str           # Hash of the data content
    created_at: datetime = field(default_factory=lambda: datetime.now())
    created_by: str = ""
    parent_version_id: Optional[str] = None
    transformation: Optional["TransformationRecord"] = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class TransformationRecord:
    """Record of a transformation applied to create a dataset version."""
    transformation_id: str
    transformation_type: TransformationType
    source_version_ids: List[str]  # Can have multiple sources (e.g., join)
    parameters: Dict[str, Any]
    code_hash: Optional[str] = None  # Hash of transformation code for reproducibility
    executed_at: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class Dataset:
    """A dataset with version history."""
    dataset_id: str
    name: str
    description: str
    format: DatasetFormat
    versions: List[DatasetVersion] = field(default_factory=list)
    current_version_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now())
    updated_at: datetime = field(default_factory=lambda: datetime.now())
    owner: str = ""
    access_groups: List[str] = field(default_factory=list)


@dataclass
class LineageNode:
    """A node in the lineage graph."""
    node_id: str
    node_type: str  # "dataset_version" or "transformation"
    metadata: Dict[str, Any]
    incoming_edges: List[str] = field(default_factory=list)
    outgoing_edges: List[str] = field(default_factory=list)
```

```python
# services/dataversion/versioning.py

from typing import Dict, Any, Optional, List, BinaryIO
from datetime import datetime

from .models import (
    Dataset,
    DatasetVersion,
    DatasetSchema,
    DatasetFormat,
    TransformationType,
    TransformationRecord,
)


class DatasetVersioningEngine:
    """
    Core dataset versioning engine.

    Manages dataset lifecycle, version creation, and schema evolution.
    Uses content-addressable storage for deduplication.
    """

    def __init__(self, storage_client, metadata_db, event_bus):
        """
        Initialize the versioning engine.

        Args:
            storage_client: Client for MinIO artifact storage
            metadata_db: Database connection for metadata
            event_bus: EventBus for publishing dataset events
        """
        pass

    def create_dataset(
        self,
        name: str,
        description: str,
        format: DatasetFormat,
        schema: DatasetSchema,
        owner: str,
        access_groups: Optional[List[str]] = None,
    ) -> Dataset:
        """
        Create a new dataset.

        Args:
            name: Human-readable dataset name
            description: Description of the dataset contents and purpose
            format: The storage format for this dataset
            schema: The initial schema definition
            owner: The owner of this dataset
            access_groups: Groups with access to this dataset

        Returns:
            The created Dataset object

        Raises:
            ValueError: If a dataset with this name already exists
        """
        pass

    def create_version(
        self,
        dataset_id: str,
        data: BinaryIO,
        schema: Optional[DatasetSchema] = None,
        parent_version_id: Optional[str] = None,
        transformation: Optional[TransformationRecord] = None,
        tags: Optional[Dict[str, str]] = None,
        created_by: str = "",
    ) -> DatasetVersion:
        """
        Create a new version of a dataset.

        Computes content hash for deduplication. If identical content
        already exists, returns the existing version.

        Args:
            dataset_id: The dataset to version
            data: Binary stream of the data content
            schema: Schema for this version (uses parent's if not provided)
            parent_version_id: The version this was derived from
            transformation: Record of transformation that created this version
            tags: Key-value tags for this version
            created_by: User or service that created this version

        Returns:
            The created DatasetVersion object

        Raises:
            ValueError: If dataset doesn't exist
            SchemaEvolutionError: If schema changes are incompatible
        """
        pass

    def get_version(
        self,
        dataset_id: str,
        version_id: Optional[str] = None,
        version_number: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> DatasetVersion:
        """
        Get a specific dataset version.

        Can retrieve by version_id, version_number, or point-in-time.

        Args:
            dataset_id: The dataset to query
            version_id: Specific version ID
            version_number: Version number (1, 2, 3, ...)
            as_of: Get the version that was current at this time

        Returns:
            The requested DatasetVersion

        Raises:
            ValueError: If the specified version doesn't exist
        """
        pass

    def list_versions(
        self,
        dataset_id: str,
        limit: int = 100,
        offset: int = 0,
        include_metadata: bool = True,
    ) -> List[DatasetVersion]:
        """
        List versions of a dataset.

        Args:
            dataset_id: The dataset to list versions for
            limit: Maximum versions to return
            offset: Pagination offset
            include_metadata: Whether to include full metadata

        Returns:
            List of DatasetVersion objects
        """
        pass

    def compare_versions(
        self,
        version_id_a: str,
        version_id_b: str,
    ) -> Dict[str, Any]:
        """
        Compare two dataset versions.

        Args:
            version_id_a: First version to compare
            version_id_b: Second version to compare

        Returns:
            Comparison result including schema diff, row count diff, and sample changes
        """
        pass

    def validate_schema_evolution(
        self,
        old_schema: DatasetSchema,
        new_schema: DatasetSchema,
    ) -> List[str]:
        """
        Validate that schema evolution is backward compatible.

        Args:
            old_schema: The previous schema
            new_schema: The proposed new schema

        Returns:
            List of compatibility warnings/errors
        """
        pass
```

```python
# services/dataversion/lineage.py

from typing import Dict, Any, Optional, List, Set
from datetime import datetime

from .models import DatasetVersion, LineageNode, TransformationRecord


class LineageGraph:
    """
    Directed acyclic graph (DAG) for dataset lineage tracking.

    Tracks the provenance of datasets through transformations,
    enabling impact analysis and reproducibility.
    """

    def __init__(self, graph_db_client):
        """
        Initialize the lineage graph.

        Args:
            graph_db_client: Client for the graph database (or in-memory for testing)
        """
        pass

    def add_version_node(
        self,
        version: DatasetVersion,
    ) -> LineageNode:
        """
        Add a dataset version to the lineage graph.

        Args:
            version: The dataset version to add

        Returns:
            The created LineageNode
        """
        pass

    def add_transformation_edge(
        self,
        source_version_ids: List[str],
        target_version_id: str,
        transformation: TransformationRecord,
    ) -> None:
        """
        Add a transformation edge connecting source versions to a target.

        Args:
            source_version_ids: The input dataset versions
            target_version_id: The output dataset version
            transformation: The transformation that was applied
        """
        pass

    def get_upstream_lineage(
        self,
        version_id: str,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get all upstream dependencies (ancestors) of a dataset version.

        Args:
            version_id: The version to trace upstream from
            max_depth: Maximum depth to traverse (None for unlimited)

        Returns:
            Lineage graph with all upstream nodes and edges
        """
        pass

    def get_downstream_lineage(
        self,
        version_id: str,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get all downstream dependents (descendants) of a dataset version.

        Useful for impact analysis when a dataset has issues.

        Args:
            version_id: The version to trace downstream from
            max_depth: Maximum depth to traverse

        Returns:
            Lineage graph with all downstream nodes and edges
        """
        pass

    def find_common_ancestors(
        self,
        version_id_a: str,
        version_id_b: str,
    ) -> List[str]:
        """
        Find common ancestor versions between two dataset versions.

        Args:
            version_id_a: First version
            version_id_b: Second version

        Returns:
            List of version IDs that are ancestors of both
        """
        pass

    def detect_cycles(self) -> List[List[str]]:
        """
        Detect any cycles in the lineage graph.

        Returns:
            List of cycles (each cycle is a list of node IDs)
        """
        pass

    def get_reproducibility_chain(
        self,
        version_id: str,
    ) -> List[TransformationRecord]:
        """
        Get the ordered chain of transformations to reproduce a version.

        Args:
            version_id: The version to reproduce

        Returns:
            Ordered list of transformations from root to target
        """
        pass
```

```python
# services/dataversion/reconstruction.py

from typing import Dict, Any, Optional, BinaryIO
from datetime import datetime

from .models import DatasetVersion
from .versioning import DatasetVersioningEngine
from .lineage import LineageGraph


class DatasetReconstructor:
    """
    Reconstruct datasets at specific points in time.

    Enables reproducible training by reconstructing the exact dataset
    state that was used for a given experiment.
    """

    def __init__(
        self,
        versioning_engine: DatasetVersioningEngine,
        lineage_graph: LineageGraph,
        storage_client,
    ):
        """
        Initialize the reconstructor.

        Args:
            versioning_engine: Dataset versioning engine
            lineage_graph: Lineage graph for tracing dependencies
            storage_client: MinIO client for artifact storage
        """
        pass

    def reconstruct_at_time(
        self,
        dataset_id: str,
        as_of: datetime,
    ) -> DatasetVersion:
        """
        Reconstruct the dataset as it existed at a specific time.

        Args:
            dataset_id: The dataset to reconstruct
            as_of: The point in time to reconstruct

        Returns:
            The DatasetVersion that was current at that time
        """
        pass

    def reconstruct_for_experiment(
        self,
        experiment_id: str,
        dataset_id: str,
    ) -> DatasetVersion:
        """
        Reconstruct the dataset version used in an experiment.

        Queries the experiment service to find the version that was
        used during training.

        Args:
            experiment_id: The experiment to match
            dataset_id: The dataset used in the experiment

        Returns:
            The exact DatasetVersion used in the experiment
        """
        pass

    def replay_transformations(
        self,
        source_version_id: str,
        target_version_id: str,
        new_source_data: BinaryIO,
    ) -> DatasetVersion:
        """
        Replay the transformation chain on new source data.

        Useful for applying the same preprocessing pipeline to new data.

        Args:
            source_version_id: The original source version
            target_version_id: The target version (defines transformation chain)
            new_source_data: New data to apply transformations to

        Returns:
            New DatasetVersion created by replaying transformations
        """
        pass

    def validate_reproducibility(
        self,
        version_id: str,
    ) -> Dict[str, Any]:
        """
        Validate that a dataset version can be reproduced.

        Checks that all source data and transformation code is available.

        Args:
            version_id: The version to validate

        Returns:
            Validation result with any missing dependencies
        """
        pass
```

### Integration Points

1. **Storage Service** (`services/storage/main.py`): Store dataset artifacts in MinIO with content-addressable paths
2. **Experiments Service** (`services/experiments/`): Link dataset versions to experiments for reproducibility
3. **Training Service** (`services/training/main.py`): Query dataset versions for training data loading
4. **Pipeline Service** (`services/pipeline/main.py`): Register transformations in the lineage graph
5. **Event Bus** (`shared/events/base.py`): Publish dataset lifecycle events

### Acceptance Criteria

1. **Unit Tests** (in `tests/unit/test_dataversion.py`):
   - Test version creation with content hashing
   - Test schema evolution validation
   - Test lineage graph traversal (upstream/downstream)
   - Test cycle detection in lineage graph
   - Test point-in-time reconstruction

2. **Integration Tests** (in `tests/integration/test_dataversion_integration.py`):
   - Test end-to-end dataset versioning workflow
   - Test integration with experiment service
   - Test MinIO artifact storage
   - Test reproducibility validation

3. **Coverage Requirements**:
   - Minimum 85% line coverage
   - 100% coverage for lineage graph traversal logic

4. **Architectural Compliance**:
   - Follow content-addressable storage pattern
   - Use timezone-aware `datetime` objects
   - Implement proper locking for concurrent version creation
   - Use safe serialization (avoid pickle for user data)

---

## Task 3: Model Explainability Engine (SHAP/LIME Integration)

### Overview

Implement a Model Explainability Engine that provides feature importance explanations for model predictions using SHAP and LIME. The service supports both real-time (synchronous) and batch (asynchronous) explanation generation, with caching for common explanation patterns.

### Location

Create the new module at: `services/explainability/`

### Required Files

```
services/explainability/
    __init__.py
    main.py           # FastAPI application with endpoints
    models.py         # Data models for explanations
    shap_engine.py    # SHAP-based explanations
    lime_engine.py    # LIME-based explanations
    aggregator.py     # Feature importance aggregation
    cache.py          # Explanation caching layer
```

### Python Interface Contract

```python
# services/explainability/models.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum


class ExplanationType(Enum):
    SHAP = "shap"
    LIME = "lime"
    INTEGRATED_GRADIENTS = "integrated_gradients"
    ATTENTION = "attention"


class AggregationMethod(Enum):
    MEAN = "mean"
    MEDIAN = "median"
    MAX = "max"
    PERCENTILE_95 = "percentile_95"


@dataclass
class FeatureContribution:
    """Contribution of a single feature to a prediction."""
    feature_name: str
    feature_value: Any
    contribution: float  # Positive = increases prediction, negative = decreases
    base_value: Optional[float] = None
    confidence: Optional[float] = None  # Confidence in the explanation


@dataclass
class PredictionExplanation:
    """Explanation for a single prediction."""
    explanation_id: str
    model_id: str
    model_version: str
    prediction_id: str
    explanation_type: ExplanationType
    base_prediction: float
    actual_prediction: float
    feature_contributions: List[FeatureContribution]
    top_positive_features: List[str] = field(default_factory=list)
    top_negative_features: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now())
    computation_time_ms: float = 0.0
    cached: bool = False


@dataclass
class GlobalExplanation:
    """Aggregated feature importance across multiple predictions."""
    explanation_id: str
    model_id: str
    model_version: str
    explanation_type: ExplanationType
    aggregation_method: AggregationMethod
    sample_count: int
    feature_importances: Dict[str, float]  # feature_name -> importance
    feature_interactions: Optional[Dict[str, Dict[str, float]]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class ExplanationRequest:
    """Request for generating an explanation."""
    model_id: str
    model_version: str
    input_data: Dict[str, Any]
    prediction_id: Optional[str] = None
    explanation_type: ExplanationType = ExplanationType.SHAP
    include_feature_interactions: bool = False
    top_k_features: int = 10
    background_sample_size: int = 100
```

```python
# services/explainability/shap_engine.py

from typing import Dict, Any, Optional, List, Callable
import numpy as np

from .models import (
    PredictionExplanation,
    GlobalExplanation,
    FeatureContribution,
    ExplanationType,
    AggregationMethod,
)


class SHAPExplainer:
    """
    SHAP (SHapley Additive exPlanations) based model explainer.

    Provides consistent, theoretically-grounded feature attributions
    based on game-theoretic Shapley values.
    """

    def __init__(
        self,
        model_loader,
        background_data_provider: Callable[[], np.ndarray],
        cache_client,
    ):
        """
        Initialize the SHAP explainer.

        Args:
            model_loader: ModelLoader from shared.ml for loading models
            background_data_provider: Callable that returns background samples
            cache_client: Redis client for caching explanations
        """
        pass

    def explain_prediction(
        self,
        model_id: str,
        model_version: str,
        input_data: Dict[str, Any],
        prediction_id: str,
        background_sample_size: int = 100,
        include_interactions: bool = False,
    ) -> PredictionExplanation:
        """
        Generate SHAP explanation for a single prediction.

        Uses KernelSHAP for model-agnostic explanations or TreeSHAP/DeepSHAP
        for specific model types when available.

        Args:
            model_id: The model to explain
            model_version: Specific model version
            input_data: The input features to explain
            prediction_id: ID to link explanation to prediction
            background_sample_size: Number of background samples for SHAP
            include_interactions: Whether to compute SHAP interaction values

        Returns:
            PredictionExplanation with feature contributions

        Raises:
            ValueError: If model cannot be loaded
            ComputationError: If SHAP computation fails
        """
        pass

    def explain_batch(
        self,
        model_id: str,
        model_version: str,
        inputs: List[Dict[str, Any]],
        prediction_ids: List[str],
        parallel: bool = True,
    ) -> List[PredictionExplanation]:
        """
        Generate SHAP explanations for a batch of predictions.

        More efficient than individual calls due to shared background data.

        Args:
            model_id: The model to explain
            model_version: Specific model version
            inputs: List of input feature dictionaries
            prediction_ids: Corresponding prediction IDs
            parallel: Whether to parallelize computation

        Returns:
            List of PredictionExplanation objects
        """
        pass

    def compute_global_importance(
        self,
        model_id: str,
        model_version: str,
        sample_inputs: List[Dict[str, Any]],
        aggregation_method: AggregationMethod = AggregationMethod.MEAN,
    ) -> GlobalExplanation:
        """
        Compute global feature importance by aggregating local explanations.

        Args:
            model_id: The model to explain
            model_version: Specific model version
            sample_inputs: Representative sample of inputs
            aggregation_method: How to aggregate importances

        Returns:
            GlobalExplanation with aggregated feature importances
        """
        pass

    def get_feature_dependence(
        self,
        model_id: str,
        model_version: str,
        feature_name: str,
        sample_inputs: List[Dict[str, Any]],
        interaction_feature: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compute SHAP dependence plot data for a feature.

        Shows how the model's predictions depend on a specific feature,
        optionally colored by an interaction feature.

        Args:
            model_id: The model to explain
            model_version: Specific model version
            feature_name: The feature to analyze
            sample_inputs: Sample inputs for the dependence plot
            interaction_feature: Optional feature to show interactions with

        Returns:
            Data for rendering a dependence plot
        """
        pass
```

```python
# services/explainability/lime_engine.py

from typing import Dict, Any, Optional, List
import numpy as np

from .models import (
    PredictionExplanation,
    FeatureContribution,
    ExplanationType,
)


class LIMEExplainer:
    """
    LIME (Local Interpretable Model-agnostic Explanations) based explainer.

    Provides local explanations by fitting interpretable models to
    perturbed samples around the prediction point.
    """

    def __init__(
        self,
        model_loader,
        feature_names: List[str],
        categorical_features: Optional[List[int]] = None,
        cache_client = None,
    ):
        """
        Initialize the LIME explainer.

        Args:
            model_loader: ModelLoader from shared.ml for loading models
            feature_names: Names of all input features
            categorical_features: Indices of categorical features
            cache_client: Redis client for caching explanations
        """
        pass

    def explain_prediction(
        self,
        model_id: str,
        model_version: str,
        input_data: Dict[str, Any],
        prediction_id: str,
        num_features: int = 10,
        num_samples: int = 5000,
    ) -> PredictionExplanation:
        """
        Generate LIME explanation for a single prediction.

        Creates a local interpretable surrogate model by sampling
        perturbations around the input and fitting a linear model.

        Args:
            model_id: The model to explain
            model_version: Specific model version
            input_data: The input features to explain
            prediction_id: ID to link explanation to prediction
            num_features: Number of top features to include
            num_samples: Number of perturbed samples to generate

        Returns:
            PredictionExplanation with feature contributions
        """
        pass

    def explain_text_prediction(
        self,
        model_id: str,
        model_version: str,
        text_input: str,
        prediction_id: str,
        num_features: int = 10,
        num_samples: int = 5000,
    ) -> PredictionExplanation:
        """
        Generate LIME explanation for a text classification prediction.

        Uses word-level perturbations for text models.

        Args:
            model_id: The model to explain
            model_version: Specific model version
            text_input: The text to explain
            prediction_id: ID to link explanation to prediction
            num_features: Number of top words to include
            num_samples: Number of perturbed samples

        Returns:
            PredictionExplanation with word contributions
        """
        pass

    def explain_image_prediction(
        self,
        model_id: str,
        model_version: str,
        image_data: np.ndarray,
        prediction_id: str,
        num_superpixels: int = 50,
        num_samples: int = 1000,
    ) -> Dict[str, Any]:
        """
        Generate LIME explanation for an image classification prediction.

        Uses superpixel segmentation for image explanations.

        Args:
            model_id: The model to explain
            model_version: Specific model version
            image_data: The image as a numpy array
            prediction_id: ID to link explanation to prediction
            num_superpixels: Number of superpixels for segmentation
            num_samples: Number of perturbed samples

        Returns:
            Explanation including superpixel importance map
        """
        pass
```

```python
# services/explainability/aggregator.py

from typing import Dict, Any, List, Optional
from collections import defaultdict
import numpy as np

from .models import (
    PredictionExplanation,
    GlobalExplanation,
    AggregationMethod,
    ExplanationType,
)


class FeatureImportanceAggregator:
    """
    Aggregate feature importances across multiple explanations.

    Provides insights into overall model behavior by combining
    local explanations into global feature importance rankings.
    """

    def __init__(self):
        """Initialize the aggregator."""
        pass

    def aggregate_explanations(
        self,
        explanations: List[PredictionExplanation],
        method: AggregationMethod = AggregationMethod.MEAN,
    ) -> GlobalExplanation:
        """
        Aggregate multiple local explanations into global importance.

        Args:
            explanations: List of local PredictionExplanation objects
            method: Aggregation method to use

        Returns:
            GlobalExplanation with aggregated importances

        Raises:
            ValueError: If explanations are from different models
        """
        pass

    def compute_stability(
        self,
        explanations: List[PredictionExplanation],
        top_k: int = 5,
    ) -> Dict[str, float]:
        """
        Compute stability of feature rankings across explanations.

        Measures how consistently features appear in top-k across samples.

        Args:
            explanations: List of explanations to analyze
            top_k: Number of top features to consider

        Returns:
            Dict mapping feature to stability score (0-1)
        """
        pass

    def detect_feature_interactions(
        self,
        explanations: List[PredictionExplanation],
    ) -> Dict[str, Dict[str, float]]:
        """
        Detect feature interactions from explanation patterns.

        Identifies features that tend to have correlated contributions.

        Args:
            explanations: List of explanations to analyze

        Returns:
            Nested dict of feature -> feature -> interaction strength
        """
        pass

    def segment_by_prediction(
        self,
        explanations: List[PredictionExplanation],
        prediction_bins: List[float],
    ) -> Dict[str, GlobalExplanation]:
        """
        Segment explanations by prediction value ranges.

        Useful for understanding how feature importance varies across
        different prediction ranges (e.g., high-risk vs low-risk).

        Args:
            explanations: List of explanations to segment
            prediction_bins: Bin edges for segmentation

        Returns:
            Dict mapping bin label to GlobalExplanation
        """
        pass
```

```python
# services/explainability/cache.py

from typing import Dict, Any, Optional
from datetime import timedelta
import hashlib
import json

from .models import PredictionExplanation, GlobalExplanation


class ExplanationCache:
    """
    Caching layer for explanations.

    Caches explanations by input hash to avoid recomputation for
    identical inputs. Uses Redis for distributed caching.
    """

    def __init__(
        self,
        redis_client,
        default_ttl: timedelta = timedelta(hours=24),
    ):
        """
        Initialize the cache.

        Args:
            redis_client: Redis client for caching
            default_ttl: Default time-to-live for cached explanations
        """
        pass

    def _compute_cache_key(
        self,
        model_id: str,
        model_version: str,
        input_data: Dict[str, Any],
        explanation_type: str,
    ) -> str:
        """
        Compute a cache key for an explanation.

        Uses content-based hashing of input data.

        Args:
            model_id: The model ID
            model_version: Model version
            input_data: The input features
            explanation_type: SHAP or LIME

        Returns:
            Cache key string
        """
        pass

    def get(
        self,
        model_id: str,
        model_version: str,
        input_data: Dict[str, Any],
        explanation_type: str,
    ) -> Optional[PredictionExplanation]:
        """
        Get a cached explanation if available.

        Args:
            model_id: The model ID
            model_version: Model version
            input_data: The input features
            explanation_type: SHAP or LIME

        Returns:
            Cached PredictionExplanation or None
        """
        pass

    def set(
        self,
        explanation: PredictionExplanation,
        ttl: Optional[timedelta] = None,
    ) -> None:
        """
        Cache an explanation.

        Args:
            explanation: The explanation to cache
            ttl: Optional custom TTL
        """
        pass

    def invalidate_model(
        self,
        model_id: str,
        model_version: Optional[str] = None,
    ) -> int:
        """
        Invalidate cached explanations for a model.

        Called when a model is updated or retrained.

        Args:
            model_id: The model ID
            model_version: Optional specific version to invalidate

        Returns:
            Number of cache entries invalidated
        """
        pass

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hit rate, miss rate, size, etc.
        """
        pass
```

### Integration Points

1. **Inference Service** (`services/inference/main.py`): Call explainability service for on-demand explanations
2. **Model Loader** (`shared/ml/model_loader.py`): Load models for explanation generation
3. **Monitoring Service** (`services/monitoring/main.py`): Track explanation computation metrics
4. **Features Service** (`services/features/`): Get feature metadata and names
5. **Redis**: Cache explanations to avoid recomputation
6. **Event Bus** (`shared/events/base.py`): Publish explanation completed events

### Acceptance Criteria

1. **Unit Tests** (in `tests/unit/test_explainability.py`):
   - Test SHAP explanation generation
   - Test LIME explanation generation
   - Test feature importance aggregation
   - Test cache hit/miss behavior
   - Test stability metrics

2. **Integration Tests** (in `tests/integration/test_explainability_integration.py`):
   - Test end-to-end explanation workflow
   - Test integration with inference service
   - Test Redis caching
   - Test batch explanation performance

3. **Coverage Requirements**:
   - Minimum 85% line coverage
   - 100% coverage for aggregation logic

4. **Architectural Compliance**:
   - Follow the `ServiceClient` pattern from `shared/clients/base.py`
   - Use timezone-aware `datetime` objects
   - Implement proper caching with Redis
   - Handle model loading errors gracefully
   - Use type hints and dataclasses consistently

### Performance Requirements

- Single SHAP explanation: < 500ms for tabular models
- Batch SHAP explanations: < 100ms per sample for batches > 100
- LIME explanation: < 2000ms (due to sampling)
- Cache hit latency: < 5ms

---

## General Requirements for All Tasks

### Code Style

- Follow PEP 8 and existing codebase conventions
- Use type hints for all function signatures
- Use dataclasses for data models (as shown in `shared/events/base.py`)
- Write comprehensive docstrings in Google style

### Testing

- All new modules must have corresponding test files
- Use pytest for testing
- Mock external service calls using the patterns in existing tests
- Include edge cases and error conditions

### Error Handling

- Define custom exceptions for domain-specific errors
- Log errors with appropriate context using the standard logger
- Return meaningful error messages to clients

### Observability

- Add logging for key operations
- Include timing metrics for performance-sensitive operations
- Propagate trace context (fix the J1 bug pattern - don't repeat it)

### Security

- Avoid pickle serialization for untrusted data (per existing I3 bug)
- Validate all inputs before processing
- Use parameterized queries for database operations
