"""
Orders service views.
"""
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any
from uuid import UUID

from django.db import transaction
from django.db.models import F
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.request import Request

from services.orders.models import Order, OrderFill, Position, OrderEvent
from shared.clients.risk import RiskClient

logger = logging.getLogger(__name__)


def publish_order_event(order: Order, event_type: str, data: Dict[str, Any]):
    """
    Publish order event to Kafka.

    BUG D4: Outbox pattern not implemented - events can be lost
    """
    
    # If Kafka is down, event is lost
    # Should: Write to outbox table in same transaction, then publish async

    sequence = OrderEvent.objects.filter(order_id=order.id).count() + 1
    OrderEvent.objects.create(
        order_id=order.id,
        event_type=event_type,
        event_data=data,
        sequence_number=sequence,
    )

    
    # If this fails, DB has event but Kafka doesn't


@api_view(["POST"])
def create_order(request: Request) -> Response:
    """
    Create a new order.

    BUG A3: Race condition on concurrent orders for same user/symbol
    BUG G1: Risk check not atomic with order creation
    """
    data = request.data

    try:
        user_id = UUID(data.get("user_id"))
        symbol = data.get("symbol")
        side = data.get("side")
        order_type = data.get("order_type")
        quantity = Decimal(str(data.get("quantity", 0)))
        price = Decimal(str(data.get("price"))) if data.get("price") else None
        stop_price = Decimal(str(data.get("stop_price"))) if data.get("stop_price") else None
        time_in_force = data.get("time_in_force", "day")
    except (ValueError, InvalidOperation) as e:
        return Response(
            {"error": f"Invalid data: {e}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate
    if not all([symbol, side, order_type, quantity > 0]):
        return Response(
            {"error": "Missing or invalid required fields"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if order_type == "limit" and not price:
        return Response(
            {"error": "Limit orders require a price"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    
    # Another order could be created between check and order creation
    risk_client = RiskClient()
    try:
        # This is async but we're in sync context - potential issue
        import asyncio
        loop = asyncio.new_event_loop()
        risk_result = loop.run_until_complete(
            risk_client.check_order_risk(
                user_id=str(user_id),
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
            )
        )
        loop.close()

        if not risk_result.get("approved"):
            return Response(
                {"error": "Risk check failed", "details": risk_result.get("reason")},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except Exception as e:
        logger.error(f"Risk check failed: {e}")
        
        return Response(
            {"error": "Risk check unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    
    # then both get created, exceeding limits
    #
    
    # When A3 is fixed (by adding proper locking), the position updates in
    # fill_order() will start racing with each other since they also lack
    # proper row-level locking. Currently the race in A3 dominates, but fixing
    # it will expose position drift where filled_quantity != sum(fill quantities).
    # Fixing A3 alone will cause tests like test_concurrent_partial_fills to fail.
    order = Order.objects.create(
        user_id=user_id,
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
        time_in_force=time_in_force,
        status="pending",
    )

    publish_order_event(order, "order.created", {
        "order_id": str(order.id),
        "user_id": str(user_id),
        "symbol": symbol,
        "side": side,
        "quantity": str(quantity),
        "price": str(price) if price else None,
    })

    return Response({
        "order_id": str(order.id),
        "status": order.status,
        "created_at": order.created_at.isoformat(),
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def get_order(request: Request, order_id: str) -> Response:
    """Get order by ID."""
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response(
            {"error": "Order not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response({
        "order_id": str(order.id),
        "user_id": str(order.user_id),
        "symbol": order.symbol,
        "side": order.side,
        "order_type": order.order_type,
        "quantity": str(order.quantity),
        "filled_quantity": str(order.filled_quantity),
        "price": str(order.price) if order.price else None,
        "avg_fill_price": order.avg_fill_price,
        "status": order.status,
        "created_at": order.created_at.isoformat(),
    })


@api_view(["POST"])
def cancel_order(request: Request, order_id: str) -> Response:
    """
    Cancel an order.

    BUG B2: No idempotency - duplicate cancels can cause issues
    """
    reason = request.data.get("reason", "user_requested")

    try:
        
        # Multiple cancel requests can race
        order = Order.objects.select_for_update().get(id=order_id)
    except Order.DoesNotExist:
        return Response(
            {"error": "Order not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if order.is_complete:
        
        # but returns error instead
        return Response(
            {"error": f"Order already {order.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        order.status = "cancelled"
        order.cancelled_at = datetime.now()  
        order.save()

        publish_order_event(order, "order.cancelled", {
            "order_id": str(order.id),
            "reason": reason,
            "cancelled_quantity": str(order.remaining_quantity),
        })

    return Response({
        "order_id": str(order.id),
        "status": order.status,
        "cancelled_at": order.cancelled_at.isoformat(),
    })


@api_view(["GET"])
def list_orders(request: Request) -> Response:
    """
    List orders for a user.

    BUG I1: SQL injection via order_by parameter
    """
    user_id = request.query_params.get("user_id")
    status_filter = request.query_params.get("status")
    symbol = request.query_params.get("symbol")
    limit = int(request.query_params.get("limit", 100))
    offset = int(request.query_params.get("offset", 0))
    order_by = request.query_params.get("order_by", "-created_at")

    if not user_id:
        return Response(
            {"error": "user_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    queryset = Order.objects.filter(user_id=user_id)

    if status_filter:
        queryset = queryset.filter(status=status_filter)

    if symbol:
        queryset = queryset.filter(symbol=symbol)

    
    # Attacker can inject: "-created_at; DROP TABLE orders; --"
    try:
        queryset = queryset.order_by(order_by)
    except Exception as e:
        
        return Response(
            {"error": f"Invalid order_by: {e}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    orders = queryset[offset:offset + limit]

    return Response({
        "orders": [
            {
                "order_id": str(o.id),
                "symbol": o.symbol,
                "side": o.side,
                "quantity": str(o.quantity),
                "filled_quantity": str(o.filled_quantity),
                "price": str(o.price) if o.price else None,
                "status": o.status,
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ],
        "count": len(orders),
    })


@api_view(["POST"])
def fill_order(request: Request, order_id: str) -> Response:
    """
    Fill an order (called by matching engine).

    BUG F3: Rounding errors in partial fills
    BUG D6: Optimistic locking not implemented correctly
    """
    data = request.data
    fill_quantity = Decimal(str(data.get("quantity", 0)))
    fill_price = Decimal(str(data.get("price", 0)))
    trade_id = data.get("trade_id")

    if fill_quantity <= 0 or fill_price <= 0:
        return Response(
            {"error": "Invalid fill data"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)

            if order.is_complete:
                return Response(
                    {"error": "Order already complete"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if fill_quantity > order.remaining_quantity:
                return Response(
                    {"error": "Fill quantity exceeds remaining"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            
            commission = float(fill_quantity) * float(fill_price) * 0.001  # 0.1% fee

            # Create fill record
            OrderFill.objects.create(
                order=order,
                trade_id=trade_id,
                quantity=fill_quantity,
                price=fill_price,
                commission=commission,  
            )

            # Update order
            order.filled_quantity = F("filled_quantity") + fill_quantity

            
            if order.avg_fill_price is None:
                order.avg_fill_price = float(fill_price)
            else:
                
                total_filled = float(order.filled_quantity) + float(fill_quantity)
                old_value = order.avg_fill_price * float(order.filled_quantity)
                new_value = float(fill_price) * float(fill_quantity)
                order.avg_fill_price = (old_value + new_value) / total_filled

            # Check if fully filled
            if fill_quantity >= order.remaining_quantity:
                order.status = "filled"
                order.filled_at = datetime.now()  
            else:
                order.status = "partial"

            order.save()

            # Update position
            
            position, created = Position.objects.get_or_create(
                user_id=order.user_id,
                symbol=order.symbol,
                defaults={"quantity": Decimal("0"), "avg_cost": 0.0},
            )

            if order.side == "buy":
                position.quantity = F("quantity") + fill_quantity
            else:
                position.quantity = F("quantity") - fill_quantity

            
            position.version = F("version") + 1
            position.save()

            publish_order_event(order, "order.filled" if order.status == "filled" else "order.partial_fill", {
                "order_id": str(order.id),
                "fill_quantity": str(fill_quantity),
                "fill_price": str(fill_price),
                "trade_id": str(trade_id),
            })

    except Order.DoesNotExist:
        return Response(
            {"error": "Order not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Refresh from DB
    order.refresh_from_db()

    return Response({
        "order_id": str(order.id),
        "status": order.status,
        "filled_quantity": str(order.filled_quantity),
        "remaining_quantity": str(order.remaining_quantity),
    })


@api_view(["GET"])
def health(request: Request) -> Response:
    """Health check endpoint."""
    return Response({"status": "healthy", "service": "orders"})
