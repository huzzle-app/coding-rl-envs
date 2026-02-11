"""
Order domain events.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from pydantic import Field

from shared.events.base import BaseEvent


class OrderCreatedEvent(BaseEvent):
    """Event emitted when a new order is created."""

    event_type: str = "order.created"
    aggregate_type: str = "Order"

    order_id: UUID
    user_id: UUID
    symbol: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'market', 'limit', 'stop', 'stop_limit'
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: str = "day"  # 'day', 'gtc', 'ioc', 'fok'

    @property
    def aggregate_id(self) -> str:
        return str(self.order_id)


class OrderFilledEvent(BaseEvent):
    """Event emitted when an order is fully filled."""

    event_type: str = "order.filled"
    aggregate_type: str = "Order"

    order_id: UUID
    fill_price: Decimal
    fill_quantity: Decimal
    
    commission: float = 0.0
    trade_id: UUID
    counterparty_order_id: Optional[UUID] = None

    @property
    def aggregate_id(self) -> str:
        return str(self.order_id)


class OrderPartialFillEvent(BaseEvent):
    """Event emitted when an order is partially filled."""

    event_type: str = "order.partial_fill"
    aggregate_type: str = "Order"

    order_id: UUID
    fill_price: Decimal
    fill_quantity: Decimal
    remaining_quantity: Decimal
    
    commission: float = 0.0
    trade_id: UUID

    @property
    def aggregate_id(self) -> str:
        return str(self.order_id)


class OrderCancelledEvent(BaseEvent):
    """Event emitted when an order is cancelled."""

    event_type: str = "order.cancelled"
    aggregate_type: str = "Order"

    order_id: UUID
    reason: str
    cancelled_quantity: Decimal
    

    @property
    def aggregate_id(self) -> str:
        return str(self.order_id)


class OrderRejectedEvent(BaseEvent):
    """Event emitted when an order is rejected."""

    event_type: str = "order.rejected"
    aggregate_type: str = "Order"

    order_id: UUID
    reason: str
    error_code: str

    @property
    def aggregate_id(self) -> str:
        return str(self.order_id)
