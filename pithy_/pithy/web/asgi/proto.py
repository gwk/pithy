# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
ASGI specification types.
* https://asgi.readthedocs.io/en/latest/specs/main.html
* https://asgi.readthedocs.io/en/latest/specs/www.html
* https://asgi.readthedocs.io/en/latest/specs/lifespan.html
'''

from typing import Any, Iterable, Literal, NotRequired, Protocol, TypedDict


type AsgiEventValAtom = None | bool | bytes | float | int | str
type AsgiEventVal = AsgiEventValAtom | tuple[AsgiEventValAtom,...] | list[AsgiEventVal] | dict[str,AsgiEventVal]

type AsgiEvent = dict[str,AsgiEventVal]

type HttpHeader = tuple[bytes, bytes]
'A single HTTP header as (lowercased-name, value), both raw byte strings.'

type HttpVersion = Literal['1.0', '1.1', '2']
type HttpScheme = Literal['http', 'https']


class AsgiVersionsDict(TypedDict):
  '''
  The scope['asgi'] sub-dictionary present in every ASGI scope.
  '''
  version: str  # e.g. '3.0'.
  spec_version: NotRequired[str]  # e.g. '2.4'; if missing assume '2.0' for HTTP.


# HTTP.


class HttpScope(TypedDict):
  '''
  Connection scope for an HTTP request.

  Passed as the first argument to an ASGI application when type == 'http'.
  The scope lives for the duration of a single HTTP request.

  https://asgi.readthedocs.io/en/latest/specs/www.html#http-connection-scope
  '''
  type: Literal['http']
  asgi: AsgiVersionsDict
  http_version: HttpVersion
  method: str # Uppercased HTTP method, e.g. 'GET'.
  scheme: NotRequired[HttpScheme] # Default 'http' if absent.
  path: str # Decoded URI path (no query string).
  raw_path: NotRequired[bytes] # Original path bytes; some servers cannot provide this.
  query_string: bytes # Raw query string after '?', percent-encoded.
  root_path: str # Equivalent to WSGI SCRIPT_NAME; may be ''.
  headers: Iterable[HttpHeader] # Lowercased header names, order preserved.
  client: NotRequired[tuple[str, int] | None] # (host, port) of the connected client.
  server: NotRequired[tuple[str, int] | None] # (host, port) of the listening server.
  state: NotRequired[dict[str, Any]] # Shared namespace from lifespan scope.
  extensions: NotRequired[dict[str, dict[str, Any]]]


class HttpRequestEvent(TypedDict):
  '''
  Request (receive).

  Sent to the application to indicate an incoming request body chunk.

  https://asgi.readthedocs.io/en/latest/specs/www.html#request-receive-event
  '''
  type: Literal['http.request']
  body: NotRequired[bytes] # Defaults to b'' if missing.
  more_body: NotRequired[bool] # Defaults to False if missing.


class HttpDisconnectEvent(TypedDict):
  '''
  Disconnect (receive).

  Sent to the application when the HTTP connection is closed (client disconnect or completion).

  https://asgi.readthedocs.io/en/latest/specs/www.html#disconnect-receive-event
  '''
  type: Literal['http.disconnect']


type HttpReceiveEvent = HttpRequestEvent | HttpDisconnectEvent


class HttpResponseStartEvent(TypedDict):
  '''
  Response Start (send).

  Starts the HTTP response; must be sent before any body chunks.

  https://asgi.readthedocs.io/en/latest/specs/www.html#response-start-send-event
  '''
  type: Literal['http.response.start']
  status: int # HTTP status code, e.g. 200.
  headers: NotRequired[list[HttpHeader]] # Defaults to [] if missing.
  trailers: NotRequired[bool] # Extension: http.response.trailers.


class HttpResponseBodyEvent(TypedDict):
  '''
  Response Body (send).

  Sends a chunk of the HTTP response body.

  https://asgi.readthedocs.io/en/latest/specs/www.html#response-body-send-event
  '''
  type: Literal['http.response.body']
  body: NotRequired[bytes] # Defaults to b'' if missing.
  more_body: NotRequired[bool] # Defaults to False if missing.


class HttpResponseTrailersEvent(TypedDict):
  '''
  Response Trailers (send); http.response.trailers extension.

  Sends trailing headers after the final body chunk (more_body=False).
  Only valid when scope['extensions']['http.response.trailers'] is present.
  The `trailers` key on HttpResponseStartEvent must be set to True to use.

  https://asgi.readthedocs.io/en/latest/extensions.html#http-trailers
  '''
  type: Literal['http.response.trailers']
  headers: NotRequired[list[HttpHeader]]
  more_trailers: NotRequired[bool]  # Defaults to False if missing.


class HttpResponsePathsendEvent(TypedDict):
  '''
  Response Path Send (send); http.response.pathsend extension.

  Delegates response body to the server via a local file path (e.g. X-Sendfile).

  https://asgi.readthedocs.io/en/latest/extensions.html#response-path-send
  '''
  type: Literal['http.response.pathsend']
  path: str


class HttpServerPushEvent(TypedDict):
  '''
  Server Push (send); http.response.push extension.

  Initiates an HTTP/2 server push for the given path and headers.

  https://asgi.readthedocs.io/en/latest/extensions.html#server-push
  '''
  type: Literal['http.response.push']
  path: str
  headers: Iterable[HttpHeader]


type HttpSendEvent = HttpResponseStartEvent | HttpResponseBodyEvent

type HttpSendEventExt = (
  HttpResponseStartEvent | HttpResponseBodyEvent | HttpResponseTrailersEvent | HttpResponsePathsendEvent | HttpServerPushEvent)


# WebSockets.


class WebSocketScope(TypedDict):
  '''
  Connection scope for a WebSocket request.

  Passed as the first argument to an ASGI application when type == 'websocket'.
  The scope lives for the duration of a single WebSocket connection.

  https://asgi.readthedocs.io/en/latest/specs/www.html#websocket-connection-scope
  '''
  type: Literal['websocket']
  asgi: AsgiVersionsDict
  http_version: HttpVersion
  scheme: NotRequired[str]
  path: str
  raw_path: NotRequired[bytes]
  query_string: bytes
  root_path: str
  headers: Iterable[HttpHeader]
  client: NotRequired[tuple[str, int] | None]
  server: NotRequired[tuple[str, int] | None]
  subprotocols: Iterable[str]
  state: NotRequired[dict[str, Any]]
  extensions: NotRequired[dict[str, dict[str, Any]]]


class WebSocketConnectEvent(TypedDict):
  '''
  Connect (receive).

  Sent to the application when the client initiates a WebSocket handshake.

  https://asgi.readthedocs.io/en/latest/specs/www.html#connect-receive-event
  '''
  type: Literal['websocket.connect']


class WebSocketReceiveEvent(TypedDict):
  '''
  Receive (receive).

  Sent to the application when a data frame is received from the client.

  https://asgi.readthedocs.io/en/latest/specs/www.html#receive-receive-event-2
  '''
  type: Literal['websocket.receive']
  bytes: NotRequired[bytes | None]
  text: NotRequired[str | None]


class WebSocketDisconnectEvent(TypedDict):
  '''
  Disconnect (receive).

  Sent to the application when the WebSocket connection is closed.

  https://asgi.readthedocs.io/en/latest/specs/www.html#disconnect-receive-event-2
  '''
  type: Literal['websocket.disconnect']
  code: int
  reason: NotRequired[str | None]


type WebSocketReceiveEvents = WebSocketConnectEvent | WebSocketReceiveEvent | WebSocketDisconnectEvent


# WebSocket send events.


class WebSocketAcceptEvent(TypedDict):
  '''
  Accept (send).

  Sent by the application to accept an incoming WebSocket connection.

  https://asgi.readthedocs.io/en/latest/specs/www.html#accept-send-event
  '''
  type: Literal['websocket.accept']
  subprotocol: NotRequired[str | None]
  headers: NotRequired[Iterable[HttpHeader]]


class WebSocketSendEvent(TypedDict):
  '''
  Send (send).

  Sent by the application to send a data frame to the client.

  https://asgi.readthedocs.io/en/latest/specs/www.html#send-send-event-2
  '''
  type: Literal['websocket.send']
  bytes: NotRequired[bytes | None]
  text: NotRequired[str | None]


class WebSocketResponseStartEvent(TypedDict):
  '''
  HTTP Response Start (send); websocket denial extension.

  Starts an HTTP response to deny a WebSocket connection.

  https://asgi.readthedocs.io/en/latest/extensions.html#websocket-denial-response
  '''
  type: Literal['websocket.http.response.start']
  status: int
  headers: Iterable[HttpHeader]


class WebSocketResponseBodyEvent(TypedDict):
  '''
  HTTP Response Body (send); websocket denial extension.

  Sends a chunk of the denial HTTP response body.

  https://asgi.readthedocs.io/en/latest/extensions.html#websocket-denial-response
  '''
  type: Literal['websocket.http.response.body']
  body: bytes
  more_body: NotRequired[bool]


class WebSocketCloseEvent(TypedDict):
  '''
  Close (send).

  Sent by the application to close the WebSocket connection.

  https://asgi.readthedocs.io/en/latest/specs/www.html#close-send-event
  '''
  type: Literal['websocket.close']
  code: NotRequired[int] # Defaults to 1000 if missing.
  reason: NotRequired[str | None]


type WebSocketSendEvents = (
  WebSocketAcceptEvent | WebSocketSendEvent | WebSocketResponseStartEvent | WebSocketResponseBodyEvent | WebSocketCloseEvent)


# Lifespan.


class LifespanScope(TypedDict):
  '''
  Lifespan scope for application startup and shutdown.

  Passed as the first argument to an ASGI application when type == 'lifespan'.
  The scope lives for the entire lifetime of the application.

  https://asgi.readthedocs.io/en/latest/specs/lifespan.html#lifespan-scope
  '''
  type: Literal['lifespan']
  asgi: AsgiVersionsDict
  state: NotRequired[dict[str, Any]] # Shared namespace for all scopes.


class LifespanStartupEvent(TypedDict):
  '''
  Startup (receive).

  Sent to the application when the server is ready for it to start up.

  https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-receive-event
  '''
  type: Literal['lifespan.startup']


class LifespanShutdownEvent(TypedDict):
  '''
  Shutdown (receive).

  Sent to the application when the server wants it to shut down.

  https://asgi.readthedocs.io/en/latest/specs/lifespan.html#shutdown-receive-event
  '''
  type: Literal['lifespan.shutdown']


type LifespanReceiveEvent = LifespanStartupEvent | LifespanShutdownEvent


class LifespanStartupCompleteEvent(TypedDict):
  '''
  Startup Complete (send).

  Sent by the application when it has finished starting up.

  https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-complete-send-event
  '''
  type: Literal['lifespan.startup.complete']


class LifespanStartupFailedEvent(TypedDict):
  '''
  Startup Failed (send).

  Sent by the application when startup has failed.

  https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-failed-send-event
  '''
  type: Literal['lifespan.startup.failed']
  message: NotRequired[str]


class LifespanShutdownCompleteEvent(TypedDict):
  '''
  Shutdown Complete (send).

  Sent by the application when it has finished shutting down.

  https://asgi.readthedocs.io/en/latest/specs/lifespan.html#shutdown-complete-send-event
  '''
  type: Literal['lifespan.shutdown.complete']


class LifespanShutdownFailedEvent(TypedDict):
  '''
  Shutdown Failed (send).

  Sent by the application when shutdown has failed.

  https://asgi.readthedocs.io/en/latest/specs/lifespan.html#shutdown-failed-send-event
  '''
  type: Literal['lifespan.shutdown.failed']
  message: NotRequired[str]


type LifespanSendEvent = (
  LifespanStartupCompleteEvent | LifespanStartupFailedEvent | LifespanShutdownCompleteEvent | LifespanShutdownFailedEvent)


# Aggregate scope and event unions.

type AsgiConnScope = HttpScope | WebSocketScope
type AsgiScope = HttpScope | WebSocketScope | LifespanScope

type AsgiReceiveEvent = HttpReceiveEvent | WebSocketReceiveEvents | LifespanReceiveEvent

type AsgiSendEvent = HttpSendEventExt | WebSocketSendEvents | LifespanSendEvent


# ASGI application protocols.


class AsgiReceiveSrc(Protocol):
  async def __call__(self) -> AsgiReceiveEvent: ...


class AsgiSendDst(Protocol):
  async def __call__(self, message:AsgiSendEvent) -> None: ...


class AsgiApp(Protocol):
  async def __call__(self, scope:AsgiScope, receive:AsgiReceiveSrc, send:AsgiSendDst) -> None: ...
