"""Settlement service views."""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.request import Request

from services.settlement.models import Settlement, SettlementFailure
from shared.utils.time import get_settlement_date

logger = logging.getLogger(__name__)


@api_view(["POST"])
def create_settlement(request: Request) -> Response:
    """
    Create a settlement record for a trade.

    BUG F8: Settlement date doesn't skip weekends/holidays
    """
    data = request.data
    trade_date = datetime.now().date()  

    
    settlement_date = get_settlement_date(datetime.now(), settlement_days=2).date()

    settlement = Settlement.objects.create(
        trade_id=data["trade_id"],
        buyer_id=data["buyer_id"],
        seller_id=data["seller_id"],
        symbol=data["symbol"],
        quantity=Decimal(str(data["quantity"])),
        price=Decimal(str(data["price"])),
        trade_date=trade_date,
        settlement_date=settlement_date,
    )

    return Response({
        "settlement_id": str(settlement.id),
        "settlement_date": settlement_date.isoformat(),
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def process_settlement(request: Request, settlement_id: str) -> Response:
    """
    Process a settlement (transfer funds and assets).

    BUG D3: Saga compensation order wrong on failure
    """
    try:
        settlement = Settlement.objects.get(id=settlement_id)
    except Settlement.DoesNotExist:
        return Response({"error": "Settlement not found"}, status=status.HTTP_404_NOT_FOUND)

    if settlement.status != "pending":
        return Response({"error": "Settlement already processed"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            # Step 1: Debit buyer
            # (Simulated - would call accounts service)
            settlement.buyer_debited = True
            settlement.save()

            # Step 2: Transfer assets
            
            settlement.assets_transferred = True
            settlement.save()

            # Step 3: Credit seller
            settlement.seller_credited = True
            settlement.status = "settled"
            settlement.save()

    except Exception as e:
        
        # Should: credit buyer back, then reverse asset transfer
        # Instead: tries to reverse assets first (which might fail again)
        logger.error(f"Settlement failed: {e}")

        SettlementFailure.objects.create(
            settlement=settlement,
            failure_reason=str(e),
        )

        
        if settlement.assets_transferred:
            # Reverse asset transfer first (wrong - should credit buyer first)
            pass
        if settlement.buyer_debited:
            # Credit buyer back
            pass

        settlement.status = "failed"
        settlement.save()

        return Response({"error": "Settlement failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        "settlement_id": str(settlement.id),
        "status": settlement.status,
    })


@api_view(["GET"])
def health(request: Request) -> Response:
    return Response({"status": "healthy", "service": "settlement"})
