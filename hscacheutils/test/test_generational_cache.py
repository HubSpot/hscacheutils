from time import time
import random

from nose.tools import ok_, eq_
from django.conf import settings
# In order to import bits of the Django test machinery, you either need the
# env variable DJANGO_SETTINGS_MODULE, or to explicitly call
# settings.configure(). The below code will work properly in either case
if not settings.configured:
    settings.configure()

try:
    from hubspot.hsutils import _set_setting, get_setting_default
except ImportError:
    from hscacheutils.setting_wrappers import _set_setting, get_setting_default


from hscacheutils.generational_cache import gen_cache, CustomUseGenCache


def test_genenerational_cache_1():
    @gen_cache.wrap("project", timeout=180)
    def func_no_args():
        return time() + random.randint(0, 10000000)

    first_result = func_no_args()
    ok_(first_result)

    second_result = func_no_args()
    ok_(second_result)

    eq_(first_result, second_result)


def test_genenerational_cache_2():
    @gen_cache.wrap("project", "project:bar", timeout=60)
    def func_with_two_args(foo, bar):
        return time() + random.randint(0, 10000000)

    first_result = func_with_two_args(1, 2)
    ok_(first_result)

    second_result = func_with_two_args(1, 2)
    ok_(second_result)

    ok_(first_result == second_result)

    third_result = func_with_two_args(10, 2)
    fourth_result = func_with_two_args(1, 20)

    ok_(second_result != third_result)
    ok_(second_result != fourth_result)


def test_genenerational_cache_3():
    @gen_cache.wrap("project", "project:foo", timeout=60)
    def func_with_multiple_args(foo, *args):
        return time() + random.randint(0, 10000000)

    first_result = func_with_multiple_args(1, 2, 3, 4, 5)
    ok_(first_result)

    second_result = func_with_multiple_args(1, 2, 3, 4, 5)
    ok_(second_result)

    ok_(first_result == second_result)

    third_result = func_with_multiple_args(10, 2, 3, 4, 5)
    fourth_result = func_with_multiple_args(1, 20, 3, 4, 5)
    fifth_result = func_with_multiple_args(1, 2, 30, 4, 5)
    sixth_result = func_with_multiple_args(1, 2, 3, 40, 5)
    seventh_result = func_with_multiple_args(1, 2, 3, 4, 50)
    eighth_result = func_with_multiple_args(1, 2, 3, 4, 5, 6)
    ninth_result = func_with_multiple_args(1)

    ok_(second_result != third_result)
    ok_(second_result != fourth_result)
    ok_(second_result != fifth_result)
    ok_(second_result != sixth_result)
    ok_(second_result != seventh_result)
    ok_(second_result != eighth_result)
    ok_(second_result != ninth_result)


def test_genenerational_cache_4a():
    @gen_cache.wrap("project", timeout=60)
    def func_with_keyword_args(foobar=None, **kwargs):
        return time() + random.randint(0, 10000000)

    first_result = func_with_keyword_args()
    ok_(first_result)

    second_result = func_with_keyword_args()
    ok_(second_result)
    ok_(first_result == second_result)


def test_genenerational_cache_4b():
    @gen_cache.wrap("project", "project:foobar", timeout=60)
    def func_with_keyword_args(foobar=None, **kwargs):
        return time() + random.randint(0, 10000000)

    some_list = [1, 2, 3]

    first_result = func_with_keyword_args(foobar=some_list, portal_id=53)
    ok_(first_result)

    second_result = func_with_keyword_args(foobar=some_list, portal_id=53)
    ok_(second_result)
    ok_(first_result == second_result)

    third_result = func_with_keyword_args(foobar=[1, 2, 3], portal_id=53)
    third_result_b = func_with_keyword_args(foobar=[1, 2, 3, 4], portal_id=53)
    fourth_result = func_with_keyword_args(foobar=some_list, portal_id=9999)
    fifth_result = func_with_keyword_args(foobar=some_list, portal_id=53, other_kwarg=True)

    ok_(second_result == third_result)
    ok_(second_result != third_result_b)
    ok_(second_result != fourth_result)
    ok_(second_result != fifth_result)


