from nose.tools import eq_
from time import time

from hscacheutils.raw_cache import cache
from hscacheutils import simple_memory_cache

def test_cache():
    now = time()
    key = 'unittestnowtimeisrawcache:%s' % now
    cache.set(key, now)
    
    val = cache.get(key)
    # NOTE: since some configs will have a dummy cache, we can't validate whether the cache
    # actually worked, really we are just testing to see if an exception was thrown

def test_simple_memory_cache_get_many():
    now = time()
    now2 = time()

    key1 = 'unittestnowtimeisrawcache1:%s' % now
    key2 = 'unittestnowtimeisrawcache2:%s' % now2

    simple_memory_cache.set(key1, now)
    simple_memory_cache.set(key2, now2)

    vals = simple_memory_cache.get_many([key1, key2])

def test_simple_memory_cache_set_many():
    now = time()
    now2 = time()

    key1 = 'unittestnowtimeisrawcache1:%s' % now
    key2 = 'unittestnowtimeisrawcache2:%s' % now2

    simple_memory_cache.set_many({
        "key1": now,
        "key2": now2
    })
