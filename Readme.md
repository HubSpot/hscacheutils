A python implementation of [generational caching](http://www.regexprn.com/2011/06/web-application-caching-strategies_05.html).

Three main interfaces are provided:

 - Direct methods `gen_cache.get`, `gen_cache.set`, `gen_cache.invalidate`, and `gen_cache.delete`
 - A function decorator `@gen_cache.wrap`
 - A `CustomUseGenCache` instance


## Direct methods:

```python
from hscacheutils.generational_cache import gen_cache

html = gen_cache.get(('nav', 'nav_portal:user_id'), user_id=1)
gen_cache.set('<html>', ('nav', 'nav_portal:user_id'), user_id=1)
gen_cache.invalidate(('nav', 'nav_portal:user_id'), user_id=1)
```

## The `@gen_cache.wrap` decorator

It can be applied to function, method or classmethod. It is mostly similar to gen_cache.get, but with some additional magic to make your life easier.


### Magic #1:

The contents of "value-based" generations are automatically pulled from the arguments in wrapped function. Eg.

```python
@gen_cache.wrap('project_name', 'foo_per_user_id:user_id')
def foobar(user_id):
    ...

foobar(53)   # Uses 'project_name' and 'foo_per_user_id:53' as generations
foobar(999)  # Uses 'project_name' and 'foo_per_user_id:999' as generations

# So when invalidating like so...
gen_cache.invalidate("for_per_user_id:user_id", user_id=999)

foobar(53)   # This is still cached
foobar(999)  # This has been invalidated
```

So the when foobar is called the ':user_id' part of the value-based generation looks for any
argument named "user_id", then takes its value to create a generation such as "for_per_user_id:53".
This means that the "for_per_user_id" generation is only invalidated on a per-portal basis


### Magic #2:

All of the arguments (not used in value-based generations described above) are automatically appended to the cache key. Eg.

```python
@gen_cache.wrap('whatever')
def foobar(something, another=False):
    ...

# XXX represents the current counter value of the 'whatever' generation

foobar(1)                # Uses a cache key roughly like: "whatever:XXX [1]{another=False}"
foobar(2)                # Uses a cache key roughly like: "whatever:XXX [2]{another=False}"
foobar(2, another=True)  # Uses a cache key roughly like: "whatever:XXX [2]{another=True}"

# So when invalidating like so...
gen_cache.invalidate("whatever")

foobar(1)                # This has been invalidated
foobar(2)                # This has been invalidated
foobar(2, another=True)  # This has been invalidated
```

If you don't what this behavior for one or more arguments, make sure to put the name of that
argument(s) in the "exclude" option (see below).


### Magic #3:

The cache key will automatically include the current module name, function name, and
line number. So when this function moves to a different file, is renamed, or moves up or down a
few lines, the cache will automatically be invalidated.

(Note, I'm not sure this file/function name magic is worth keeping)

### EXTRAS

The wrapped callable gets `invalidate` methods. Call `invalidate` with
same arguments as function and the result for these arguments will be
invalidated.

### KEYWORD OPTIONS

timeout=3600 (defaults to None) is the number of seconds before this cache should expire

exclude=[...] (defaults to empty list) is all the arguments you do not want to automaticaaly be
a included in the cache key.

log_misses=True (False by default) will print out some debugging into on every cache miss

ignore_locally=True (False by default) will disable this caching when ENV == 'local'

### REAL `gen_cache.wraps` cache key example

    [cached]hsdjango.test.test_generational_cache.func_with_lots_of_args:369(['one','two']{'project':1336056824437339,'foobar':'NOThello','user_id':42})
        ^                        ^                          ^             ^        ^                   ^                                ^
        |                        |                          |             |        |                   |                                |
     prefix                 module name                 func name       line #     |   generation & current counter value               |
                                                                                   |                                                    |
                                                                       non-excluded positional args                         non-excluded keyword args




Gotcha #1: Be careful to use either "self" or "cls" as the first argument name when wrapping
methods and classmethods. This code relies on those names (see _func_type) to automatically
chop off the first argument from the cache key.




## A `CustomUseGenCache` instance

```python
custom_cache = CustomUseGenCache([
    'customgenz:user_id',
    'customgenz:blog_id'
])

blog_id = 17
user_id = 123
key = random.randint(1, 20000000)

val = custom_cache.get(blog_id=blog_id, user_id=123, cache_key=key)
custom_cache.set(value=first_val, blog_id=blog_id, user_id=123, cache_key=key)
custom_cache.invalidate(user_id=123)
custom_cache.delete(blog_id=blog_id, user_id=123, cache_key=key)
```


_Note: based on (and built re-using) django-cache-utils._

