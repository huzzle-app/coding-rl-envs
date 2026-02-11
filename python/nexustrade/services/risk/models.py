"""Risk service models."""
from decimal import Decimal
from uuid import uuid4
from django.db import models


class RiskProfile(models.Model):
    """User risk profile and limits."""
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user_id = models.UUIDField(unique=True)
    max_position_size = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("100000"))
    max_daily_loss = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("10000"))
    max_order_size = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("10000"))
    max_exposure = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("500000"))
    
    margin_call_threshold = models.FloatField(default=0.25)
    liquidation_threshold = models.FloatField(default=0.15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "risk"
        db_table = "risk_profiles"


class ExposureSnapshot(models.Model):
    """Point-in-time exposure snapshot."""
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    symbol = models.CharField(max_length=20, null=True, blank=True)
    exposure = models.DecimalField(max_digits=20, decimal_places=8)
    
    snapshot_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "risk"
        db_table = "exposure_snapshots"


class MarginAccount(models.Model):
    """User margin account."""
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user_id = models.UUIDField(unique=True)
    equity = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    margin_used = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal("0"))
    
    var_95 = models.FloatField(default=0.0)
    var_99 = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "risk"
        db_table = "margin_accounts"

    @property
    def margin_available(self) -> Decimal:
        return self.equity - self.margin_used

    @property
    def margin_ratio(self) -> float:
        if self.equity == 0:
            return 0.0
        return float(self.margin_used / self.equity)
