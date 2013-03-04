import inspect
import logging

from time import time

from django.utils.functional import wraps
from django.utils.encoding import smart_str

from cache_utils.utils import _cache_key, _func_info
from cache_utils.utils import sanitize_memcached_key as orig_sanitize_memcached_key

from hscacheutils.raw_cache import cache as raw_cache, MAX_MEMCACHE_TIMEOUT

try:
    from hubspot.hsutils import get_setting_default
except ImportError:
    from hscacheutils.setting_wrappers import get_setting_default
    

def in_gen_cache_debug_mode():
    return get_setting_default('DEBUG_GENERATIONAL_CACHE', False)

# Take from cache_utils and extended (new check for klass and Klass)
# Relying on the name of an agument to determine the type of
# function is quite fragile, but still I think it is a good heruristic
# to prevent our gen_cache.wrap cache keys from having the self/cls
# arg inserted into them.
def _func_type(func):
    """ returns if callable is a function, method or a classmethod """
    argnames = func.func_code.co_varnames[:func.func_code.co_argcount]
    if len(argnames) > 0:
        first_arg = argnames[0].lower()

        if first_arg == 'self':
            return 'method'
        if first_arg in ('cls', 'klass', 'kls'):
            return 'classmethod'

    return 'function'

# Total complete hack to get the names of the current memcache servers.
# Used mostly for debugging sake to make sure we are actually talking
# to the memcache boxes that we think we should be talking to.
def current_raw_caching_servers():
    return raw_cache.__dict__['_servers']


class GenCachedBuilder(object):

    def __init__(self, timeout, generations, exclude=None):
        self.timeout = timeout
        self.generations = generations
        self.exclude = set(exclude or [])

        # Gather all the dynamic generational args (eg. "cms:user_id")
        self.dynamic_gen_tuples = [parse_generation(gen) for gen in self.generations if ':' in gen]

        # Automatically exclude the dynamic generational paramaters from the rest of the cache key
        map(self.exclude.add, [dyn_param for gen, dyn_param in self.dynamic_gen_tuples])

    def func_helper(self, func):
        return GenFuncHelper(self, func)


class GenFuncHelper(object):

    def __init__(self, builder, func):
        self.builder = builder
        self.func = func

        self.func_type = _func_type(func)
        self.arg_names, self.varargs_name, self.keywords_name, self.defaults = getargspec(func)
        self.num_specced_args = len(self.arg_names)

        # All of the non excluded argument names (minus *arg_names and **kwargs)
        self.ignored_args = [arg in builder.exclude for arg in self.arg_names]

        self.ignore_varargs = self.varargs_name and self.varargs_name in builder.exclude
        self.ignore_keywords = self.keywords_name and self.keywords_name in builder.exclude

        self.full_key = None

    def get_key(self, func_name, func_type, args, kwargs):
        self.full_key = key = smart_str(_cache_key(func_name, func_type, args, kwargs))
        return sanitize_memcached_key(key)

    def _cache_func_name(self, args):
        # full name is stored as attribute on first call
        if not hasattr(self, '_full_name'):
            name, _args = _func_info(self.func, args)
            self._full_name = name

    def build_wrapped_cache_key_with_generations(self, args, kwargs):

        self._cache_func_name(args)

        args_in_rest_of_cache_key = [arg for arg, ignored in zip(args, self.ignored_args) if not ignored]
        kwargs_in_rest_of_cache_key = dict()

        if not self.ignore_varargs:
            args_in_rest_of_cache_key += args[self.num_specced_args:]

        if not self.ignore_keywords:
            kwargs_in_rest_of_cache_key = dict(((name, val) for name, val in kwargs.items() if name not in self.builder.exclude))

        # Capture all args by name, including the positional ones (via argspec)
        all_args_by_name = dict(zip(self.arg_names, args))
        all_args_by_name.update(kwargs)

        # Multi-get the generation values
        all_gen_values = multi_generation_values(*self.builder.generations, **all_args_by_name)

        # Add the generations to the kwargs in the cache key
        kwargs_in_rest_of_cache_key.update(all_gen_values)

        return self.get_key(self._full_name, self.func_type, args_in_rest_of_cache_key, kwargs_in_rest_of_cache_key)


