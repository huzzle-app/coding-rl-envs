"""
Risk management domain events.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import Field

from shared.events.base import BaseEvent


class RiskLimitBreachedEvent(BaseEvent):
    """Event emitted when a risk limit is breached."""

    event_type: str = "risk.limit_breached"
    aggregate_type: str = "RiskProfile"

    user_id: UUID
    limit_type: str  # 'position', 'daily_loss', 'order_size', 'exposure'
    limit_value: Decimal
    current_value: Decimal
    
    breach_percentage: float
    action_taken: str  # 'blocked', 'warning', 'liquidation'

    @property
    def aggregate_id(self) -> str:
        return str(self.user_id)


class MarginCallEvent(BaseEvent):
    """Event emitted when a margin call is triggered."""

    event_type: str = "risk.margin_call"
    aggregate_type: str = "RiskProfile"

    user_id: UUID
    account_equity: Decimal
    margin_requirement: Decimal
    
    margin_deficit: Decimal
    deadline: datetime
    positions_at_risk: list = Field(default_factory=list)

    @property
    def aggregate_id(self) -> str:
        return str(self.user_id)


class PositionLiquidatedEvent(BaseEvent):
    """Event emitted when a position is force liquidated."""

    event_type: str = "risk.position_liquidated"
    aggregate_type: str = "Position"

    user_id: UUID
    position_id: UUID
    symbol: str
    quantity_liquidated: Decimal
    liquidation_price: Decimal
    reason: str

    @property
    def aggregate_id(self) -> str:
        return str(self.position_id)


class RiskLimitUpdatedEvent(BaseEvent):
    """Event emitted when risk limits are updated."""

    event_type: str = "risk.limit_updated"
    aggregate_type: str = "RiskProfile"

    user_id: UUID
    limit_type: str
    old_value: Decimal
    new_value: Decimal
    updated_by: UUID
    reason: str

    @property
    def aggregate_id(self) -> str:
        return str(self.user_id)
