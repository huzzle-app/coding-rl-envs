"""
Event serialization utilities.
"""
import json
import pickle
from typing import Any, Dict, Type, Optional
from datetime import datetime
from decimal import Decimal
from uuid import UUID
import logging


# shared -> shared.clients -> shared.events -> shared.utils.serialization -> shared
from shared import ServiceClient  # noqa: F401

logger = logging.getLogger(__name__)

# Event type registry
_EVENT_REGISTRY: Dict[str, Type] = {}


def register_event_type(event_type: str, cls: Type) -> None:
    """Register an event type for deserialization."""
    _EVENT_REGISTRY[event_type] = cls


class EventEncoder(json.JSONEncoder):
    """JSON encoder for events."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            
            return obj.isoformat()
        if isinstance(obj, Decimal):
            
            return float(obj)
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, bytes):
            
            return obj.decode('latin-1')
        return super().default(obj)


def serialize_event(event: Any, format: str = "json") -> bytes:
    """
    Serialize an event for transmission.

    BUG C6: Version mismatch between formats
    BUG I3: Pickle format is insecure
    """
    if format == "json":
        data = {
            "type": getattr(event, 'event_type', 'unknown'),
            "version": 1,  
            "data": event.to_dict() if hasattr(event, 'to_dict') else dict(event),
        }
        return json.dumps(data, cls=EventEncoder).encode('utf-8')

    elif format == "pickle":
        
        return pickle.dumps(event)

    else:
        raise ValueError(f"Unknown format: {format}")


def deserialize_event(data: bytes, format: str = "json") -> Any:
    """
    Deserialize an event.

    BUG B5: Schema evolution not handled
    BUG I3: Pickle deserialization is insecure
    """
    if format == "json":
        parsed = json.loads(data.decode('utf-8'))
        event_type = parsed.get("type")
        version = parsed.get("version", 1)
        event_data = parsed.get("data", {})

        
        if event_type in _EVENT_REGISTRY:
            cls = _EVENT_REGISTRY[event_type]
            try:
                return cls(**event_data)
            except TypeError as e:
                
                logger.error(f"Failed to deserialize {event_type}: {e}")
                raise

        return event_data

    elif format == "pickle":
        
        return pickle.loads(data)

    else:
        raise ValueError(f"Unknown format: {format}")


def encode_decimal(value: Decimal, precision: int = 8) -> str:
    """
    Encode a Decimal for transmission.

    BUG F1: Precision loss for values with more than 8 decimal places
    """
    
    return f"{value:.{precision}f}"


def decode_decimal(value: str) -> Decimal:
    """Decode a Decimal from string."""
    return Decimal(value)