def sanitize_memcached_key(key):
    """
    Wrap the django-cache-util's sanitization method, to prevent "cache key too long" warnings
    (since django is still appending it's version number to this key we build).
    """
    return orig_sanitize_memcached_key(key, max_length=240)

def parse_generation(generation):
    """
    Parses a generation, returning both the name and the dynamic parameter
    the generation is based on.

    So parse_generation("nav:user_id") => ("nav", "user_id")
    and parse_generation("nav") => ("nav", None)
    """
    parts = generation.split(':')

    if len(parts) == 1:
        return (parts[0], None)
    else:
        return tuple(parts)


def _gen_cached(timeout, generations, exclude=None, log_misses=False):
    """
    Generational Caching decorator. Can be applied to function, method or classmethod.

    Exclude (tuple or list) is all the arguments you do not want to be a included in
    the cache key.

    Wrapped callable gets `invalidate` methods. Call `invalidate` with
    same arguments as function and the result for these arguments will be
    invalidated.

    Note: based on (and built re-using) django-cache-utils.
    """

    builder = GenCachedBuilder(timeout, generations, exclude=exclude)

    def _cached(func):

        func_helper = builder.func_helper(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = func_helper.build_wrapped_cache_key_with_generations(args, kwargs)
            value = raw_cache.get(key)

            # in case of cache miss recalculate the value and put it to the cache
            if value is None:
                value = func(*args, **kwargs)
                raw_cache.set(key, value, timeout)

                if log_misses is True or in_gen_cache_debug_mode():
                    logging.debug("Cache miss for gen_cache.wrap: %s \n    key = %s" % (generations, func_helper.full_key or key))

            return value

        def invalidate(*args, **kwargs):
            ''' invalidates cache result for function called with passed arguments '''
            if not hasattr(func_helper, '_full_name'):
                return
            key = func_helper.build_wrapped_cache_key_with_generations(args, kwargs)
            raw_cache.delete(key)

            if in_gen_cache_debug_mode():
                logging.info('Invalidating key: %s' % key)

        wrapper.invalidate = invalidate
        return wrapper
    return _cached


GENERATION_KEY = "_gen_%s"


def build_generation_cache_key_suffix(generation, **kwargs):
    generation_name, dynamic_param = parse_generation(generation)

    if not dynamic_param:
        return  generation
    elif dynamic_param not in kwargs:
        raise Exception("Tried to get the value of a dynamic cache generation without passing the necessary keyword paramater (%s)" % dynamic_param)
    else:
        return "%s:%s" % (smart_str(dynamic_param), smart_str(kwargs[dynamic_param]))


def build_generation_cache_key(suffix):
    return sanitize_memcached_key(GENERATION_KEY % smart_str(suffix))


def build_generation_cache_key_full(generation, **kwargs):
    return build_generation_cache_key(build_generation_cache_key_suffix(generation, **kwargs))


def new_generation_value():
    """
    Creates an intial value for a generation. Starts off as microseconds since 1970 to be unique.
    With that, the generation would have to incremented a million times in order to collide with
    a generation invalidation that happened a second later.
    """
    microseconds = int(time() * 1000000)
    return microseconds


def multi_generation_values(*generations, **kwargs):
    keys_suffix = [build_generation_cache_key_suffix(gen, **kwargs) for gen in generations]
    keys = map(build_generation_cache_key, keys_suffix)
    result_values = raw_cache.get_many(keys)
    if in_gen_cache_debug_mode():
        logging.debug('Fetching generations %s => %s' % (keys, result_values))

    # Create new values for all the generations that are empty
    newly_initialized_gens = dict()

    for key in keys:
        if result_values.get(key) is None:
            new_value = new_generation_value()
            result_values[key] = newly_initialized_gens[key] = new_value

    if newly_initialized_gens:
        raw_cache.set_many(newly_initialized_gens, MAX_MEMCACHE_TIMEOUT)

        if in_gen_cache_debug_mode():
            logging.debug('Creating new generations %s => %s' % (newly_initialized_gens, new_value))

    return dict([(keys_suffix[i], result_values.get(key)) for i, key in enumerate(keys)])

def identity_decorator(f):
    return f

class GenerationalCache(object):
    """
    A simple class to wrap all the generational caching functions under a
    single namespace.

    Usage:

        from hscacheutils.generational_cache import gen_cache

        html = gen_cache.get(('nav', 'nav_portal:user_id'), user_id=1)
        gen_cache.set('<html>', ('nav', 'nav_portal:user_id'), user_id=1)
        gen_cache.invalidate(('nav', 'nav_portal:user_id'), user_id=1)

    """
    def build_key(self, *generations, **kwargs):
        all_gen_values = multi_generation_values(*generations, **kwargs)
        gen_list = ["%s:%s" % (gen, value) for gen, value in all_gen_values.items()] 

        add_to_key = kwargs.pop('add_to_key', None)

        if add_to_key is None:
            add_to_key = []
        elif isinstance(add_to_key, basestring):
            add_to_key = [smart_str(add_to_key)]
        elif isinstance(add_to_key, tuple):
            add_to_key = [smart_str(s) for s in add_to_key]
        else:
            add_to_key = [smart_str(add_to_key)]

        return sanitize_memcached_key(','.join(gen_list + add_to_key))

    def get(self, *generations, **kwargs):
        # If use raw, we will avoid the default django behavior of adding a prefix and version number
        # to the cache key, useful for a key between apps
        use_raw = kwargs.get('use_raw')
        if use_raw != None:
            del kwargs['use_raw']

        # TODO, docs! (don't forget the add_to_key param)

        if not self.should_ignore_caching(kwargs):
            key = self.build_key(*generations, **kwargs)
            result = raw_cache.get(key)

            if in_gen_cache_debug_mode():
                logging.debug("gen_cache.get: %s => %s" % (key, result))

            return result


    def set(self, value, *generations, **kwargs):
        # If use raw, we will avoid the default django behavior of adding a prefix and version number
        # to the cache key, useful for a key between apps
        use_raw = kwargs.get('use_raw')
        if use_raw != None:
            del kwargs['use_raw']

        timeout = None

        if 'timeout' in kwargs:
            timeout = kwargs.pop('timeout')

        key = self.build_key(*generations, **kwargs)
        raw_cache.set(key, value, timeout=timeout)

        if in_gen_cache_debug_mode():
            logging.debug("gen_cache.set: %s to %s" % (key, value))

    def delete(self, *generations, **kwargs):
        key = self.build_key(*generations, **kwargs)
        raw_cache.delete(key) 
        if in_gen_cache_debug_mode():
            logging.debug("gen_cache.remove: %s " % (key))


    def invalidate(self, generation, **kwargs):
        key = build_generation_cache_key_full(generation, **kwargs)
        c = raw_cache

        if in_gen_cache_debug_mode():
            logging.debug("gen_cache.invalidate: %s" % (key))

        try:
            val = c.incr(key)
            return val
        except ValueError:
            return c.set(key, 1)
    
    def wrap(self, *generations, **kwargs):
        """
        Generational Caching decorator. Can be applied to function, method or classmethod. It is
        mostly similar to gen_cache.get, but with some additional magic to make your life easier.


        Magic #1: The contents of "value-based" generations are automatically pulled from the
        arguments in wrapped function. Eg.

            @gen_cache.wrap('project_name', 'foo_per_user_id:user_id')
            def foobar(user_id):
                ...

            foobar(53)   -> Uses 'project_name' and 'foo_per_user_id:53' as generations
            foobar(999)  -> Uses 'project_name' and 'foo_per_user_id:999' as generations

            # So when invalidating like so...
            gen_cache.invalidate("for_per_user_id:user_id", user_id=999)

            foobar(53)   -> This is still cached
            foobar(999)  -> This has been invalidated

        So the when foobar is called the ':user_id' part of the value-based generation looks for any
        argument named "user_id", then takes its value to create a generation such as "for_per_user_id:53".
        This means that the "for_per_user_id" generation is only invalidated on a per-portal basis


        Magic #2: All of the arguments (not used in value-based generations described above) are
        automatically appended to the cache key. Eg.

            @gen_cache.wrap('whatever')
            def foobar(something, another=False):
                ...

            # XXX represents the current counter value of the 'whatever' generation

            foobar(1)                -> Uses a cache key roughly like: "whatever:XXX [1]{another=False}"
            foobar(2)                -> Uses a cache key roughly like: "whatever:XXX [2]{another=False}"
            foobar(2, another=True)  -> Uses a cache key roughly like: "whatever:XXX [2]{another=True}"

            # So when invalidating like so...
            gen_cache.invalidate("whatever")

            foobar(1)                -> This has been invalidated
            foobar(2)                -> This has been invalidated
            foobar(2, another=True)  -> This has been invalidated

        If you don't what this behavior for one or more arguments, make sure to put the name of that
        argument(s) in the "exclude" option (see below).


        Magic #3: The cache key will automatically include the current module name, function name, and
        line number. So when this function moves to a different file, is renamed, or moves up or down a
        few lines, the cache will automatically be invalidated.

        (Note, I'm not sure this file/function name magic is worth keeping)


        ## REAL CACHE KEY EXAMPLE


            [cached]hscacheutils.test.test_generational_cache.func_with_lots_of_args:369(['one','two']{'project':1336056824437339,'foobar':'NOThello','user_id':42})
                ^                        ^                          ^             ^        ^                   ^                                ^
                |                        |                          |             |        |                   |                                |
             prefix                 module name                 func name       line #     |   generation & current counter value               |
                                                                                           |                                                    |
                                                                               non-excluded positional args                         non-excluded keyword args


        ## KEYWORD OPTIONS

        timeout=3600 (defaults to None) is the number of seconds before this cache should expire

        exclude=[...] (defaults to empty list) is all the arguments you do not want to automaticaaly be
        a included in the cache key.

        log_misses=True (False by default) will print out some debugging into on every cache miss

        ignore_locally=True (False by default) will disable this caching when ENV == 'local'


        ## EXTRAS

        Wrapped callable gets `invalidate` methods. Call `invalidate` with
        same arguments as function and the result for these arguments will be
        invalidated.


        Gotcha #1: Be careful to use either "self" or "cls" as the first argument name when wrapping
        methods and classmethods. This code relies on those names (see _func_type) to automatically
        chop off the first argument from the cache key.

        Note: based on (and built re-using) django-cache-utils.
        """

        timeout = None

        if 'timeout' in kwargs:
            timeout = kwargs.pop('timeout')

        if self.should_ignore_caching(kwargs):
            return identity_decorator
        else:
            # Only doing a simple function call for simiplicity of the review
            # diff for now. Will move the code over here later.
            return _gen_cached(timeout, generations, **kwargs)

    def should_ignore_caching(self, dict_of_args):
        ignore_locally = dict_of_args.pop('ignore_locally', None)
        ignore_if_setting_is_true = dict_of_args.pop('ignore_if_setting_is_true', None)

        # Skip caching if ignore_locally was set and we're in the local ENV
        if ignore_locally and get_setting_default('ENV', 'local') == 'local':
            return True

        # Skip caching if ignore_if_setting_is_true is set to some setting that is set to some Truthy value
        if ignore_if_setting_is_true and get_setting_default(ignore_if_setting_is_true, False):
            return True


gen_cache = GenerationalCache()


class CustomUseGenCache(object):
    '''
    Use this to create a generational_cache specific to your application:

    my_gen_cache = CustomUseGenCache([
         "cos_templates",
         "cos_template_user_id:user_id",
         "cos_template_path:template_path"],
         timeout=500)

    my_gen_cache.get(user_id=123, template_path='my/path.html')
    my_gen_cache.set(myvalue, user_id=123, template_path='my/path.html')
    my_gen_cache.invalidate('cos_template_user_id:user_id', user_id=123)
    my_gen_cache.invalidate('cos_templates')
    

    @my_gen_cache.wrap()
    def get_template(user_id, path):
        pass
    '''

    def __init__(self, generation_names, timeout=300):
        self.generation_names = generation_names
        self.timeout = timeout

    def build_key(self, **kwargs):
        return gen_cache.build_key(*self.generation_names, **kwargs)

    def get(self, **kwargs):
        self._adjust_kwargs(kwargs)
        return gen_cache.get(*self.generation_names, **kwargs)

    def set(self, value, **kwargs):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        self._adjust_kwargs(kwargs)
        gen_cache.set(value, *self.generation_names, **kwargs)

    def delete(self, **kwargs):
        self._adjust_kwargs(kwargs)
        return gen_cache.delete(*self.generation_names, **kwargs)

    def _adjust_kwargs(self, kwargs):
        # cache_key is a synonym for add_to_key
        if 'cache_key' in kwargs:
            kwargs['add_to_key'] = kwargs['cache_key']
            del kwargs['cache_key']
        

    def invalidate(self, generation=None, **kwargs):
        if generation == None:
            # infer the gernation_name from the kwargs
            for key in kwargs.keys():
                for genname in self.generation_names:
                    if genname.endswith(':' + key):
                        generation = genname
                        break
        gen_cache.invalidate(generation, **kwargs)

    def wrap(self, *args, **kwargs):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        all_args = list(self.generation_names) + list(args)
        return gen_cache.wrap(*all_args, **kwargs)

class DummyGenCache(object):
    '''
    Used as a swap in replacement for CustomUseGenCache if you need to disable caching for whatever reason
    '''
    def get(self, *args, **kwargs):
        return None

    def set(self, *args, **kwargs):
        return None

    def invalidate(self, *args, **kwargs):
        return None

    def wrap(self, *args, **kwargs):
        return None

# From http://kbyanc.blogspot.com/2007/07/python-more-generic-getargspec.html
def getargspec(obj):
    """Get the names and default values of a callable's
       arguments

    A tuple of four things is returned: (args, varargs,
    varkw, defaults).
      - args is a list of the argument names (it may
        contain nested lists).
      - varargs and varkw are the names of the * and
        ** arguments or None.
      - defaults is a tuple of default argument values
        or None if there are no default arguments; if
        this tuple has n elements, they correspond to
        the last n elements listed in args.

    Unlike inspect.getargspec(), can return argument
    specification for functions, methods, callable
    objects, and classes.  Does not support builtin
    functions or methods.
    """
    if not callable(obj):
        raise TypeError("%s is not callable" % type(obj))
    try:
        if inspect.isfunction(obj):
            return inspect.getargspec(obj)
        elif hasattr(obj, 'im_func'):
            # For methods or classmethods drop the first
            # argument from the returned list because
            # python supplies that automatically for us.
            # Note that this differs from what
            # inspect.getargspec() returns for methods.
            # NB: We use im_func so we work with
            #     instancemethod objects also.
            spec = list(inspect.getargspec(obj.im_func))
            spec[0] = spec[0][1:]
            return spec
        elif inspect.isclass(obj):
            return getargspec(obj.__init__)
        elif isinstance(obj, object) and not isinstance(obj, type(arglist.__get__)):
            # We already know the instance is callable,
            # so it must have a __call__ method defined.
            # Return the arguments it expects.
            return getargspec(obj.__call__)
    except NotImplementedError:
        # If a nested call to our own getargspec()
        # raises NotImplementedError, re-raise the
        # exception with the real object type to make
        # the error message more meaningful (the caller
        # only knows what they passed us; they shouldn't
        # care what aspect(s) of that object we actually
        # examined).
        pass
    raise NotImplementedError("do not know how to get argument list for %s" % type(obj))
