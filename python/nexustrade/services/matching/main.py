"""
Matching Engine Service - High-performance order matching.

This service consumes orders from Kafka, matches them against the order book,
and produces trade execution events.
"""
import os
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from uuid import uuid4
from dataclasses import dataclass, field
from collections import defaultdict
import json

import redis
from confluent_kafka import Consumer, Producer, KafkaError

from shared.utils.time import utc_now, is_market_open

logger = logging.getLogger(__name__)

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/4")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_GROUP_ID = "matching-engine"


@dataclass
class OrderBookEntry:
    """Entry in the order book."""
    order_id: str
    user_id: str
    price: Decimal
    quantity: Decimal
    timestamp: datetime
    
    # Orders at same price should be FIFO, but we don't track arrival order properly


@dataclass
class OrderBook:
    """Order book for a single symbol."""
    symbol: str
    
    bids: List[OrderBookEntry] = field(default_factory=list)  # Sorted by price DESC
    asks: List[OrderBookEntry] = field(default_factory=list)  # Sorted by price ASC
    
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def add_bid(self, entry: OrderBookEntry) -> None:
        """Add a buy order to the book."""
        
        self.bids.append(entry)
        
        self.bids.sort(key=lambda x: x.price, reverse=True)

    def add_ask(self, entry: OrderBookEntry) -> None:
        """Add a sell order to the book."""
        self.asks.append(entry)
        self.asks.sort(key=lambda x: x.price)

    def get_best_bid(self) -> Optional[OrderBookEntry]:
        """Get best bid price."""
        return self.bids[0] if self.bids else None

    def get_best_ask(self) -> Optional[OrderBookEntry]:
        """Get best ask price."""
        return self.asks[0] if self.asks else None

    def remove_order(self, order_id: str) -> bool:
        """Remove an order from the book."""
        for i, entry in enumerate(self.bids):
            if entry.order_id == order_id:
                self.bids.pop(i)
                return True
        for i, entry in enumerate(self.asks):
            if entry.order_id == order_id:
                self.asks.pop(i)
                return True
        return False


