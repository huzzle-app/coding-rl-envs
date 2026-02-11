"""
SynapseNet Test Configuration
Terminal Bench v2 - 750+ Test Suite
"""
import os
import sys
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ===========================================
# Fixtures for Testing
# ===========================================

@pytest.fixture
def sample_user_id():
    """Generate a sample user ID."""
    return str(uuid4())


@pytest.fixture
def sample_model_data():
    """Generate sample model metadata."""
    return {
        "model_id": str(uuid4()),
        "name": "text-classifier-v1",
        "framework": "pytorch",
        "version": "1.0.0",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"label": {"type": "string"}, "score": {"type": "number"}}},
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_training_job():
    """Generate sample training job data."""
    return {
        "job_id": str(uuid4()),
        "model_id": str(uuid4()),
        "dataset_id": str(uuid4()),
        "hyperparameters": {
            "learning_rate": 0.001,
            "batch_size": 32,
            "epochs": 10,
            "optimizer": "adam",
            "weight_decay": 1e-5,
        },
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_experiment_data():
    """Generate sample experiment data."""
    return {
        "experiment_id": str(uuid4()),
        "name": "lr-sweep-001",
        "model_id": str(uuid4()),
        "metrics": {
            "accuracy": Decimal("0.9523"),
            "loss": Decimal("0.1234"),
            "f1_score": Decimal("0.9412"),
        },
        "hyperparameters": {
            "learning_rate": 0.001,
            "batch_size": 32,
        },
        "tags": ["production", "sweep", "v2"],
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_feature_data():
    """Generate sample feature store data."""
    return {
        "feature_group": "user_features",
        "features": {
            "user_age": 32,
            "login_count": 150,
            "avg_session_duration": 45.3,
            "country": "US",
        },
        "entity_id": str(uuid4()),
        "event_time": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_prediction_request():
    """Generate sample prediction request."""
    return {
        "model_id": str(uuid4()),
        "model_version": "1.0.0",
        "input_data": {
            "text": "This is a sample input for prediction",
            "features": [0.1, 0.2, 0.3, 0.4, 0.5],
        },
        "request_id": str(uuid4()),
    }


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    mock.delete.return_value = True
    mock.hset.return_value = True
    mock.hget.return_value = None
    mock.pipeline.return_value = MagicMock()
    return mock


@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer."""
    mock = MagicMock()
    mock.produce.return_value = None
    mock.flush.return_value = 0
    return mock


@pytest.fixture
def mock_kafka_consumer():
    """Mock Kafka consumer."""
    mock = MagicMock()
    mock.poll.return_value = None
    mock.subscribe.return_value = None
    return mock


@pytest.fixture
def mock_minio_client():
    """Mock MinIO client."""
    mock = MagicMock()
    mock.put_object.return_value = None
    mock.get_object.return_value = MagicMock()
    mock.bucket_exists.return_value = True
    mock.make_bucket.return_value = None
    return mock


@pytest.fixture
def mock_elasticsearch():
    """Mock Elasticsearch client."""
    mock = MagicMock()
    mock.index.return_value = {"result": "created"}
    mock.search.return_value = {"hits": {"hits": [], "total": {"value": 0}}}
    mock.indices.exists.return_value = True
    return mock


@pytest.fixture
def mock_model_weights():
    """Generate mock model weights as numpy array."""
    import numpy as np
    return {
        "layer_0.weight": np.random.randn(128, 64).astype(np.float32),
        "layer_0.bias": np.random.randn(128).astype(np.float32),
        "layer_1.weight": np.random.randn(64, 32).astype(np.float32),
        "layer_1.bias": np.random.randn(64).astype(np.float32),
        "output.weight": np.random.randn(10, 64).astype(np.float32),
        "output.bias": np.random.randn(10).astype(np.float32),
    }


@pytest.fixture
def mock_gradient_data():
    """Generate mock gradient data for distributed training tests."""
    import numpy as np
    return {
        "worker_id": str(uuid4()),
        "gradients": {
            "layer_0": np.random.randn(128, 64).astype(np.float32),
            "layer_1": np.random.randn(64, 32).astype(np.float32),
            "output": np.random.randn(10, 64).astype(np.float32),
        },
        "step": 100,
        "learning_rate": 0.001,
    }


# ===========================================
# Markers Registration
# ===========================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "chaos: marks tests as chaos engineering tests")
    config.addinivalue_line("markers", "security: marks tests as security tests")
    config.addinivalue_line("markers", "contract: marks tests as contract tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")
    config.addinivalue_line("markers", "ml: marks tests as ML pipeline tests")


# ===========================================
# Test Collection Hooks
# ===========================================

def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    # Add markers based on test location
    for item in items:
        if "chaos" in str(item.fspath):
            item.add_marker(pytest.mark.chaos)
        elif "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "contract" in str(item.fspath):
            item.add_marker(pytest.mark.contract)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
        if "ml_pipeline" in str(item.fspath) or "model_serving" in str(item.fspath):
            item.add_marker(pytest.mark.ml)
