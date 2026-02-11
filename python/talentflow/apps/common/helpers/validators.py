"""
Common validation helpers.
"""
import re
from typing import Optional


def validate_email_domain(email: str, allowed_domains: list = None) -> bool:
    """Validate that email domain is allowed."""
    if not email or '@' not in email:
        return False

    domain = email.split('@')[1].lower()

    if allowed_domains:
        return domain in [d.lower() for d in allowed_domains]

    return True


def validate_phone_number(phone: str, country_code: str = 'US') -> bool:
    """Validate phone number format."""
    if not phone:
        return True  # Optional field

    # Remove common formatting
    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)

    if country_code == 'US':
        # US phone: 10 digits, optionally starting with 1
        if cleaned.startswith('1'):
            cleaned = cleaned[1:]
        return len(cleaned) == 10 and cleaned.isdigit()

    # Generic: between 7-15 digits
    return 7 <= len(cleaned) <= 15 and cleaned.isdigit()


def validate_url(url: str, require_https: bool = False) -> bool:
    """Validate URL format."""
    if not url:
        return True  # Optional field

    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    if require_https:
        pattern = r'^https://[^\s/$.?#].[^\s]*$'

    return bool(re.match(pattern, url, re.IGNORECASE))


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Remove path components
    filename = filename.replace('/', '_').replace('\\', '_')

    # Remove potentially dangerous characters
    dangerous = ['<', '>', ':', '"', '|', '?', '*', '\0']
    for char in dangerous:
        filename = filename.replace(char, '_')

    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_len = 255 - len(ext) - 1
        filename = name[:max_name_len] + ('.' + ext if ext else '')

    return filename
