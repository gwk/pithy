# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.web.app import WebApp
from pithy.web.auth import (allow_public, check_access, declared_access, requires_privileges, SameOriginCheck,
  validate_privileges)
from pithy.web.errors import ForbiddenError, ResponseError, UnauthorizedError
from pithy.web.handler import RoutableHandler
from pithy.web.request import Request
from utest import utest, utest_exc, utest_run, utest_val


def _request(headers:dict[str,str], method:str='GET') -> Request:
  return Request(method=method, scheme='http', host='localhost', port=80, raw_path='/', query_str='', headers=headers,
    client_addr=('127.0.0.1', 0), content_length=None)


@utest_run
def _() -> None:
  'SameOriginCheck: host must match; origin and sec-fetch-site are checked only when present.'
  origin = 'http://127.0.0.1:8000'
  check = SameOriginCheck(origin)
  host = {'host':'127.0.0.1:8000'}

  def status(headers:dict[str,str], method:str='GET') -> int:
    try: check(_request(headers, method))
    except ResponseError as exc: return exc.status.value
    return 200

  utest(200, status, host)
  utest(200, status, {**host, 'origin':origin, 'sec-fetch-site':'same-origin'})
  utest(200, status, {**host, 'origin':origin, 'sec-fetch-site':'same-origin'}, 'POST')
  utest(400, status, {})
  utest(421, status, {'host':'localhost:8000'}) # Misdirected: the server does not serve this authority.
  utest(None, SameOriginCheck('http://localhost:8000'), _request({'host':'LOCALHOST:8000'})) # Ignores case.
  utest(403, status, {**host, 'origin':'https://evil.example'})
  utest(403, status, {**host, 'origin':'null'}) # An opaque origin, e.g. a post redirected across sites.
  utest(403, status, {**host, 'sec-fetch-site':'cross-site'})

  # Cross-site top-level GET navigations are admitted: links from other sites and redirects back from sign-in providers.
  navigation = {**host, 'sec-fetch-site':'cross-site', 'sec-fetch-mode':'navigate', 'sec-fetch-dest':'document'}
  utest(200, status, navigation)
  utest(200, status, navigation, 'HEAD')
  utest(200, status, {**navigation, 'sec-fetch-site':'none'}) # Typed or bookmarked.
  utest(403, status, {**navigation, 'origin':'https://idp.example'}, 'POST') # A cross-site form post fails the Origin check.
  utest(403, status, navigation, 'POST') # A posting navigation is refused even without an Origin header.
  utest(403, status, {**navigation, 'sec-fetch-dest':'iframe'}) # Framing is not top-level.
  utest(403, status, {**navigation, 'sec-fetch-dest':'object'})
  utest(403, status, {**navigation, 'sec-fetch-mode':'no-cors', 'sec-fetch-dest':'image'}) # Subresource inclusion.
  utest(403, status, {**navigation, 'sec-fetch-mode':'cors', 'sec-fetch-dest':'empty'}) # A fetch, even without Origin.


@utest_run
def _() -> None:
  'SameOriginCheck validates its origin at construction.'
  for origin in ('', 'example.com', 'ftp://example.com', 'http://', 'https://example.com/',
   'https://example.com/path', 'https://example.com?', 'https://example.com?query',
   'https://example.com#', 'https://example.com#fragment', 'https://user:pass@example.com',
   'https://example.com\\path', ' https://example.com', 'https://exa\nmple.com', 'https://example.com\x00',
   'https://:443', 'https://example.com:', 'https://example.com:abc', 'https://example.com:65536',
   'https://[::1', 'https://::1', 'http://Localhost:8000', 'https://EXAMPLE.com', 'http://[::ABCD]',
   'http://example.com:80', 'https://example.com:443'):
    utest_exc(ValueError, SameOriginCheck, origin)

  for origin, authority in (('https://example.com', 'example.com'), ('http://localhost:8000', 'localhost:8000'),
   ('http://example.com:443', 'example.com:443'), ('https://example.com:80', 'example.com:80'),
   ('https://example.com:8443', 'example.com:8443'), ('http://[::1]', '[::1]'), ('http://[::1]:8000', '[::1]:8000')):
    check = SameOriginCheck(origin)
    utest(authority, getattr, check, 'authority')
    utest(None, check, _request({'host': authority, 'origin': origin}))


@utest_run
def _() -> None:
  'Authentication results must be immutable and distinguish anonymous from authenticated without application privileges.'
  utest(None, validate_privileges, frozenset())
  utest(None, validate_privileges, frozenset({'authenticated'}))
  utest_exc(TypeError, validate_privileges, {'authenticated'})
  utest_exc(TypeError, validate_privileges, None)
  utest_exc(TypeError, validate_privileges, frozenset({1}))
  utest_exc(TypeError, validate_privileges, frozenset({'authenticated', ''}))
  utest_exc(ValueError, validate_privileges, frozenset({'read'}))
  utest(None, check_access, frozenset(), frozenset())
  utest_exc(UnauthorizedError, check_access, frozenset(), frozenset({'authenticated'}))
  utest(None, check_access, frozenset({'authenticated'}), frozenset({'authenticated'}))
  utest_exc(ForbiddenError, check_access, frozenset({'authenticated'}), frozenset({'read'}))


@utest_run
def _() -> None:
  'Declarations preserve functions and reject ambiguous or malformed policies.'
  def fn(n:int) -> int: return n + 1
  utest_val(None, declared_access(fn))
  utest_val(True, requires_privileges('read')(fn) is fn)
  utest(3, fn, 2) # Direct calls do not authorize.
  utest_val(frozenset({'read'}), declared_access(fn))
  utest_exc(TypeError, allow_public, fn)
  utest_exc(TypeError, requires_privileges('write'), fn)
  utest_exc(ValueError, requires_privileges)
  utest_exc(TypeError, requires_privileges, '')
  utest_exc(TypeError, requires_privileges, 1)

  @allow_public
  def public_fn() -> None: pass
  utest_val(frozenset(), declared_access(public_fn))
  utest_exc(TypeError, requires_privileges('read'), public_fn)


@utest_run
def _() -> None:
  'Access decorators accept RoutableHandler classes only; subclasses inherit access, and each class may be decorated once.'
  @requires_privileges('read')
  class Base(RoutableHandler): pass
  class Child(Base): pass
  utest_val(frozenset({'read'}), declared_access(Child))
  utest_val(frozenset(), declared_access(allow_public(Child)))
  utest_exc(TypeError, requires_privileges('write'), Base)
  utest_exc(TypeError, allow_public, Child)

  class App(WebApp): pass
  class Plain: pass
  utest_exc(TypeError, allow_public, App) # A WebApp declares access on handle_request.
  utest_exc(TypeError, requires_privileges('read'), Plain)