def test_genenerational_cache_5():
    @gen_cache.wrap("project", "project:a", "global:portal_id", timeout=3600)
    def func_with_lots_of_args(a, b, foobar=None, **blakwargs):
        return time() + random.randint(0, 10000000)

    first_result = func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    ok_(first_result)

    second_result = func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    ok_(second_result)

    ok_(first_result == second_result)

    third_result = func_with_lots_of_args('one', 'TWO', foobar='hello', portal_id=42)
    fourth_result = func_with_lots_of_args('ONE', 'two', foobar='hello', portal_id=42)
    fifth_result = func_with_lots_of_args('one', 'two', foobar='HELLO', portal_id=42)
    sixth_result = func_with_lots_of_args('one', 'two', foobar='hello', portal_id=9999)

    ok_(second_result != third_result)
    ok_(second_result != fourth_result)
    ok_(second_result != fifth_result)
    ok_(second_result != sixth_result)


def test_genenerational_cache_invalidation():
    @gen_cache.wrap("project", "project:a", "global:portal_id", timeout=3600)
    def func_with_lots_of_args(a, b, foobar=None, **blakwargs):
        return time() + random.randint(0, 10000000)

    first_result = func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)

    gen_cache.invalidate('project')
    second_result = func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    ok_(first_result != second_result)

    gen_cache.invalidate('project:a', a='one')
    third_result = func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    ok_(second_result != third_result)

    gen_cache.invalidate('global:portal_id', portal_id=42)
    fourth_result = func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    ok_(third_result != fourth_result)


def test_genenerational_cache_invalidation_by_fun():
    @gen_cache.wrap("project", "project:a", "global:portal_id", timeout=3600)
    def func_with_lots_of_args(a, b, foobar=None, **blakwargs):
        return time() + random.randint(0, 10000000)

    first_result = func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)

    func_with_lots_of_args.invalidate('one', 'two', foobar='hello', portal_id=42)
    second_result = func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    ok_(first_result != second_result)


def test_dynamic_generations_without_params():
    @gen_cache.wrap("project", "project:a", timeout=180)
    def func_no_args():
        return time() + random.randint(0, 10000000)

    @gen_cache.wrap("project", "global:portal_id", timeout=180)
    def func_no_args2():
        return time() + random.randint(0, 10000000)

    @gen_cache.wrap("project", "global:portal_id", timeout=180)
    def func_no_args3(portal_id=None):
        return time() + random.randint(0, 10000000)

    exception_message = None
    try:
        func_no_args()
    except Exception, e:
        exception_message = e.message

    ok_(exception_message)
    ok_("without passing the necessary keyword paramater" in exception_message)
    ok_("(a)" in exception_message)

    exception_message = None
    try:
        func_no_args2()
    except Exception, e:
        exception_message = e.message

    ok_(exception_message)
    ok_("without passing the necessary keyword paramater" in exception_message)
    ok_("(portal_id)" in exception_message)

    exception_message = None
    try:
        func_no_args3()
    except Exception, e:
        exception_message = e.message

    ok_(exception_message)
    ok_("without passing the necessary keyword paramater" in exception_message)
    ok_("(portal_id)" in exception_message)


# When ignore locally doesn't do its thing because ENV != qa
def test_not_ignore_locally():

    # Temporarily fake the ENV
    old_env = get_setting_default("ENV", None)
    _set_setting('ENV', 'qa')

    @gen_cache.wrap("some_gen", ignore_locally=True)
    def func_no_args():
        return time() + random.randint(0, 10000000)

    first_result = func_no_args()
    ok_(first_result)

    second_result = func_no_args()
    ok_(second_result)

    ok_(first_result == second_result)

    # Reset ENV just in case
    _set_setting('ENV', old_env)

