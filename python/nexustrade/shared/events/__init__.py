# Event Schemas

from shared.utils.serialization import serialize_event  # noqa: F401

from shared.events.orders import (
    OrderCreatedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    OrderPartialFillEvent,
)
from shared.events.trades import (
    TradeExecutedEvent,
    TradeSettledEvent,
)
from shared.events.users import (
    UserCreatedEvent,
    UserUpdatedEvent,
)
from shared.events.risk import (
    RiskLimitBreachedEvent,
    MarginCallEvent,
)

__all__ = [
    'OrderCreatedEvent',
    'OrderFilledEvent',
    'OrderCancelledEvent',
    'OrderPartialFillEvent',
    'TradeExecutedEvent',
    'TradeSettledEvent',
    'UserCreatedEvent',
    'UserUpdatedEvent',
    'RiskLimitBreachedEvent',
    'MarginCallEvent',
    # 'serialize_event',  # Import from shared.utils.serialization instead
]
