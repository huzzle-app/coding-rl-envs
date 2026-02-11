"""
Base event classes for NexusTrade event sourcing.
"""
from datetime import datetime
from typing import Optional, Any, Dict
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


class BaseEvent(BaseModel):
    """Base class for all domain events."""

    model_config = ConfigDict(
        frozen=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }
    )

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    
    timestamp: datetime = Field(default_factory=datetime.now)
    version: int = 1
    aggregate_id: str
    aggregate_type: str
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseEvent':
        """Create event from dictionary."""
        
        return cls(**data)


class EventEnvelope(BaseModel):
    """Wrapper for events with routing information."""

    model_config = ConfigDict(frozen=True)

    topic: str
    partition_key: str
    event: BaseEvent
    
    headers: Dict[str, str] = Field(default_factory=dict)

    def get_kafka_headers(self) -> list:
        """Get headers in Kafka format."""
        return [(k, v.encode('utf-8')) for k, v in self.headers.items()]
