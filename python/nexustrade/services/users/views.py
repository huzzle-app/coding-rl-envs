"""Users service views."""
import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.request import Request

from services.users.models import UserProfile, BankAccount

logger = logging.getLogger(__name__)


@api_view(["GET"])
def get_profile(request: Request, user_id: str) -> Response:
    """
    Get user profile.

    BUG I5: IDOR - No check if requester owns this profile
    """
    
    # Should verify request.user.id == user_id
    try:
        profile = UserProfile.objects.get(user_id=user_id)
    except UserProfile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    
    return Response({
        "user_id": str(profile.user_id),
        "full_name": profile.full_name,
        "account_number": profile.account_number,  
        "account_type": profile.account_type,
        "trading_tier": profile.trading_tier,
        "kyc_verified": profile.kyc_verified,
    })


@api_view(["PUT"])
def update_profile(request: Request, user_id: str) -> Response:
    """
    Update user profile.

    BUG I7: Mass assignment - trading_tier can be changed
    """
    try:
        profile = UserProfile.objects.get(user_id=user_id)
    except UserProfile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    data = request.data

    
    # User can set trading_tier, kyc_verified, etc.
    for field in ["full_name", "phone", "trading_tier", "kyc_verified"]:
        if field in data:
            setattr(profile, field, data[field])

    profile.save()

    return Response({"status": "updated"})


@api_view(["GET"])
def get_bank_accounts(request: Request, user_id: str) -> Response:
    """
    Get user's bank accounts.

    BUG I5: IDOR - No authorization check
    """
    
    accounts = BankAccount.objects.filter(user__user_id=user_id)

    return Response({
        "accounts": [
            {
                "id": str(a.id),
                "bank_name": a.bank_name,
                "account_number": a.account_number,  
                "is_primary": a.is_primary,
            }
            for a in accounts
        ]
    })


@api_view(["GET"])
def health(request: Request) -> Response:
    return Response({"status": "healthy", "service": "users"})