# When ignore locally doesn't do its thing because ignore_locally=False
def test_not_ignore_locally_2():

    # Temporarily fake the ENV
    old_env = get_setting_default("ENV", None)
    _set_setting('ENV', 'local')

    @gen_cache.wrap("some_gen", ignore_locally=False)
    def func_no_args():
        return time() + random.randint(0, 10000000)

    first_result = func_no_args()
    ok_(first_result)

    second_result = func_no_args()
    ok_(second_result)

    ok_(first_result == second_result)

    # Reset ENV just in case
    _set_setting('ENV', old_env)

def test_ignore_if_setting_is_true():

    _set_setting('RANDOM_SETTING', True)

    @gen_cache.wrap("some_gen", ignore_if_setting_is_true='RANDOM_SETTING')
    def func_no_args():
        return time() + random.randint(0, 10000000)

    first_result = func_no_args()
    ok_(first_result)

    second_result = func_no_args()
    ok_(second_result)

    ok_(first_result != second_result)

def test_not_ignore_if_setting_is_true():

    _set_setting('RANDOM_SETTING', False)

    @gen_cache.wrap("some_gen", ignore_if_setting_is_true='RANDOM_SETTING')
    def func_no_args():
        return time() + random.randint(0, 10000000)

    first_result = func_no_args()
    ok_(first_result)

    second_result = func_no_args()
    ok_(second_result)

    ok_(first_result == second_result)

# Test that it just doesn't screw anything up
def test_log_misses():
    @gen_cache.wrap("project", "project:a", "global:portal_id", timeout=3600, log_misses=True)
    def func_with_lots_of_args(a, b, foobar=None, **blakwargs):
        return time() + random.randint(0, 10000000)

    first_result = func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)

    gen_cache.invalidate('project')
    second_result = func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    ok_(first_result != second_result)

def test_not_ignore_if_setting_is_true2():

    # Leave RANDOM_SETTING unset

    @gen_cache.wrap("some_gen", ignore_if_setting_is_true='RANDOM_SETTING')
    def func_no_args():
        return time() + random.randint(0, 10000000)

    first_result = func_no_args()
    ok_(first_result)

    second_result = func_no_args()
    ok_(second_result)

    ok_(first_result == second_result)

def test_instance_methods():
    class BestClassEvar(object):
        @gen_cache.wrap("project", "project:a", "global:portal_id", timeout=3600)
        def func_with_lots_of_args(self, a, b, foobar=None, **blakwargs):
            return time() + random.randint(0, 10000000)

    bce = BestClassEvar()
    first_result = bce.func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    second_result = bce.func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    third_result = bce.func_with_lots_of_args('one', 'NOT two', foobar='hello', portal_id=42)
    fourth_result = bce.func_with_lots_of_args('one', 'two', foobar='NOT hello', portal_id=42)

    ok_(first_result == second_result)

    ok_(first_result != third_result)
    ok_(first_result != fourth_result)

    gen_cache.invalidate('project')
    fifth_result = bce.func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    ok_(first_result != fifth_result)

def test_class_methods():
    class BestClassEvar(object):
        @classmethod
        @gen_cache.wrap("project", timeout=3600)
        def func_with_lots_of_args(Klass, a, b, foobar=None, **blakwargs):
            return time() + random.randint(0, 10000000)

    first_result = BestClassEvar.func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    second_result = BestClassEvar.func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    third_result = BestClassEvar.func_with_lots_of_args('one', 'NOT two', foobar='hello', portal_id=42)
    fourth_result = BestClassEvar.func_with_lots_of_args('one', 'two', foobar='NOT hello', portal_id=42)

    ok_(first_result == second_result)

    ok_(first_result != third_result)
    ok_(first_result != fourth_result)

    gen_cache.invalidate('project')
    fifth_result = BestClassEvar.func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    ok_(first_result != fifth_result)


    # Via instance?
    bce = BestClassEvar()
    first_result = bce.func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    second_result = bce.func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    third_result = bce.func_with_lots_of_args('one', 'NOT two', foobar='hello', portal_id=42)
    fourth_result = bce.func_with_lots_of_args('one', 'two', foobar='NOT hello', portal_id=42)

    ok_(first_result == second_result)

    ok_(first_result != third_result)
    ok_(first_result != fourth_result)

    gen_cache.invalidate('project')
    fifth_result = bce.func_with_lots_of_args('one', 'two', foobar='hello', portal_id=42)
    ok_(first_result != fifth_result)


