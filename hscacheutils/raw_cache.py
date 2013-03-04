"""Use raw memcache because its more appropriate for sharing cache between multiple applications
       and systems, the django cache stuff adds a bunch extra versioning on the cache key, and you need
       to specify a prefix in your settings.py this decorator will just work.
       Key prefix must be a callable"""

import memcache
import sys
import traceback

try:
    from hubspot.hsutils import get_setting, get_setting_default
except ImportError:
    from hscacheutils.setting_wrappers import get_setting, get_setting_default

try:
    from django.core.cache import get_cache
except ImportError:
    get_cache = None
    sys.stderr.write("Warning: error importing the django cache\n")
    from hscacheutils import simple_memory_cache
    
# The maximum timeout to use if you want to cache values in memcache as long as possible.
# It is only ~30 days (in seconds) because that is the highest timeout that memcache
# allows before it starts treating the timeout as a timestamp instead of a # of seconds.
MAX_MEMCACHE_TIMEOUT = 2591999

class ClientPool(object):
    _pool = dict()

    @classmethod
    def get(cls,servers):
        key = str(servers)
        if key not in ClientPool._pool:
            ClientPool._pool[key] = memcache.Client(servers)
        return ClientPool._pool.get(key)
def raw_memcache(timeout, key_prefix, servers):
    '''
    A decorator for caching the results of a function using the passed in 
    memcached server
    '''
    def decorator(original_f):
        def wrapped_f(*args,**kwargs):
            client = ClientPool.get(servers)
            cache_key = key_prefix(*args,**kwargs) + ":" + original_f.__name__
            value = client.get(cache_key)
            if value:
                return value
            value = original_f(*args, **kwargs)
            client.add(cache_key, value, timeout)
            return value
        return wrapped_f
    return decorator


def load_cache():
    '''
    If the RAW_CACHE_NAME is defined in settings, load the cache of that name.

    Otherwise, load the cache that has the exact same settings as the default cache,
    except with no 'KEY_PREFIX' set
    '''
    # If no django installed, we use the local memory cache
    if not get_cache:
        return simple_memory_cache
    cache_name = get_setting_default('RAW_CACHE_NAME', None)
    if cache_name:
        return get_cache(cache_name)
    conf = get_setting('CACHES').get('default')
    backend = conf['BACKEND']
    raw_conf_dict = {}
    for key in ('LOCATION', 'TIMEOUT'):
        val = conf.get(key)
        if val != None:
            raw_conf_dict[key] = val
    raw_conf_dict['KEY_FUNCTION'] = lambda key, key_prefix, version: key
    the_cache = get_cache(backend, **raw_conf_dict)
    return the_cache

cache = load_cache()


