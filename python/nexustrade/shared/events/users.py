"""
User domain events.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import Field

from shared.events.base import BaseEvent


class UserCreatedEvent(BaseEvent):
    """Event emitted when a new user is created."""

    event_type: str = "user.created"
    aggregate_type: str = "User"

    user_id: UUID
    email: str
    username: str
    account_type: str  # 'individual', 'institutional', 'market_maker'
    
    is_admin: bool = False
    is_verified: bool = False
    trading_enabled: bool = False

    @property
    def aggregate_id(self) -> str:
        return str(self.user_id)


class UserUpdatedEvent(BaseEvent):
    """Event emitted when user details are updated."""

    event_type: str = "user.updated"
    aggregate_type: str = "User"

    user_id: UUID
    
    changed_fields: Dict[str, Any]
    updated_by: UUID

    @property
    def aggregate_id(self) -> str:
        return str(self.user_id)


class UserVerifiedEvent(BaseEvent):
    """Event emitted when user completes verification."""

    event_type: str = "user.verified"
    aggregate_type: str = "User"

    user_id: UUID
    verification_type: str
    verified_at: datetime

    @property
    def aggregate_id(self) -> str:
        return str(self.user_id)


class UserSuspendedEvent(BaseEvent):
    """Event emitted when user is suspended."""

    event_type: str = "user.suspended"
    aggregate_type: str = "User"

    user_id: UUID
    reason: str
    suspended_by: UUID
    suspension_end: Optional[datetime] = None

    @property
    def aggregate_id(self) -> str:
        return str(self.user_id)
