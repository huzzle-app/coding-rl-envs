"""
TalentFlow Accounts Celery Tasks
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta


@shared_task
def cleanup_expired_tokens():
    """Remove expired refresh tokens from the database."""
    from .models import RefreshToken

    cutoff = timezone.now() - timedelta(days=7)  # Keep for 7 days after expiry

    deleted, _ = RefreshToken.objects.filter(
        expires_at__lt=cutoff
    ).delete()

    return {'deleted_tokens': deleted}


@shared_task
def cleanup_expired_oauth_states():
    """Remove expired OAuth state parameters."""
    from .models import OAuthState

    deleted, _ = OAuthState.objects.filter(
        expires_at__lt=timezone.now()
    ).delete()

    return {'deleted_states': deleted}


@shared_task
def send_email_verification(user_id: int):
    """Send email verification to user."""
    from django.core.mail import send_mail
    from .models import User

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {'error': 'User not found'}

    # Generate verification token (simplified)
    import secrets
    token = secrets.token_urlsafe(32)

    # In real implementation, store token and send actual email
    send_mail(
        subject='Verify your TalentFlow email',
        message=f'Click here to verify: https://talentflow.example/verify?token={token}',
        from_email='noreply@talentflow.example',
        recipient_list=[user.email],
        fail_silently=True,
    )

    return {'sent_to': user.email}


@shared_task
def sync_user_from_oauth_provider(user_id: int, provider: str):
    """Sync user data from OAuth provider."""
    from .models import User

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {'error': 'User not found'}

    # In real implementation, fetch latest user data from provider
    # and update local user record

    return {'synced': True, 'user_id': user_id, 'provider': provider}
