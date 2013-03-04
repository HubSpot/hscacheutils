# Basic settings helpers (we've overridden them for internal HubSpot usage)
import sys

try:
    from django.conf import settings as settings_obj

    if not settings_obj.configured:
        sys.stderr.write("Warning: django settings not configured, falling back to a non-django settings implementation.")
        raise ImportError("Django settings must be configured before importing settings_wrappers (or it will just fallback on a non-django settings implementation.")

except ImportError:
    class SimpleSettings: pass
    settings_obj = SimpleSettings()

def get_setting(property):
    upper_p = property.upper()
    return getattr(settings_obj, upper_p)

def get_setting_default(property, default_value):
    upper_p = property.upper()
    return getattr(settings_obj, upper_p, default_value)

def _set_setting(property, value):
    """
    A for-tests only method to override a setting at runtime.
    """
    setattr(settings_obj, property.upper(), value)