def test_gen_cache_build_key():
    key = gen_cache.build_key('unittest', 'myproject', 'testnum:num', 'anothergeneration:gen', num=98, gen='anothergen')
    key2 = gen_cache.build_key('unittest', 'myproject', 'testnum:num', 'anothergeneration:gen', num=98, gen='anothergen')
    eq_(key, key2)
    
    gen_cache.invalidate('myproject')
    key3 = gen_cache.build_key('unittest', 'myproject', 'testnum:num', 'anothergeneration:gen', num=98, gen='anothergen')
    ok_(key3 != key2)

    gen_cache.invalidate('testnum:num', num=98)
    key4 = gen_cache.build_key('unittest', 'myproject', 'testnum:num', 'anothergeneration:gen', num=98, gen='anothergen')
    ok_(key3 != key4)

def test_really_long_gen_cache_build_key():
    SUPER_LONG_STRING = 'lorem' * 84
    SLIGHTLY_LONG_GEN = 'anothergeneration222222222222222222222222222222222222222222222222222222222222222:gen'

    key = gen_cache.build_key('unittest', 'myproject', 'testnum:num', SLIGHTLY_LONG_GEN, SUPER_LONG_STRING, num=98, gen='anothergen')
    key2 = gen_cache.build_key('unittest', 'myproject', 'testnum:num', SLIGHTLY_LONG_GEN, SUPER_LONG_STRING, num=98, gen='anothergen')
    eq_(key, key2)
    
    gen_cache.invalidate('myproject')
    key3 = gen_cache.build_key('unittest', 'myproject', 'testnum:num', SLIGHTLY_LONG_GEN, SUPER_LONG_STRING, num=98, gen='anothergen')
    ok_(key3 != key2)

    gen_cache.invalidate(SUPER_LONG_STRING)
    key4 = gen_cache.build_key('unittest', 'myproject', 'testnum:num', SLIGHTLY_LONG_GEN, SUPER_LONG_STRING, num=98, gen='anothergen')
    ok_(key4 != key3)

    gen_cache.invalidate(SLIGHTLY_LONG_GEN, gen='anothergen')
    key5 = gen_cache.build_key('unittest', 'myproject', 'testnum:num', SLIGHTLY_LONG_GEN, SUPER_LONG_STRING, num=98, gen='anothergen')
    ok_(key5 != key4)



custom_cache = CustomUseGenCache([
    'customgenz:portal_id',
    'customgenz:blog_id'])

def test_custom_gen_cache():
    blog_id = 17
    portal_id = 123
    key = random.randint(1, 20000000)
    first_val = random.randint(1, 2000000)
    second_val = random.randint(1, 2000000)

    custom_cache.delete(blog_id=blog_id, portal_id=123, cache_key=key)

    val = custom_cache.get(blog_id=blog_id, portal_id=123, cache_key=key)
    eq_(None, val)

    custom_cache.set(value=first_val, blog_id=blog_id, portal_id=123, cache_key=key)

    val = custom_cache.get(blog_id=blog_id, portal_id=123, cache_key=key)
    eq_(first_val, val)

    val = custom_cache.invalidate(portal_id=123)
    eq_(None, val)
    
    custom_cache.set(value=second_val, blog_id=blog_id, portal_id=123, cache_key=key)

    val = custom_cache.get(blog_id=blog_id, portal_id=123, cache_key=key)
    eq_(second_val, val)

    custom_cache.delete(blog_id=blog_id, portal_id=123, cache_key=key)

    val = custom_cache.get(blog_id=blog_id, portal_id=123, cache_key=key)
    eq_(None, val)
    
    