class MatchingEngine:
    """
    High-performance order matching engine.

    Handles order matching, trade execution, and order book management.
    """

    def __init__(self):
        self.redis = redis.from_url(REDIS_URL)
        self.order_books: Dict[str, OrderBook] = defaultdict(
            lambda: OrderBook(symbol="")
        )
        self.producer: Optional[Producer] = None
        self.consumer: Optional[Consumer] = None
        
        # On restart, order book state is lost

    async def start(self):
        """Start the matching engine."""
        logger.info("Starting matching engine...")

        # Initialize Kafka producer
        self.producer = Producer({
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "client.id": "matching-engine",
        })

        # Initialize Kafka consumer
        self.consumer = Consumer({
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": KAFKA_GROUP_ID,
            "auto.offset.reset": "earliest",
            
            "enable.auto.commit": True,
        })

        
        # Kafka auto.create.topics.enable is false
        self.consumer.subscribe(["orders.created", "orders.cancelled"])

        logger.info("Matching engine started")

        # Main loop
        await self._run_loop()

    async def _run_loop(self):
        """Main processing loop."""
        while True:
            try:
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error(f"Kafka error: {msg.error()}")
                    continue

                # Process message
                await self._process_message(msg)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, msg):
        """Process a Kafka message."""
        try:
            value = json.loads(msg.value().decode("utf-8"))
            topic = msg.topic()

            if topic == "orders.created":
                await self._handle_new_order(value)
            elif topic == "orders.cancelled":
                await self._handle_cancel(value)

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def _handle_new_order(self, order_data: Dict[str, Any]):
        """
        Handle a new order.

        BUG F5: Market close edge case not handled
        BUG F4: Stop orders not checked against current price
        """
        symbol = order_data["symbol"]
        order_id = order_data["order_id"]
        user_id = order_data["user_id"]
        side = order_data["side"]
        order_type = order_data["order_type"]
        quantity = Decimal(str(order_data["quantity"]))
        price = Decimal(str(order_data.get("price", 0))) if order_data.get("price") else None
        stop_price = Decimal(str(order_data.get("stop_price", 0))) if order_data.get("stop_price") else None

        
        if not is_market_open():
            
            # Should reject orders after 4:00 PM, but >= allows 4:00 PM orders
            logger.warning(f"Market closed, rejecting order {order_id}")
            await self._publish_rejection(order_id, "Market is closed")
            return

        order_book = self.order_books[symbol]

        # Initialize order book for symbol if needed
        if not order_book.symbol:
            order_book.symbol = symbol

        # Handle market orders
        if order_type == "market":
            await self._execute_market_order(
                order_book, order_id, user_id, side, quantity
            )
        elif order_type == "limit":
            await self._process_limit_order(
                order_book, order_id, user_id, side, quantity, price
            )
        elif order_type == "stop":
            
            # Should check if current price already past stop price
            await self._add_stop_order(
                order_book, order_id, user_id, side, quantity, stop_price
            )

    async def _execute_market_order(
        self,
        order_book: OrderBook,
        order_id: str,
        user_id: str,
        side: str,
        quantity: Decimal,
    ):
        """
        Execute a market order immediately.

        BUG A3: Race condition with concurrent orders
        """
        remaining = quantity
        fills = []

        
        if side == "buy":
            while remaining > 0 and order_book.asks:
                best_ask = order_book.asks[0]

                fill_qty = min(remaining, best_ask.quantity)
                fill_price = best_ask.price

                fills.append({
                    "counterparty_order_id": best_ask.order_id,
                    "quantity": fill_qty,
                    "price": fill_price,
                })

                remaining -= fill_qty
                best_ask.quantity -= fill_qty

                if best_ask.quantity <= 0:
                    order_book.asks.pop(0)

        else:  # sell
            while remaining > 0 and order_book.bids:
                best_bid = order_book.bids[0]

                fill_qty = min(remaining, best_bid.quantity)
                fill_price = best_bid.price

                fills.append({
                    "counterparty_order_id": best_bid.order_id,
                    "quantity": fill_qty,
                    "price": fill_price,
                })

                remaining -= fill_qty
                best_bid.quantity -= fill_qty

                if best_bid.quantity <= 0:
                    order_book.bids.pop(0)

        # Publish fills
        for fill in fills:
            await self._publish_trade(
                order_id=order_id,
                user_id=user_id,
                counterparty_order_id=fill["counterparty_order_id"],
                symbol=order_book.symbol,
                side=side,
                quantity=fill["quantity"],
                price=fill["price"],
            )

        if remaining > 0:
            # Unfilled portion
            logger.warning(f"Order {order_id} partially filled, {remaining} remaining")

    async def _process_limit_order(
        self,
        order_book: OrderBook,
        order_id: str,
        user_id: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
    ):
        """
        Process a limit order - match or add to book.

        BUG F1: Price comparison uses float, loses precision
        """
        remaining = quantity

        if side == "buy":
            # Match against asks at or below limit price
            while remaining > 0 and order_book.asks:
                best_ask = order_book.asks[0]

                
                
                # When F1 is fixed (using Decimal comparison), trades will execute at
                # slightly different boundary prices. The _publish_trade() method converts
                # price back to float (line 440), causing the settlement service to receive
                # incorrect trade values. Fixing F1 without also fixing the float conversion
                # in _publish_trade() will cause settlement amount mismatches.
                if float(best_ask.price) > float(price):
                    break

                fill_qty = min(remaining, best_ask.quantity)
                fill_price = best_ask.price

                await self._publish_trade(
                    order_id=order_id,
                    user_id=user_id,
                    counterparty_order_id=best_ask.order_id,
                    symbol=order_book.symbol,
                    side=side,
                    quantity=fill_qty,
                    price=fill_price,
                )

                remaining -= fill_qty
                best_ask.quantity -= fill_qty

                if best_ask.quantity <= 0:
                    order_book.asks.pop(0)

            # Add remaining to book
            if remaining > 0:
                entry = OrderBookEntry(
                    order_id=order_id,
                    user_id=user_id,
                    price=price,
                    quantity=remaining,
                    timestamp=datetime.now(),  
                )
                order_book.add_bid(entry)

        else:  # sell
            while remaining > 0 and order_book.bids:
                best_bid = order_book.bids[0]

                
                if float(best_bid.price) < float(price):
                    break

                fill_qty = min(remaining, best_bid.quantity)
                fill_price = best_bid.price

                await self._publish_trade(
                    order_id=order_id,
                    user_id=user_id,
                    counterparty_order_id=best_bid.order_id,
                    symbol=order_book.symbol,
                    side=side,
                    quantity=fill_qty,
                    price=fill_price,
                )

                remaining -= fill_qty
                best_bid.quantity -= fill_qty

                if best_bid.quantity <= 0:
                    order_book.bids.pop(0)

            if remaining > 0:
                entry = OrderBookEntry(
                    order_id=order_id,
                    user_id=user_id,
                    price=price,
                    quantity=remaining,
                    timestamp=datetime.now(),
                )
                order_book.add_ask(entry)

    async def _add_stop_order(
        self,
        order_book: OrderBook,
        order_id: str,
        user_id: str,
        side: str,
        quantity: Decimal,
        stop_price: Decimal,
    ):
        """
        Add a stop order to be triggered later.

        BUG F4: Not checking if stop price already triggered
        """
        
        # If stop already triggered, should execute immediately

        # Store in Redis for later trigger checking
        
        key = f"stop_orders:{order_book.symbol}"
        self.redis.hset(key, order_id, json.dumps({
            "order_id": order_id,
            "user_id": user_id,
            "side": side,
            "quantity": str(quantity),
            "stop_price": str(stop_price),
        }))

    async def _handle_cancel(self, cancel_data: Dict[str, Any]):
        """Handle order cancellation."""
        order_id = cancel_data["order_id"]
        symbol = cancel_data.get("symbol")

        if symbol and symbol in self.order_books:
            order_book = self.order_books[symbol]
            order_book.remove_order(order_id)

        # Also remove from stop orders
        for key in self.redis.scan_iter("stop_orders:*"):
            self.redis.hdel(key, order_id)

    async def _publish_trade(
        self,
        order_id: str,
        user_id: str,
        counterparty_order_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
    ):
        """
        Publish trade execution event.

        BUG J1: Trace context not propagated
        """
        trade_id = str(uuid4())

        trade_event = {
            "trade_id": trade_id,
            "buy_order_id": order_id if side == "buy" else counterparty_order_id,
            "sell_order_id": counterparty_order_id if side == "buy" else order_id,
            "symbol": symbol,
            
            "price": float(price),
            "quantity": str(quantity),
            "execution_time": datetime.now().isoformat(),  
            
        }

        self.producer.produce(
            topic="trades.executed",
            key=trade_id.encode("utf-8"),
            value=json.dumps(trade_event).encode("utf-8"),
        )
        self.producer.flush()

        logger.info(f"Trade executed: {trade_id} - {quantity} @ {price}")

    async def _publish_rejection(self, order_id: str, reason: str):
        """Publish order rejection event."""
        event = {
            "order_id": order_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }

        self.producer.produce(
            topic="orders.rejected",
            key=order_id.encode("utf-8"),
            value=json.dumps(event).encode("utf-8"),
        )
        self.producer.flush()


# Simple HTTP health check server
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "matching"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logging


def run_health_server():
    server = HTTPServer(("0.0.0.0", 8000), HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Start health check server in background
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    # Start matching engine
    engine = MatchingEngine()
    asyncio.run(engine.start())
