"""
NexusTrade Test Configuration
Terminal Bench v2 - 500+ Test Suite
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


# shared -> shared.clients -> shared.events -> shared.utils.serialization -> shared
# FIX: Remove this import or break the circular dependency chain
from shared import ServiceClient  # noqa: F401


# ===========================================
# Fixtures for Testing
# ===========================================

@pytest.fixture
def sample_user_id():
    """Generate a sample user ID."""
    return str(uuid4())


@pytest.fixture
def sample_order_data(sample_user_id):
    """Generate sample order data."""
    return {
        "user_id": sample_user_id,
        "symbol": "AAPL",
        "side": "buy",
        "order_type": "limit",
        "quantity": Decimal("100"),
        "price": Decimal("150.50"),
        "time_in_force": "day",
    }


@pytest.fixture
def sample_trade_data():
    """Generate sample trade data."""
    return {
        "trade_id": str(uuid4()),
        "symbol": "AAPL",
        "buy_order_id": str(uuid4()),
        "sell_order_id": str(uuid4()),
        "buyer_id": str(uuid4()),
        "seller_id": str(uuid4()),
        "price": Decimal("150.50"),
        "quantity": Decimal("100"),
        "execution_time": datetime.now(timezone.utc),
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
