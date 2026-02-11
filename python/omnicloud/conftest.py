"""
OmniCloud Test Configuration
Terminal Bench v2 - 750+ Test Suite
"""
import os
import sys
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock
from ipaddress import IPv4Network

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ===========================================
# Fixtures for Testing
# ===========================================

@pytest.fixture
def sample_tenant_id():
    """Generate a sample tenant ID."""
    return str(uuid4())


@pytest.fixture
def sample_user_id():
    """Generate a sample user ID."""
    return str(uuid4())


@pytest.fixture
def sample_resource_data(sample_tenant_id):
    """Generate sample infrastructure resource data."""
    return {
        "tenant_id": sample_tenant_id,
        "resource_type": "compute_instance",
        "name": "web-server-01",
        "region": "us-east-1",
        "spec": {
            "cpu": 4,
            "memory_gb": 16,
            "disk_gb": 100,
        },
        "tags": {"env": "production", "team": "platform"},
    }


@pytest.fixture
def sample_network_data(sample_tenant_id):
    """Generate sample network configuration."""
    return {
        "tenant_id": sample_tenant_id,
        "vpc_cidr": "10.0.0.0/16",
        "subnets": [
            {"cidr": "10.0.1.0/24", "az": "us-east-1a", "type": "public"},
            {"cidr": "10.0.2.0/24", "az": "us-east-1b", "type": "private"},
        ],
        "security_groups": [
            {
                "name": "web-sg",
                "rules": [
                    {"protocol": "tcp", "port": 80, "source": "0.0.0.0/0"},
                    {"protocol": "tcp", "port": 443, "source": "0.0.0.0/0"},
                ],
            },
        ],
    }


@pytest.fixture
def sample_deployment_data(sample_tenant_id):
    """Generate sample deployment configuration."""
    return {
        "tenant_id": sample_tenant_id,
        "service_name": "api-gateway",
        "version": "2.1.0",
        "strategy": "rolling",
        "replicas": 3,
        "batch_size": 1,
        "health_check": {
            "path": "/health",
            "interval": 10,
            "timeout": 5,
            "healthy_threshold": 3,
        },
    }


@pytest.fixture
def sample_billing_data(sample_tenant_id):
    """Generate sample billing data."""
    return {
        "tenant_id": sample_tenant_id,
        "billing_period_start": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "billing_period_end": datetime(2024, 2, 1, tzinfo=timezone.utc),
        "line_items": [
            {
                "resource_type": "compute_instance",
                "quantity": Decimal("720"),
                "unit": "hours",
                "unit_price": Decimal("0.0464"),
            },
            {
                "resource_type": "block_storage",
                "quantity": Decimal("100"),
                "unit": "gb_months",
                "unit_price": Decimal("0.10"),
            },
        ],
    }


@pytest.fixture
def sample_cidr_pool():
    """Generate a sample CIDR pool for network tests."""
    return [
        IPv4Network("10.0.0.0/16"),
        IPv4Network("10.1.0.0/16"),
        IPv4Network("10.2.0.0/16"),
    ]


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
    mock.setnx.return_value = True
    mock.expire.return_value = True
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
def mock_etcd_client():
    """Mock etcd client."""
    mock = MagicMock()
    mock.get.return_value = (None, None)
    mock.put.return_value = True
    mock.lock.return_value = MagicMock()
    mock.watch.return_value = iter([])
    return mock


@pytest.fixture
def mock_vault_client():
    """Mock Vault client."""
    mock = MagicMock()
    mock.secrets.kv.v2.read_secret_version.return_value = {"data": {"data": {}}}
    mock.secrets.kv.v2.create_or_update_secret.return_value = True
    return mock


@pytest.fixture
def mock_consul_client():
    """Mock Consul client."""
    mock = MagicMock()
    mock.agent.service.register.return_value = True
    mock.health.service.return_value = (None, [])
    mock.kv.get.return_value = (None, None)
    mock.kv.put.return_value = True
    return mock


@pytest.fixture
def mock_minio_client():
    """Mock MinIO client."""
    mock = MagicMock()
    mock.bucket_exists.return_value = True
    mock.put_object.return_value = MagicMock()
    mock.get_object.return_value = MagicMock()
    return mock


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
    config.addinivalue_line("markers", "system: marks tests as system/end-to-end tests")


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
        elif "system" in str(item.fspath):
            item.add_marker(pytest.mark.system)
