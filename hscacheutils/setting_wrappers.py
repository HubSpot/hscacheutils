# Basic settings helpers (we've overridden them for internal HubSpot usage)

from django.conf import settings as dj_settings

def get_setting(property):
    upper_p = property.upper()
    return getattr(dj_settings, upper_p)

def get_setting_default(property, default_value):
    upper_p = property.upper()
    return getattr(dj_settings, upper_p, default_value)

def _set_setting(property, value):
    """
    A for-tests only method to override a setting at runtime.
    """
    setattr(dj_settings, property.upper(), value)
