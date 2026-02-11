"""
TalentFlow Settings Module

Loads appropriate settings based on environment.
"""
import os

# Import development settings as the default
from .development import *  # noqa: F401, F403

# Check for environment-specific settings
_env = os.environ.get('DJANGO_SETTINGS_MODULE', '')

if 'production' in _env:
    try:
        from .production import *  # noqa: F401, F403
    except ImportError:
        pass
elif 'testing' in _env:
    try:
        from .testing import *  # noqa: F401, F403
    except ImportError:
        pass
