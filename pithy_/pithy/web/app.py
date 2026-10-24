# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from .auth import declared_access, Privileges
from .destination import Destination
from .errorrender import (bare_media_type, default_error_extension_media_types, default_error_media_type,
  default_error_renderers, error_media_type_for_path, ErrorRenderer)
from .errors import ResponseError
from .handler import RequestHandler
from .request import Request
from .response import Response


_context_keywords_ = ['application', 'dispatch', 'http', 'request lifecycle', 'routing', 'web framework']


class WebApp(RequestHandler):
  '''
  The application object that the server consults for every request.

  The server drives a fixed lifecycle, in this order:
  1. `check_request` refuses requests the deployment does not serve at all, e.g. from another origin.
  2. `authenticate` identifies the requester from its credentials; the result becomes `request.privileges`.
  3. `resolve_destination` selects a recipient and its access requirements without constructing a handler.
  4. The server checks the authenticated privileges against the destination requirements.
  5. The destination's `get_handler` returns or constructs the authorized handler.
  6. The handler's `handle_expect_100_continue`, when applicable, accepts or rejects the request before its body is read.
  7. If not rejected, the handler's `prepare_for_request` prepares to handle the request, e.g. by reading the body.
  8. The handler's `handle_request` produces a response.
  Admission, authentication and routing precede handler preparation; overrides of those steps must not read the body.

  A ResponseError raised during these steps is turned into a response by `error_response`,
  or by the built-in plain text renderer if that returns None or raises; a raise is logged.
  The default selects a renderer from `error_renderers` by the request path extension; see `error_media_type_for`.
  A 401 response without a WWW-Authenticate header receives the challenge from `www_authenticate_for`, if any.

  Normal responses, rejections from step 6 and responses produced by `error_response` pass through `finish_response`.
  Protocol rejections before Request construction bypass the application entirely.
  An unhandled exception elsewhere, including from `finish_response`, produces a bare 500 without consulting the app again.
  Likewise, a body read that raises ClientProtocolError produces a bare response with its status, such as 400 or 408.
  '''

  # Snapshotted from handle_request when the subclass is defined.
  _required_privileges:ClassVar[Privileges|None] = None

  error_media_type:ClassVar[str] = default_error_media_type
  'The bare media type of error responses for paths without an extension, e.g. `text/html` for a page app.'

  error_extension_media_types:ClassVar[Mapping[str,str]] = default_error_extension_media_types
  '''
  Lowercase path extensions mapped to the bare media type of their error responses; other extensions get plain text.
  Override with a mapping that extends `default_error_extension_media_types`, e.g. to add `jsonl`.
  '''

  error_renderers:ClassVar[Mapping[str,ErrorRenderer]] = default_error_renderers
  '''
  Error renderers keyed by bare media type.
  Override with a mapping that extends `default_error_renderers`, e.g. to render a styled HTML page.
  Every media type that `error_media_type` and `error_extension_media_types` name, and `text/plain`, must have an entry;
  this is checked when the subclass is defined.
  '''

  www_authenticate:ClassVar[str|None] = None
  '''
  The challenge for the WWW-Authenticate header of 401 responses, e.g. `Bearer realm="api"`; see `www_authenticate_for`.
  RFC 9110 requires a challenge on 401 responses, but cookie sessions have no standard scheme,
  and a `Basic` challenge makes browsers show their login dialog. The default None therefore omits the header.
  '''


  def __init_subclass__(cls, **kwargs:Any) -> None:
    super().__init_subclass__(**kwargs)
    cls._required_privileges = declared_access(cls.handle_request)
    if cls.handle_request is not WebApp.handle_request and cls._required_privileges is None:
      raise TypeError(f'{cls.__qualname__}.handle_request must declare access '
        'with the allow_public or requires_privileges decorator.')
    media_types = {cls.error_media_type, 'text/plain', *cls.error_extension_media_types.values()}
    for media_type in sorted(media_types):
      if media_type != bare_media_type(media_type):
        raise TypeError(f'{cls.__qualname__}: error media types must be bare, without parameters: {media_type!r}.')
      if media_type not in cls.error_renderers:
        raise TypeError(f'{cls.__qualname__}: error media type {media_type!r} has no entry in error_renderers.')


  def check_request(self, request:Request) -> None:
    '''
    Check deployment-wide request constraints before authentication; raise ResponseError to reject.
    Applies to every request, including static files and unknown paths. See `pithy.web.auth.SameOriginCheck`.
    '''


  def authenticate(self, request:Request) -> Privileges:
    '''
    Return effective privileges without reading the body: empty for anonymous, otherwise including `authenticated`.
    Nonempty results without `authenticated` are programming errors.
    Application user data can be stored in `request.ctx`; the server enforces destination requirements separately.

    Raise UnauthorizedError for invalid credentials that the client explicitly presented, such as a bad bearer token.
    This refuses every path, including public ones. Treat a stale or invalid session cookie as anonymous instead,
    so that public pages still work and restricted routes respond with 401.
    '''
    return frozenset()


  def www_authenticate_for(self, request:Request) -> str|None:
    '''
    Select the WWW-Authenticate challenge for a 401 response to a request; the default returns `www_authenticate`.
    The server adds it to any 401 response that lacks the header, including access denials and errors raised by
    `authenticate`, before `finish_response`. A challenge that the application sets itself is kept.
    Override to vary it by request, e.g. a Bearer challenge for API paths and none for pages.
    '''
    return self.www_authenticate


  def resolve_destination(self, request:Request) -> Destination:
    '''
    Select this application as the destination, using the declaration on `handle_request`.
    Override to implement routing. Resolution must not construct handlers or read the request body.
    '''
    if self._required_privileges is None: # Only possible when handle_request is not overridden.
      raise NotImplementedError(f'{type(self).__qualname__} does not implement handle_request.')
    return AppDestination(required_privileges=self._required_privileges, app=self)


  def handle_request(self, request:Request) -> Response:
    raise NotImplementedError


  def error_media_type_for(self, request:Request) -> str:
    '''
    Select the bare media type of the error response for a request; the default `error_response` renders with it.
    The default decides by the path extension: none gives `error_media_type`, a listed one gives its mapped type and
    any other gives plain text; see `error_media_type_for_path`.
    The extension is taken from the percent-decoded final segment, as routing sees it, so `/items%2Ejson` selects JSON;
    a path that cannot be decoded selects from its raw final segment.
    Override to consult other signals, e.g. the Accept header or a query parameter.
    '''
    try: segment = request.path_segments[-1]
    except ResponseError: segment = request.raw_path.rpartition('/')[2]
    return error_media_type_for_path(segment, default=self.error_media_type,
      extension_media_types=self.error_extension_media_types)


  def error_response(self, request:Request, error:ResponseError) -> Response|None:
    '''
    Build the response for a ResponseError raised during application dispatch or body handling,
    or return None to defer to the built-in plain text renderer.

    BodyTooLargeError and NotImplementedError from those steps are converted to ResponseError and pass through this hook.
    Unmatched paths and rejections before routing pass through it too, so the selection must not assume a handler.

    The default renders with the `error_renderers` entry for `error_media_type_for(request)`.
    Override `error_media_type_for` to change the selection, or this method to change how errors are built.
    An exception raised here is logged and treated as a deferral.
    '''
    return self.error_renderers[self.error_media_type_for(request)](request, error)


  def finish_response(self, request:Request, response:Response) -> Response:
    '''
    Adjust a response before it is sent; the default returns it unchanged.
    Override to apply policy headers to normal responses and responses produced by `error_response`.
    An exception raised here, including ResponseError, produces a bare 500 without calling either hook again.

    Body ownership: the server closes the body of the returned response after sending it.
    If the hook replaces the body, by returning a different response or by assigning `response.body`,
    the server closes the original body; the returned response may also reuse the original body.
    If the hook raises, the server closes the original body and any replacement attached to the input response.
    Overrides are responsible for closing any intermediate bodies they allocate and discard internally.
    '''
    return response



@dataclass(frozen=True)
class AppDestination(Destination):
  'An already constructed application selected to handle a request.'
  app:WebApp

  def get_handler(self, request:Request) -> WebApp:
    return self.app
