"""
Orders service models.
"""
from decimal import Decimal
from uuid import uuid4
from django.db import models


class Order(models.Model):
    """Trading order model."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("open", "Open"),
        ("partial", "Partially Filled"),
        ("filled", "Filled"),
        ("cancelled", "Cancelled"),
        ("rejected", "Rejected"),
    ]

    SIDE_CHOICES = [
        ("buy", "Buy"),
        ("sell", "Sell"),
    ]

    TYPE_CHOICES = [
        ("market", "Market"),
        ("limit", "Limit"),
        ("stop", "Stop"),
        ("stop_limit", "Stop Limit"),
    ]

    TIF_CHOICES = [
        ("day", "Day"),
        ("gtc", "Good Till Cancelled"),
        ("ioc", "Immediate or Cancel"),
        ("fok", "Fill or Kill"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    symbol = models.CharField(max_length=20, db_index=True)
    side = models.CharField(max_length=10, choices=SIDE_CHOICES)
    order_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    filled_quantity = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    stop_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    
    avg_fill_price = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    time_in_force = models.CharField(max_length=10, choices=TIF_CHOICES, default="day")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    filled_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # idempotency_key = models.CharField(max_length=100, unique=True, null=True)

    class Meta:
        app_label = "orders"
        db_table = "orders"
        
        indexes = [
            models.Index(fields=["user_id"]),
            models.Index(fields=["symbol"]),
            # Missing: Index(fields=["user_id", "status", "created_at"])
        ]

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity

    @property
    def is_complete(self) -> bool:
        return self.status in ("filled", "cancelled", "rejected")


class OrderFill(models.Model):
    """Individual order fill."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="fills")
    trade_id = models.UUIDField(db_index=True)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    
    commission = models.FloatField(default=0.0)
    filled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "orders"
        db_table = "order_fills"


class Position(models.Model):
    """User position in a symbol."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user_id = models.UUIDField()
    symbol = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    
    avg_cost = models.FloatField(default=0.0)
    realized_pnl = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    updated_at = models.DateTimeField(auto_now=True)
    
    version = models.IntegerField(default=0)

    class Meta:
        app_label = "orders"
        db_table = "positions"
        unique_together = [["user_id", "symbol"]]


class OrderEvent(models.Model):
    """Order event log for event sourcing."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    order_id = models.UUIDField(db_index=True)
    event_type = models.CharField(max_length=50)
    event_data = models.JSONField()
    sequence_number = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    

    class Meta:
        app_label = "orders"
        db_table = "order_events"
        indexes = [
            models.Index(fields=["order_id", "sequence_number"]),
        ]
