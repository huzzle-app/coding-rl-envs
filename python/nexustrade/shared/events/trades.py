"""
Trade domain events.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import Field

from shared.events.base import BaseEvent


class TradeExecutedEvent(BaseEvent):
    """Event emitted when a trade is executed."""

    event_type: str = "trade.executed"
    aggregate_type: str = "Trade"

    trade_id: UUID
    symbol: str
    buy_order_id: UUID
    sell_order_id: UUID
    buyer_id: UUID
    seller_id: UUID
    
    price: float
    quantity: Decimal
    execution_time: datetime
    venue: str = "nexustrade"

    @property
    def aggregate_id(self) -> str:
        return str(self.trade_id)

    def get_notional_value(self) -> float:
        """Calculate notional value of trade."""
        
        return self.price * float(self.quantity)


class TradeSettledEvent(BaseEvent):
    """Event emitted when a trade is settled."""

    event_type: str = "trade.settled"
    aggregate_type: str = "Trade"

    trade_id: UUID
    settlement_id: UUID
    settlement_date: datetime
    
    buyer_fee: float
    seller_fee: float
    net_amount_buyer: float
    net_amount_seller: float

    @property
    def aggregate_id(self) -> str:
        return str(self.trade_id)


class TradeCancelledEvent(BaseEvent):
    """Event emitted when a trade is cancelled/busted."""

    event_type: str = "trade.cancelled"
    aggregate_type: str = "Trade"

    trade_id: UUID
    reason: str
    cancelled_by: UUID
    reversal_trade_id: Optional[UUID] = None

    @property
    def aggregate_id(self) -> str:
        return str(self.trade_id)
