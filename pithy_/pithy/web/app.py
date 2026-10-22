# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from typing import Any, ClassVar

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
  1. `resolve_handler` routes to a handler (the default is `self`).
  2. The handler's `handle_expect_100_continue`, when applicable, accepts or rejects the request before its body is read.
  3. If not rejected, the handler's `prepare_for_request` prepares to handle the request, e.g. by reading the body.
  4. The handler's `handle_request` produces a response.

  A ResponseError raised during these steps is turned into a response by `error_response`,
  or by the built-in plain text renderer if that returns None or raises; a raise is logged.
  The default selects a renderer from `error_renderers` by the request path extension; see `error_media_type_for`.

  Normal responses, rejections from step 2 and responses produced by `error_response` pass through `finish_response`.
  Protocol rejections before Request construction bypass the application entirely.
  An unhandled exception elsewhere, including from `finish_response`, produces a bare 500 without consulting the app again.
  '''

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


  def __init_subclass__(cls, **kwargs:Any) -> None:
    super().__init_subclass__(**kwargs)
    media_types = {cls.error_media_type, 'text/plain', *cls.error_extension_media_types.values()}
    for media_type in sorted(media_types):
      if media_type != bare_media_type(media_type):
        raise TypeError(f'{cls.__qualname__}: error media types must be bare, without parameters: {media_type!r}.')
      if media_type not in cls.error_renderers:
        raise TypeError(f'{cls.__qualname__}: error media type {media_type!r} has no entry in error_renderers.')


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
    except ResponseError: segment = request.path.rpartition('/')[2]
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


  def resolve_handler(self, request:Request) -> RequestHandler:
    'Resolve the handler for a request. Override to implement routing.'
    return self


  def handle_request(self, request:Request) -> Response:
    raise NotImplementedError
