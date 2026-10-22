# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from typing import Any, ClassVar

from .errorrender import bare_media_type, default_error_media_type, default_error_renderers, ErrorRenderer
from .errors import ResponseError
from .handler import RequestHandler
from .request import Request
from .response import Response


_context_keywords_ = ['application', 'dispatch', 'http', 'request lifecycle', 'routing', 'web framework']


class WebApp(RequestHandler):
  '''
  The application object that the server consults for every request.

  The server drives a fixed lifecycle, in this order:
  1. `resolve_handler` routes to a handler (the default is `self`).
  2. The handler's `handle_expect_100_continue`, when applicable, accepts or rejects the request before its body is read.
  3. If not rejected, the handler's `prepare_for_request` prepares to handle the request, e.g. by reading the body.
  4. The handler's `handle_request` produces a response.

  A ResponseError raised during these steps is turned into a response by `error_response`;
  the default renders it with the `error_renderers` entry for `error_media_type`.
  Normal responses, rejections from step 2 and responses produced by `error_response` pass through `finish_response`.
  Protocol rejections before Request construction bypass the application entirely.
  An unhandled exception, including an exception from either response hook, produces a bare 500 without consulting the app
  again.
  '''

  error_media_type:ClassVar[str] = default_error_media_type
  'The bare media type of error responses. It must be a key of `error_renderers`; this is checked when the subclass is defined.'

  error_renderers:ClassVar[Mapping[str,ErrorRenderer]] = default_error_renderers
  '''
  Error renderers keyed by bare media type.
  Override with a mapping that extends `default_error_renderers`, e.g. to render a styled HTML page.
  '''


  def __init_subclass__(cls, **kwargs:Any) -> None:
    super().__init_subclass__(**kwargs)
    media_type = cls.error_media_type
    if media_type != bare_media_type(media_type):
      raise TypeError(f'{cls.__qualname__}.error_media_type must be a bare media type without parameters: {media_type!r}.')
    if media_type not in cls.error_renderers:
      raise TypeError(f'{cls.__qualname__}.error_media_type {media_type!r} has no entry in error_renderers.')


  def error_response(self, request:Request, error:ResponseError) -> Response:
    '''
    Build the response for a ResponseError raised during application dispatch or body handling.
    BodyTooLargeError and NotImplementedError from those steps are converted to ResponseError and pass through this hook.
    The default renders with the `error_renderers` entry for `error_media_type`.
    Override to choose the renderer per request, e.g. from the Accept header or the resolved handler.
    An exception raised here produces a bare 500.
    '''
    return self.error_renderers[self.error_media_type](request, error)


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


  def resolve_handler(self, request:Request) -> RequestHandler:
    'Resolve the handler for a request. Override to implement routing.'
    return self


  def handle_request(self, request:Request) -> Response:
    raise NotImplementedError
