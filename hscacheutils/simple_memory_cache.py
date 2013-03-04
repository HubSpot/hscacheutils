"""
So that we don't have to force a django dependency for unittests to pass,
we use this cache in some modules if the django cache is not available
"""

_cache_dict = {}

def delete(key):
    if key in _cache_dict:
        try:
            del _cache_dict[key]
        except KeyError:
            pass
    
def set(key, value, timeout=None):
    _cache_dict[key] = value

def set_many(vals_by_key, timeout=None):
    for key, value in vals_by_key.items():
        _cache_dict[key] = value

def get(key):
    return _cache_dict.get(key)

def get_many(keys):
    result = {}

    for key in keys:
        result[key] = _cache_dict.get(key)

    return result

def incr(self, key, delta=1):
    if not key in _cache_dict:
        _cache_dict[key] = 0
    _cache_dict[key] += delta
    return _cache_dict[key]
