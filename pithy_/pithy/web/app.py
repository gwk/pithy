# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from typing import Any, ClassVar

from .errorrender import bare_media_type, default_error_media_type, default_error_renderers, ErrorRenderer
from .handler import RequestHandler
from .request import Request
from .response import Response


_context_keywords_ = ['application', 'dispatch', 'http', 'request lifecycle', 'routing', 'web framework']


class WebApp(RequestHandler):
  '''
  The application object that the server consults for every request.
  A ResponseError raised while handling a request is rendered by the `error_renderers` entry for `error_media_type`.
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


  def error_renderer(self) -> ErrorRenderer:
    'The renderer selected by `error_media_type`.'
    return self.error_renderers[self.error_media_type]


  def resolve_handler(self, request:Request) -> RequestHandler:
    'Resolve the handler for a request. Override to implement routing.'
    return self


  def handle_request(self, request:Request) -> Response:
    raise NotImplementedError
