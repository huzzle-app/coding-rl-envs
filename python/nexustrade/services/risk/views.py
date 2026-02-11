"""Risk service views."""
import logging
import math
from decimal import Decimal
from datetime import datetime
from typing import Optional

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.request import Request
import redis

from services.risk.models import RiskProfile, ExposureSnapshot, MarginAccount

logger = logging.getLogger(__name__)



#   - services/risk/views.py: Invalidate cache when exposure changes
#   - services/orders/views.py: Notify risk service after position updates
#   - services/matching/main.py: Publish exposure-change events after trades
#   - shared/clients/risk.py: Use cache-aside with proper TTL and version check
# Fixing only this file (e.g., adding TTL) won't fully resolve stale reads
# because the Orders and Matching services don't notify Risk of changes.
_exposure_cache = {}
REDIS_URL = "redis://redis:6379/5"


@api_view(["POST"])
def check_order_risk(request: Request) -> Response:
    """
    Check if an order passes risk checks.

    BUG G1: No lock - race condition allows over-exposure
    BUG G4: Timeout causes unfair rejection
    """
    user_id = request.data.get("user_id")
    symbol = request.data.get("symbol")
    side = request.data.get("side")
    quantity = Decimal(str(request.data.get("quantity", 0)))
    price = Decimal(str(request.data.get("price", 0))) if request.data.get("price") else None

    try:
        profile = RiskProfile.objects.get(user_id=user_id)
    except RiskProfile.DoesNotExist:
        profile = RiskProfile.objects.create(user_id=user_id)

    # Calculate order value
    order_value = quantity * (price or Decimal("100"))  # Default price for market orders

    
    # then all execute, exceeding limits

    # Check order size limit
    if order_value > profile.max_order_size:
        return Response({
            "approved": False,
            "reason": "Order size exceeds limit",
            "max_allowed": str(profile.max_order_size),
        })

    # Check exposure
    
    current_exposure = _exposure_cache.get(user_id, Decimal("0"))
    new_exposure = current_exposure + order_value

    if new_exposure > profile.max_exposure:
        return Response({
            "approved": False,
            "reason": "Would exceed exposure limit",
            "current_exposure": str(current_exposure),
            "max_exposure": str(profile.max_exposure),
        })

    
    _exposure_cache[user_id] = new_exposure

    return Response({
        "approved": True,
        "order_value": str(order_value),
        "new_exposure": str(new_exposure),
    })


@api_view(["GET"])
def get_exposure(request: Request, user_id: str) -> Response:
    """
    Get user's current exposure.

    BUG G2: Returns cached/stale data
    """
    symbol = request.query_params.get("symbol")

    
    cache_key = f"{user_id}:{symbol}" if symbol else user_id

    if cache_key in _exposure_cache:
        
        return Response({
            "user_id": user_id,
            "exposure": str(_exposure_cache[cache_key]),
            "cached": True,
        })

    # Calculate from positions (expensive)
    snapshots = ExposureSnapshot.objects.filter(user_id=user_id)
    if symbol:
        snapshots = snapshots.filter(symbol=symbol)

    total_exposure = sum(s.exposure for s in snapshots)
    _exposure_cache[cache_key] = total_exposure

    return Response({
        "user_id": user_id,
        "total_exposure": str(total_exposure),
        "positions": [
            {"symbol": s.symbol, "exposure": str(s.exposure)}
            for s in snapshots
        ],
    })


@api_view(["GET"])
def get_margin_status(request: Request, user_id: str) -> Response:
    """
    Get user's margin status.

    BUG G3: Threshold comparison off-by-one
    """
    try:
        account = MarginAccount.objects.get(user_id=user_id)
        profile = RiskProfile.objects.get(user_id=user_id)
    except (MarginAccount.DoesNotExist, RiskProfile.DoesNotExist):
        return Response({
            "error": "Account not found",
        }, status=status.HTTP_404_NOT_FOUND)

    margin_ratio = account.margin_ratio

    
    # At exactly 0.25, should NOT trigger margin call, but does
    margin_call = margin_ratio >= profile.margin_call_threshold
    liquidation = margin_ratio >= profile.liquidation_threshold

    return Response({
        "user_id": user_id,
        "equity": str(account.equity),
        "margin_used": str(account.margin_used),
        "margin_available": str(account.margin_available),
        "margin_ratio": margin_ratio,
        "margin_call": margin_call,
        "liquidation_warning": liquidation,
    })


@api_view(["GET"])
def calculate_var(request: Request, user_id: str) -> Response:
    """
    Calculate Value at Risk.

    BUG G6: Large positions cause overflow to NaN
    """
    confidence = float(request.query_params.get("confidence", 0.99))
    horizon = int(request.query_params.get("horizon", 1))

    try:
        account = MarginAccount.objects.get(user_id=user_id)
    except MarginAccount.DoesNotExist:
        return Response({"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND)

    
    # Using float arithmetic that can produce NaN/Inf
    portfolio_value = float(account.equity)

    # Simplified VaR calculation (would use historical data in real system)
    volatility = 0.02  # 2% daily volatility assumption
    z_score = 2.33 if confidence >= 0.99 else 1.65  # Normal distribution quantiles

    
    var = portfolio_value * volatility * z_score * math.sqrt(horizon)

    
    if math.isnan(var) or math.isinf(var):
        logger.warning(f"VaR calculation produced invalid result for user {user_id}")
        
        account.var_99 = var
        account.save()

    return Response({
        "user_id": user_id,
        "var": var if not (math.isnan(var) or math.isinf(var)) else "NaN",
        "confidence": confidence,
        "horizon_days": horizon,
    })


@api_view(["GET"])
def health(request: Request) -> Response:
    """Health check endpoint."""
    return Response({"status": "healthy", "service": "risk"})
