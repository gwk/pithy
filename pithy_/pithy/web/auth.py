# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Privilege sets and declarative route access policies.

An empty request privilege set means anonymous. Every nonempty set must contain the reserved
`authenticated` privilege. Applications choose all other names; matching is exact, with no namespace syntax.
`WebApp.authenticate` returns the effective privileges; application user data can live in `Request.ctx`.
When reducing privileges for a request, preserve `authenticated`.

`requires_privileges` and `allow_public` are decorators that attach metadata to their targets;
`declare_access` attaches the same metadata directly, e.g. to generated handlers.
They apply to Endpoint handler methods, GET functions, and RoutableHandler classes; see `freeze_required_privileges`.
The Router validates and snapshots policies at registration. Simple WebApps declare access on `handle_request`.
The server checks the resolved destination before obtaining its handler or reading request bodies.
Direct calls to decorated functions do not enforce access; use `check_access` for explicit checks.
'''

from collections.abc import Callable
from http import HTTPStatus
from typing import Any
from urllib.parse import urlsplit

from .errors import BadRequestError, ForbiddenError, ResponseError, UnauthorizedError
from .handler import RoutableHandler
from .request import Request


_context_keywords_ = ['access control', 'anonymous', 'authentication', 'authorization', 'csrf', 'origin check',
  'privileges', 'same origin']


type Privileges = frozenset[str]
"Effective or required privilege names. Effective nonempty sets must include 'authenticated'."

_access_attr = '_web_required_privileges'
'The attribute in which the access decorators store their declaration.'


def requires_privileges[F:Callable[...,Any]](*privileges:str) -> Callable[[F],F]:
  '''
  Decorator declaring that a route requires every listed privilege; use `authenticated` for any authenticated caller.
  Empty declarations and repeated access decorators are errors. Use `allow_public` for public routes.
  Applied to a RoutableHandler class, the requirement covers every method the class accepts.
  '''
  if not privileges: raise ValueError('requires_privileges needs at least one privilege; use allow_public for public routes.')
  required = frozenset(privileges)
  _validate_names(required)
  def decorate(fn:F) -> F:
    return declare_access(fn, required)
  return decorate


def allow_public[F:Callable[...,Any]](fn:F) -> F:
  'Decorator declaring that a route permits anonymous callers. Authentication and deployment checks still apply.'
  return declare_access(fn, frozenset())


def declare_access[F:Callable[...,Any]](target:F, required:Privileges) -> F:
  '''
  Attach an access declaration to a handler function or RoutableHandler class and return it.
  The decorators call this; call it directly to declare access on generated handlers, as `get_endpoint` does.
  An empty set declares the target public. A target may be declared once; a subclass may redeclare its inherited access.
  '''
  if isinstance(target, type):
    if not issubclass(target, RoutableHandler):
      raise TypeError(f'Access decorators apply to handler functions and RoutableHandler classes, not {target.__qualname__}; '
        'decorate the handle_request method of a WebApp.')
  elif not callable(target): raise TypeError('Access decorators apply to handler functions and RoutableHandler classes.')
  if not isinstance(required, frozenset): raise TypeError('Required privileges must be a frozenset of privilege names.')
  _validate_names(required)
  if _access_attr in getattr(target, '__dict__', ()):
    raise TypeError('A handler must have exactly one access declaration.')
  #^ A class inherits its bases' declarations; checking its own namespace lets a subclass redeclare.
  setattr(target, _access_attr, required)
  return target


def check_access(privileges:Privileges, required:Privileges) -> None:
  '''
  Require all named privileges, raising 401 for anonymous callers or 403 otherwise.
  The effective privileges must already be validated; the server does so with `validate_privileges` after authentication.
  '''
  if required <= privileges: return
  if 'authenticated' not in privileges: raise UnauthorizedError('Authentication required.')
  raise ForbiddenError('Insufficient privileges.')


def validate_privileges(privileges:Privileges) -> None:
  'Reject malformed authentication results as programming errors, including nonempty sets without authenticated.'
  if not isinstance(privileges, frozenset): raise TypeError('Authentication must return a frozenset of privilege names.')
  _validate_names(privileges)
  if privileges and 'authenticated' not in privileges:
    raise ValueError('Nonempty effective privileges must contain authenticated.')


def declared_access(fn:object) -> Privileges|None:
  'Read explicit decorator metadata; None means no declaration, distinct from an explicitly public empty set.'
  required = getattr(fn, _access_attr, None)
  if required is None: return None
  if not isinstance(required, frozenset): raise TypeError('Access metadata must be a frozenset of privilege names.')
  _validate_names(required)
  return required


def freeze_required_privileges(handler_cls:type[RoutableHandler], *, default_public:bool) -> frozendict[str,Privileges]:
  '''
  Validate and freeze the required privileges of a route handler class for every method it accepts.

  Decorating the class declares access for every accepted method. An Endpoint may instead decorate each handler method;
  decorating both the class and its methods raises TypeError. Other handler classes can only be decorated as a whole.
  Subclasses inherit access declared by a base class decorator, and may be decorated to replace it.
  HEAD always shares the GET requirement.
  Undeclared methods raise TypeError unless `default_public` is true, which makes them public.
  The Router and the Starlette adapter both use this, so that one handler class has the same policy on either server.
  '''
  accepted = {'GET' if m == 'HEAD' else m for m in handler_cls._methods}
  targets = handler_cls._access_targets()
  requirements:dict[str,Privileges] = {}
  for method in accepted:
    if (required := declared_access(targets.get(method))) is not None: requirements[method] = required
  if (class_required := declared_access(handler_cls)) is not None:
    if requirements:
      raise TypeError(f'{handler_cls.__qualname__} declares access on both the class and handler methods: '
        f'{sorted(requirements)}.')
    requirements = dict.fromkeys(accepted, class_required)
  if missing := accepted - set(requirements):
    if not default_public:
      raise TypeError(f'{handler_cls.__qualname__} omits access declarations: {sorted(missing)}.')
    requirements.update(dict.fromkeys(missing, frozenset()))
  return frozendict({method: requirements['GET' if method == 'HEAD' else method] for method in handler_cls._methods})


class SameOriginCheck:
  '''
  A callable that rejects a request whose headers show it did not come from `origin`, except a top-level navigation to it.

  Construct it once from the deployment's public origin, e.g. `https://example.com`, and call it from
  `WebApp.check_request`, so that cross-site requests are refused before any credential is read.
  Construction validates `origin` and raises ValueError, so that a misconfigured origin fails at startup.
  `origin` must be an HTTP(S) origin URI: a scheme and authority (host and optional port), with no other trailing parts.
  It must be spelled as browsers send it: lowercase, and without the scheme's default port.

  Each call checks the request headers:
  * The Host header must equal the authority of `origin`, ignoring case; this defends against DNS rebinding.
    A mismatch raises 421 Misdirected Request, which RFC 9110 specifies for a target URI the server does not serve;
    a missing Host header raises 400.
  * The Origin header, when present, must equal `origin`. Browsers send it on every cross-origin request except GET
    and HEAD navigations, so this is the CSRF check: cross-site form posts fail here, including redirected ones.
  * A Sec-Fetch-Site header of 'cross-site' is refused unless the request is a GET or HEAD top-level navigation,
    i.e. Sec-Fetch-Mode is 'navigate' and Sec-Fetch-Dest is 'document'. Browsers send these headers even when Origin
    is omitted. The exemption admits links from other sites and redirects back from sign-in providers;
    such navigations carry no body and must be free of side effects. Cross-site frames, subresources and fetches are refused.
  The Origin and Sec-Fetch-Site checks raise ForbiddenError with a reason naming the failed check.
  An application that must accept cross-site posts, e.g. a payment callback, should exempt those paths before calling this.
  '''

  __slots__ = ('origin', 'authority')

  origin:str
  'The validated origin, e.g. `https://example.com`.'

  authority:str
  'The host and optional port of `origin`, which the Host header must match.'


  def __init__(self, origin:str) -> None:
    scheme, sep, authority = origin.partition('://')
    error = f'origin must be an HTTP(S) scheme and host with an optional port, without other components: {origin!r}.'
    if (scheme not in ('http', 'https') or not sep or not authority
     or any(c in authority for c in '/?#@\\') or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in origin)):
      raise ValueError(error)
    try:
      parsed = urlsplit(origin)
      if not parsed.hostname or authority.endswith(':'): raise ValueError(error)
      port = parsed.port # Validates the port's syntax and range.
    except ValueError as exc:
      raise ValueError(error) from exc
    if authority != authority.lower() or port == (443 if scheme == 'https' else 80):
      raise ValueError(f'origin must be lowercase without a default port, as browsers send it: {origin!r}.')
    self.origin = origin
    self.authority = authority


  def __repr__(self) -> str: return f'{type(self).__name__}({self.origin!r})'


  def __call__(self, request:Request) -> None:
    origin = self.origin
    headers = request.headers
    if (host := headers.get('host')) is None:
      raise BadRequestError('Missing Host header.')
    if host.lower() != self.authority:
      raise ResponseError(HTTPStatus.MISDIRECTED_REQUEST, f'Invalid host. Open {origin}/ instead.')
    if headers.get('origin', origin) != origin:
      raise ForbiddenError('Invalid origin.')
    if headers.get('sec-fetch-site') == 'cross-site' and not (request.method in ('GET', 'HEAD')
     and headers.get('sec-fetch-mode') == 'navigate' and headers.get('sec-fetch-dest') == 'document'):
      raise ForbiddenError('Cross-site request.')



def _validate_names(privileges:Privileges) -> None:
  if any(not isinstance(name, str) or not name for name in privileges):
    raise TypeError('Privilege names must be nonempty strings.')
