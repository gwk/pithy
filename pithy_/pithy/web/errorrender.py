# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Render ResponseError exceptions as complete responses, with one renderer per media type.

A renderer is a plain function from `(request, error)` to a Response.
Renderers are keyed by bare media type rather than attached to Response subclasses,
so that an application changes an error format by supplying a function instead of subclassing Response.
`WebApp.error_renderers` holds the mapping; the default `WebApp.error_response` selects an entry from the request path
extension via `error_media_type_for_path`. Everything defaults to the values defined here, so that an application is well
behaved without customization.

Every renderer must honor `pithy.http.may_send_body`: HEAD requests and bodiless statuses get no body and no Content-Type.
`build_error_response` applies that rule for renderers that produce a string body.
'''

from collections.abc import Callable, Mapping
from html import escape as html_escape

from ..http import may_send_body
from ..json import render_json
from .errors import ResponseError
from .request import Request
from .response import Response


_context_keywords_ = ['content type', 'error body', 'error page', 'html', 'json', 'media type', 'plain text',
  'problem details', 'rfc 9457']


type ErrorRenderer = Callable[[Request,ResponseError],Response]
'''
Build the complete response for a ResponseError raised while handling `request`.
The status, reason and headers of the error must be preserved; `build_error_response` does this.
'''


default_error_media_type = 'text/plain'
'''
The media type of error responses for an application that declares none.
Plain text displays readably in browsers, terminals and API clients alike, and needs no escaping.
'''


problem_json_media_type = 'application/problem+json'
'The media type of RFC 9457 Problem Details bodies.'


default_error_extension_media_types:frozendict[str,str] = frozendict({
  'htm': 'text/html',
  'html': 'text/html',
  'htmx': 'text/html',
  'json': 'application/json',
})
'''
Lowercase path extensions mapped to the bare media type of their error responses.
Only HTML, htmx and JSON consumers benefit from an error body in their own format;
every other extension denotes a file, and `error_media_type_for_path` gives those plain text.
'''


def error_media_type_for_path(path:str, *, default:str,
 extension_media_types:Mapping[str,str]=default_error_extension_media_types) -> str:
  '''
  Select the error media type for a request path from the extension of its last segment.
  `path` must already be percent-decoded, or be the decoded final segment itself; `WebApp.error_media_type_for` does this.
  A path without an extension gets `default`; a known extension gets its mapped type; any other extension gets plain text,
  because a CSS, image or data response that carries an HTML or JSON error body serves no consumer, and an error typed as
  the file's own media type risks being consumed as content.
  '''
  ext = path_extension(path)
  if not ext: return default
  return extension_media_types.get(ext, 'text/plain')


def path_extension(path:str) -> str:
  '''
  The lowercase extension of the last path segment without its dot, or empty.
  A leading dot does not start an extension, and a suffix starting with a digit is not one,
  so that version-like segments such as `1.2` or `1.0rc1` are treated as extensionless.
  '''
  segment = path.rpartition('/')[2]
  stem, _, ext = segment.rpartition('.')
  if not stem or not ext or ext[0].isdigit(): return ''
  return ext.lower()


def render_error_text(request:Request, error:ResponseError) -> Response:
  'Render an error as a plain text line of the form `404: Not Found.`'
  body = f'{error.status.value}: {error_reason(error)}\n'
  return build_error_response(request, error, body=body, media_type='text/plain')


def render_error_html(request:Request, error:ResponseError) -> Response:
  'Render an error as a minimal HTML page, or as a bare paragraph for an htmx request, as indicated by the HX-Request header.'
  reason = html_escape(error_reason(error), quote=False) # Escape the reason to prevent cross-site scripting attacks.
  code = error.status.value
  if request.headers.get('hx-request') == 'true':
    body = f'<p>{code}: {reason}</p>\n'
  else:
    body = error_html_format.format(code=code, phrase=error.status.phrase, reason=reason)
  return build_error_response(request, error, body=body, media_type='text/html')


def render_error_problem_json(request:Request, error:ResponseError) -> Response:
  '''
  Render an error as an RFC 9457 Problem Details object.
  `type` is omitted, which the RFC defines as `about:blank`, so `title` is the status phrase.
  `detail` carries the reason verbatim when one was given.
  '''
  problem:dict[str,object] = {'status': error.status.value, 'title': error.status.phrase}
  if error.reason: problem['detail'] = error.reason
  body = render_json(problem, indent=None) + '\n'
  return build_error_response(request, error, body=body, media_type=problem_json_media_type)


default_error_renderers:frozendict[str,ErrorRenderer] = frozendict({
  'text/plain': render_error_text,
  'text/html': render_error_html,
  'application/json': render_error_problem_json,
  problem_json_media_type: render_error_problem_json,
})
'''
Renderers for the common media types, keyed by bare media type.
JSON endpoints get Problem Details bodies, whose Content-Type is `application/problem+json` as the RFC intends.
Applications extend the mapping rather than mutate it: `{**default_error_renderers, 'text/html': render_my_page}`.
'''


def build_error_response(request:Request, error:ResponseError, *, body:str, media_type:str) -> Response:
  '''
  Build the Response for an error from a rendered string body, preserving the error's status, reason and headers.
  The body and Content-Type are omitted when `may_send_body` forbids a body, e.g. for HEAD requests.
  '''
  if not may_send_body(request.method, error.status):
    return Response(error.status, reason=error.reason, headers=error.headers)
  return Response(error.status, reason=error.reason, headers=error.headers, body=body, media_type=media_type)


def error_reason(error:ResponseError) -> str:
  'The reason for display: the error reason or else the status phrase, ending with terminal punctuation.'
  reason = error.reason or error.status.phrase
  if not reason.endswith(('.', '!', '?')): reason += '.'
  return reason


def bare_media_type(media_type:str) -> str:
  'Strip parameters such as charset and normalize case, producing the key form used by renderer mappings.'
  return media_type.partition(';')[0].strip().lower()


error_html_format = '''\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{code} {phrase}</title>
</head>
<body>
  <p>{code}: {reason}</p>
</body>
</html>
'''
