# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import mimetypes
from collections.abc import Mapping
from email.utils import parsedate_to_datetime
from html import escape as html_escape
from http import HTTPStatus
from io import BufferedReader
from os import fstat as os_fstat, stat_result
from typing import cast
from urllib.parse import quote as url_quote, unquote as url_unquote

from ..fs import is_dir, path_exists, scan_dir
from ..http import format_header_date
from ..logs import logE
from ..path import norm_path, path_ext, path_join
from .app import WebApp
from .errors import ResponseError
from .handler import RoutableHandler
from .request import Request
from .response import html_media_type, Response
from .util import norm_url_path


def _build_ext_media_types() -> dict[str,str]:
  'Build the extension-to-media-type map once, at import time rather than per request.'
  if not mimetypes.inited: mimetypes.init()
  types = { ext : mime_type for (ext, mime_type) in mimetypes.types_map.items() }
  types.update({
    '': 'text/plain', # Default.
    '.bz2': 'application/x-bzip2',
    '.gz': 'application/gzip',
    '.sh': 'text/plain', # Show text instead of prompting a download.
    '.xz': 'application/x-xz',
    '.z': 'application/octet-stream',
    })
  return types


ext_media_types = _build_ext_media_types()


def file_etag(stat:stat_result) -> str:
  'A strong entity tag derived from the file size and modification time.'
  return f'"{stat.st_size:x}-{stat.st_mtime_ns:x}"'


def is_request_modified(request:Request, *, etag:str, mtime:float) -> bool:
  '''
  Return True if the request's conditional headers do not show the client's cached copy to be current.
  If-None-Match takes precedence over If-Modified-Since (RFC 9110).
  '''
  if_none_match = request.headers.get('if-none-match')
  if if_none_match is not None:
    return not _does_header_match_etag(if_none_match, etag)
  if_modified_since = request.headers.get('if-modified-since')
  if if_modified_since is not None:
    since = _parse_http_date(if_modified_since)
    if since is not None:
      return int(mtime) > since
  return True


def _does_header_match_etag(header:str, etag:str) -> bool:
  'Compare an If-None-Match header value (a comma list, or `*`) against `etag` using weak comparison.'
  candidates = [c.strip() for c in header.split(',')]
  if '*' in candidates: return True
  target = etag.removeprefix('W/')
  return any(c.removeprefix('W/') == target for c in candidates)


def _parse_http_date(text:str) -> int|None:
  'Parse an HTTP date header into an integer unix timestamp, or None if it cannot be parsed.'
  try: dt = parsedate_to_datetime(text)
  except (TypeError, ValueError): return None
  return int(dt.timestamp())


