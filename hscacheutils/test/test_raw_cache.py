from nose.tools import eq_
from time import time

from hscacheutils.raw_cache import cache

def test_cache():
    now = time()
    key = 'unittestnowtimeisrawcache:%s' % now
    cache.set(key, now)
    
    val = cache.get(key)
    # NOTE: since some configs will have a dummy cache, we can't validate whether the cache
    # actually worked, really we are just testing to see if an exception was thrown
