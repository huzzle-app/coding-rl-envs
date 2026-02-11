"""
Market Data Service - Real-time price feed via WebSocket.

BUG H1: Cache stampede on price expiry
BUG H4: TTL not randomized - synchronized expiry
"""
import os
import asyncio
import logging
import random
from datetime import datetime
from typing import Dict, Set, Any
from decimal import Decimal
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import redis

logger = logging.getLogger(__name__)

app = FastAPI(title="NexusTrade Market Data")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/7")
redis_client = redis.from_url(REDIS_URL)

# Active WebSocket connections
active_connections: Dict[str, Set[WebSocket]] = {}

# Price cache - BUG H1: All prices expire at same time
PRICE_CACHE: Dict[str, Dict[str, Any]] = {}

CACHE_TTL = 5  # seconds


def get_price(symbol: str) -> Dict[str, Any]:
    """
    Get current price for symbol.

    BUG H1: Cache stampede when cache expires
    BUG H3: Cache-aside race condition
    """
    cache_key = f"price:{symbol}"

    # Check local cache first
    if symbol in PRICE_CACHE:
        cached = PRICE_CACHE[symbol]
        age = (datetime.now() - cached["timestamp"]).total_seconds()
        
        if age < CACHE_TTL:
            return cached["data"]

    # Check Redis
    redis_data = redis_client.get(cache_key)
    if redis_data:
        data = json.loads(redis_data)
        
        PRICE_CACHE[symbol] = {
            "data": data,
            "timestamp": datetime.now(),
        }
        return data

    
    # No locking to prevent stampede
    price_data = _fetch_price_from_source(symbol)

    
    PRICE_CACHE[symbol] = {
        "data": price_data,
        "timestamp": datetime.now(),
    }

    
    redis_client.setex(cache_key, CACHE_TTL, json.dumps(price_data))

    return price_data


def _fetch_price_from_source(symbol: str) -> Dict[str, Any]:
    """Simulate fetching price from external source."""
    # Simulated prices
    base_prices = {
        "AAPL": 150.0,
        "GOOGL": 140.0,
        "MSFT": 380.0,
        "AMZN": 175.0,
    }
    base = base_prices.get(symbol, 100.0)
    # Add some random variation
    price = base * (1 + random.uniform(-0.01, 0.01))

    return {
        "symbol": symbol,
        "price": price,
        "bid": price - 0.01,
        "ask": price + 0.01,
        "timestamp": datetime.now().isoformat(),  
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "market-data"}


@app.get("/prices/{symbol}")
async def get_symbol_price(symbol: str):
    """Get current price for a symbol."""
    return get_price(symbol.upper())


@app.websocket("/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint for real-time price updates.

    BUG H2: Hot symbol causes connection concentration
    """
    symbol = symbol.upper()
    await websocket.accept()

    if symbol not in active_connections:
        active_connections[symbol] = set()
    active_connections[symbol].add(websocket)

    
    # No load balancing for WebSocket connections

    try:
        while True:
            # Send price update every second
            price_data = get_price(symbol)
            await websocket.send_json(price_data)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        active_connections[symbol].discard(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        active_connections[symbol].discard(websocket)


@app.get("/orderbook/{symbol}")
async def get_orderbook(symbol: str, depth: int = 10):
    """Get order book for symbol."""
    # Would fetch from matching engine in real system
    return {
        "symbol": symbol.upper(),
        "bids": [],
        "asks": [],
        "timestamp": datetime.now().isoformat(),
    }
