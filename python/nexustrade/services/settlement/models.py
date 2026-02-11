"""Settlement service models."""
from decimal import Decimal
from uuid import uuid4
from django.db import models


class Settlement(models.Model):
    """Trade settlement record."""
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    trade_id = models.UUIDField(unique=True)
    buyer_id = models.UUIDField()
    seller_id = models.UUIDField()
    symbol = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    
    trade_date = models.DateField()
    settlement_date = models.DateField()
    status = models.CharField(max_length=20, default="pending")  # pending, settled, failed
    
    buyer_debited = models.BooleanField(default=False)
    seller_credited = models.BooleanField(default=False)
    assets_transferred = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "settlement"
        db_table = "settlements"


class SettlementFailure(models.Model):
    """Failed settlement tracking."""
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    settlement = models.ForeignKey(Settlement, on_delete=models.CASCADE)
    failure_reason = models.TextField()
    
    compensation_status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "settlement"
        db_table = "settlement_failures"
