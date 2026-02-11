"""Users service models."""
from uuid import uuid4
from django.db import models


class UserProfile(models.Model):
    """User profile with trading preferences."""
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user_id = models.UUIDField(unique=True)  # References auth.User
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, null=True, blank=True)
    
    account_number = models.CharField(max_length=20, unique=True)
    account_type = models.CharField(max_length=50, default="individual")
    trading_tier = models.CharField(max_length=20, default="basic")  # basic, premium, vip
    kyc_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "users"
        db_table = "user_profiles"


class BankAccount(models.Model):
    """User bank account for deposits/withdrawals."""
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="bank_accounts")
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    routing_number = models.CharField(max_length=50)
    is_primary = models.BooleanField(default=False)
    
    verified = models.BooleanField(default=False)

    class Meta:
        app_label = "users"
        db_table = "bank_accounts"
