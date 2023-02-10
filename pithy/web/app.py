# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import mimetypes
from html import escape as html_escape
from http import HTTPStatus
from io import BufferedReader
from os import close
from typing import Any, cast, Iterable, TYPE_CHECKING
from urllib.parse import quote as url_quote, unquote as url_unquote

from pithy.path import path_ext, path_join

from ..fs import is_dir, path_exists, scan_dir
from ..http import format_header_date, http_status_response_strings
from . import compute_local_path, html_media_type, norm_url_path, Request, Response, ResponseError


if TYPE_CHECKING:
  from _typeshed.wsgi import StartResponse, WSGIApplication


class WebApp:

  def __init__(self, local_dir:str|None=None, prevent_client_caching:bool=False, map_bare_names_to_html=False):

    self.local_dir = local_dir
    self.prevent_client_caching = prevent_client_caching
    self.map_bare_names_to_html = map_bare_names_to_html

    if not mimetypes.inited: mimetypes.init()

    self.ext_media_types = { ext : mime_type for (ext, mime_type) in mimetypes.types_map.items() }
    self.ext_media_types.update({
      '': 'text/plain', # Default.
      '.bz2': 'application/x-bzip2',
      '.gz': 'application/gzip',
      '.sh': 'text/plain', # Show text instead of prompting a download.
      '.xz': 'application/x-xz',
      '.z': 'application/octet-stream',
      })


  def __call__(self, env:dict[str,Any], start:'StartResponse') -> Iterable[bytes]:
    '''
    The WSGI application interface.
    '''

    #from pprint import pprint
    #pprint(env)

    err = env['wsgi.errors']
    path = env['PATH_INFO']
    assert path.startswith('/')

    headers = {}
    for (name, value) in env.items():
      if name.startswith('HTTP_'):
        headers[name[5:].replace('_', '-').title()] = str(value)
      elif name in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
        headers[name.replace('_', '-').title()] = str(value)

    try:
      request = Request(
        method=env['REQUEST_METHOD'],
        scheme=env['wsgi.url_scheme'],
        host=env['SERVER_NAME'],
        port=env['SERVER_PORT'],
        path=path,
        query=env['QUERY_STRING'],
        body_file=env['wsgi.input'],
        err=err,
        is_multiprocess=env['wsgi.multiprocess'],
        is_multithread=env['wsgi.multithread'],
        headers=headers,
      )

      response = self.handle_request(request)

    except ResponseError as e:
      response = e.response(request.method)

    self.fill_response_headers(request, response, close_connection=False) # TODO: is this always correct?

    start(http_status_response_strings[response.status], response.headers_list())

    if isinstance(response.body, BufferedReader):
      return [response.body.read()] # TODO: consider iterating over large chunks.
    elif response.body:
      return [response.body]
    else:
      return ()


  def handle_expect_100_continue(self, request:Request) -> Response:
    '''
    Decide how to respond to an "Expect: 100-continue" header.

    We must respond with either a 100 Continue or a final response before waiting for the request body.
    The default is to always respond with a 100 Continue.
    You can behave differently (for example, reject unauthorized requests) by overriding this method.

    This method should be overridden to return the apppropriate Response or raise an ResponseError.
    '''
    return Response(status=HTTPStatus.CONTINUE)


  def handle_request(self, request:Request) -> Response:
    '''
    Override point for subclasses to handle a request.
    The base implementation returns a 501 Not Implemented response.
    This method should be overridden to return the apppropriate Response or raise an ResponseError.
    '''
    raise ResponseError(status=HTTPStatus.NOT_IMPLEMENTED)


  def fill_response_headers(self, request:Request, response:Response, close_connection:bool) -> None:
    '''
    '''
    if self.prevent_client_caching and request.method in ('HEAD', 'GET', 'POST'):
      response.headers.setdefault('Cache-Control', 'no-cache, no-store, must-revalidate')
      response.headers.setdefault('Pragma', 'no-cache')
      response.headers.setdefault('Expires', '0')

    status = response.status
    headers = response.headers
    if status != HTTPStatus.CONTINUE and status != HTTPStatus.SWITCHING_PROTOCOLS:
      # According to https://datatracker.ietf.org/doc/html/rfc2616#section-14.18:
      # 100 and 101 may optionally include date. Otherwise it is required.
      headers['Date'] = format_header_date()

    if close_connection:
      headers['Connection'] = 'close'



  def serve_content_from_local_fs(self, request:Request, *, raw_path='') -> Response:
    '''
    Return the content of a local file or a directory listing.
    This method should be called by `handle_request` implementations to serve content from the local file system.
    '''
    if not self.local_dir: raise ResponseError(status=HTTPStatus.INTERNAL_SERVER_ERROR)

    if not raw_path: raw_path = request.path
    norm_path = norm_url_path(raw_path)
    local_path = compute_local_path(local_dir=self.local_dir, norm_path=norm_path, map_bare_names_to_html=self.map_bare_names_to_html)

    if not local_path: raise ValueError(local_path) # Should never end up with an empty string.

    if is_dir(local_path, follow=True):
      if not norm_path.endswith('/'): # Redirect browser to path with slash (same behavior as Apache).
        assert norm_path.startswith('/')
        query = '?' + request.query if request.query else ''
        new_url = f'{norm_path}/{query}'
        raise ResponseError(status=HTTPStatus.MOVED_PERMANENTLY, headers={'Location':new_url})
      index_path = path_join(local_path, 'index.html')
      if path_exists(index_path, follow=False):
        local_path = index_path
      else:
        return self.list_directory(request=request, local_path=local_path)

    try: file = open(local_path, 'rb')
    except (FileNotFoundError, PermissionError): raise ResponseError(status=HTTPStatus.NOT_FOUND)

    assert isinstance(file, BufferedReader)
    return self.transform_file_from_local_fs(request=request, norm_path=norm_path, local_path=local_path, file=file)


  def transform_file_from_local_fs(self, request:Request, norm_path:str, local_path:str, file:BufferedReader) -> Response:
    '''
    Override point to transform the content of a local file. The base implementation returns the file handle unaltered.
    '''
    return Response(body=file, media_type=self.guess_media_type(local_path))


  def list_directory(self, request:Request, local_path:str) -> Response:
    '''
    Produce a directory listing html page (absent index.html).
    '''
    try: listing = scan_dir(local_path)
    except OSError as exc:
      print('Failed to list directory:', local_path, exc, file=request.err)
      raise ResponseError(status=HTTPStatus.NOT_FOUND) from exc
    listing.sort(key=lambda e: cast(str, e.name.lower()))

    display_path = url_unquote(request.path, errors='replace')
    title = html_escape(display_path, quote=False)

    r = []
    r.append('<!DOCTYPE html>\n<html>')
    r.append(f'<head>\n<meta charset="utf-8" />\n<title>{title}</title>\n</head>')
    r.append(f'<body>\n<h1>{title}</h1>')
    r.append('<hr>\n<ul>')
    for entry in listing:
      n = entry.name + ('/' if entry.is_dir(follow_symlinks=True) else '')
      link_href = url_quote(n, errors='replace')
      link_text = html_escape(n, quote=False)
      r.append(f'<li><a href="{link_href}">{link_text}</a></li>')
    r.append('</ul>\n<hr>\n</body>\n</html>\n')
    body = '\n'.join(r).encode(errors='replace')
    return Response(body=body, media_type=html_media_type)


  def guess_media_type(self, path:str) -> str:
    'Guess the mime type for a file path.'
    ext = path_ext(path).lower()
    try: return self.ext_media_types[ext]
    except KeyError: return self.ext_media_types['']