class _FilesServing:
  '''
  Shared local file serving logic, mixed into both FilesApp (whole application) and FilesHandler (mounted route target).
  Configuration is read from `self`: `local_dir`, `prevent_client_caching`, `map_bare_names_to_html`, and `ext_media_types`.
  '''

  local_dir:str
  prevent_client_caching:bool
  map_bare_names_to_html:bool

  # The shared default map; subclasses override with their own mapping to add or alter media types.
  ext_media_types:Mapping[str,str] = ext_media_types


  def serve(self, request:Request, raw_path:str='') -> Response:
    'Serve content from the local file system, applying no-cache headers when configured.'
    response = self.serve_content_from_local_fs(request, raw_path=raw_path)
    if self.prevent_client_caching or request.prevent_client_caching: response.set_no_cache_headers()
    return response


  def serve_content_from_local_fs(self, request:Request, *, raw_path:str='') -> Response:
    '''
    Return the content of a local file or a directory listing.
    `raw_path` selects the url path to map into `local_dir`; it defaults to the full request path.
    Mounted handlers pass the sub-path below their prefix so that only that portion maps into `local_dir`.
    '''

    if not raw_path: raw_path = request.path
    norm_path = norm_url_path(raw_path)
    local_path = compute_local_path(local_dir=self.local_dir, norm_path=norm_path,
      map_bare_names_to_html=self.map_bare_names_to_html)

    if not local_path: raise ValueError(local_path) # Should never end up with an empty string.

    if is_dir(local_path, follow=True):
      if not norm_path.endswith('/'): # Redirect browser to path with slash (same behavior as Apache).
        url_path = norm_url_path(request.path) # The full request path, so mounted handlers redirect within their prefix.
        query = '?' + request.query_str if request.query_str else ''
        new_url = f'{url_path}/{query}'
        raise ResponseError(status=HTTPStatus.MOVED_PERMANENTLY, headers={'location':new_url})
      index_path = path_join(local_path, 'index.html')
      if path_exists(index_path, follow=False):
        local_path = index_path
      else:
        return self.list_directory(request=request, local_path=local_path)

    try: file = open(local_path, 'rb')
    except (FileNotFoundError, PermissionError): raise ResponseError(status=HTTPStatus.NOT_FOUND)

    assert isinstance(file, BufferedReader)

    if self.prevent_client_caching or request.prevent_client_caching:
      # No-store development mode: never emit validators or 304s, so the client always refetches.
      return self.transform_file_from_local_fs(request=request, norm_path=norm_path, local_path=local_path, file=file)

    stat = os_fstat(file.fileno())
    etag = file_etag(stat)
    if not is_request_modified(request, etag=etag, mtime=stat.st_mtime):
      file.close()
      return Response(status=HTTPStatus.NOT_MODIFIED, headers={'etag':etag}, last_modified=stat.st_mtime)

    response = self.transform_file_from_local_fs(request=request, norm_path=norm_path, local_path=local_path, file=file)
    response.headers.setdefault('etag', etag)
    response.headers.setdefault('last-modified', format_header_date(stat.st_mtime))
    return response


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
      logE('Failed to list directory.', local_path=local_path, exc=exc)
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
    media_types = self.ext_media_types
    ext = path_ext(path).lower()
    try: return media_types[ext]
    except KeyError: return media_types['']



class FilesApp(_FilesServing, WebApp):
  'Serve a local directory as an entire web application, e.g. `pithytools serve_dir`.'


  def __init__(self, local_dir:str, prevent_client_caching:bool=False, map_bare_names_to_html:bool=False) -> None:
    self.local_dir = norm_path(local_dir)
    self.prevent_client_caching = prevent_client_caching
    self.map_bare_names_to_html = map_bare_names_to_html


  def handle_request(self, request:Request) -> Response:
    request.allow_methods('GET', 'HEAD')
    return self.serve(request)



class FilesHandler(_FilesServing, RoutableHandler):
  '''
  Serve a local directory mounted under a router prefix.
  Mount with a `{subpath:path}` tail route whose handler subclass sets `local_dir`, e.g.:
    class MyStatic(FilesHandler): local_dir = '/path/to/assets'
    routes = { '/static/{subpath:path}': MyStatic }
  The captured `subpath` is mapped into `local_dir`; the full request path is used for directory redirects.
  '''

  local_dir = '' # Set by subclasses.
  prevent_client_caching = False
  map_bare_names_to_html = False
  _methods = frozenset({'GET', 'HEAD'})


  def __init__(self, request:Request, path_params:Mapping[str,object]) -> None:
    self.subpath = str(path_params['subpath'])


  def handle_request(self, request:Request) -> Response:
    return self.serve(request, raw_path='/' + self.subpath)


def compute_local_path(*, local_dir:str, norm_path:str, map_bare_names_to_html:bool) -> str:
  '''
  Compute local_path from a normalized url path (result of `norm_url_path`).
  If `map_bare_names_to_html` is True, then a path without a file extension has '.html' appended.
  '''
  assert local_dir and not local_dir.endswith('/'), local_dir

  if not norm_path.startswith('/'): raise ValueError(norm_path)
  if '..' in norm_path: raise ResponseError(HTTPStatus.FORBIDDEN)

  if map_bare_names_to_html and not norm_path.endswith('/') and not path_ext(norm_path):
    norm_path += '.html'

  return local_dir + norm_path
