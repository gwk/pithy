# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import mimetypes
from collections.abc import Mapping
from email.utils import parsedate_to_datetime
from html import escape as html_escape
from http import HTTPStatus
from io import BufferedReader
from os import fstat as os_fstat, stat_result
from typing import cast
from urllib.parse import quote as url_quote

from ..fs import is_dir, path_exists, scan_dir
from ..http import format_header_date
from ..logs import logE
from ..path import Path, path_ext
from .app import WebApp
from .errors import ResponseError
from .handler import RoutableHandler
from .request import Request
from .response import close_response_body, html_media_type, Response


_context_keywords_ = ['conditional requests', 'directory listing', 'etag', 'http.server.SimpleHTTPRequestHandler', 'mime types',
  'mimetypes.guess_type', 'mounted assets', 'static serving']


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


  def handle_file_request(self, request:Request, path:Path, *, as_dir:bool) -> Response:
    'Serve a decoded path within the mount and apply the configured cache policy.'
    response = self.serve_content_from_local_fs(request, path=path, as_dir=as_dir)
    try:
      if self.prevent_client_caching or request.prevent_client_caching: response.set_no_cache_headers()
      return response
    except:
      close_response_body(response.body)
      raise


  def serve_content_from_local_fs(self, request:Request, *, path:Path, as_dir:bool) -> Response:
    '''
    Serve a file or directory under `local_dir`.

    `path` is decoded and absolute within the mount: `/a.txt` selects `local_dir/a.txt`.
    `as_dir` records whether the request ended with a slash. It suppresses `.html` mapping and directory redirects.
    Collapse parent components before joining to `local_dir`, so they cannot climb above the mount root.
    '''
    norm_path = path.collapse_dotdot()
    local_path = compute_local_path(local_dir=self.local_dir, norm_path=norm_path, as_dir=as_dir,
      map_bare_names_to_html=self.map_bare_names_to_html)

    if is_dir(local_path, follow=True):
      if not as_dir: # Redirect browser to path with slash (same behavior as Apache).
        # The location is built from the full raw request path, so mounted handlers redirect within their prefix
        # and the redirect target stays percent-encoded.
        query = '?' + request.query_str if request.query_str else ''
        new_url = Path(request.path).collapse_dotdot().str_with_slash() + query
        raise ResponseError(status=HTTPStatus.MOVED_PERMANENTLY, headers={'location':new_url})
      index_path = local_path / 'index.html'
      if path_exists(index_path, follow=False):
        local_path = index_path
      else:
        return self.list_directory(request=request, local_path=local_path)
    elif as_dir:
      raise ResponseError(status=HTTPStatus.NOT_FOUND)

    try: file = open(local_path, 'rb')
    except (FileNotFoundError, PermissionError): raise ResponseError(status=HTTPStatus.NOT_FOUND)

    transferred = False
    response:Response|None = None
    try:
      assert isinstance(file, BufferedReader)
      if self.prevent_client_caching or request.prevent_client_caching:
        # No-store development mode: never emit validators or 304s, so the client always refetches.
        response = self.transform_file_from_local_fs(request=request, norm_path=norm_path, local_path=local_path, file=file)
      else:
        stat = os_fstat(file.fileno())
        etag = file_etag(stat)
        if not is_request_modified(request, etag=etag, mtime=stat.st_mtime):
          return Response(status=HTTPStatus.NOT_MODIFIED, headers={'etag':etag}, last_modified=stat.st_mtime)

        response = self.transform_file_from_local_fs(request=request, norm_path=norm_path, local_path=local_path, file=file)
        response.headers.setdefault('etag', etag)
        response.headers.setdefault('last-modified', format_header_date(stat.st_mtime))

      transferred = response.body is file
      return response
    except:
      if response is not None: close_response_body(response.body)
      raise
    finally:
      if not transferred: file.close()


  def transform_file_from_local_fs(self, request:Request, norm_path:Path, local_path:Path, file:BufferedReader) -> Response:
    'Override to transform file content; by default, transfer the open file to the response.'
    return Response(body=file, media_type=self.guess_media_type(local_path))


  def list_directory(self, request:Request, local_path:Path) -> Response:
    'Render an HTML listing for a directory without an index.html file.'
    try: listing = scan_dir(local_path)
    except OSError as exc:
      logE('Failed to list directory.', local_path=local_path, exc=exc)
      raise ResponseError(status=HTTPStatus.NOT_FOUND) from exc
    listing.sort(key=lambda e: cast(str, e.name.lower()))

    title = html_escape('/' + '/'.join(request.path_segments), quote=False)

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


  def guess_media_type(self, path:str|Path) -> str:
    'Guess the mime type for a file path.'
    media_types = self.ext_media_types
    ext = path_ext(path).lower()
    try: return media_types[ext]
    except KeyError: return media_types['']



class FilesApp(_FilesServing, WebApp):
  'Serve a local directory as an entire web application, e.g. taptools `serve-dir`.'


  def __init__(self, local_dir:str, prevent_client_caching:bool=False, map_bare_names_to_html:bool=False) -> None:
    self.local_dir = str(Path(local_dir))
    self.prevent_client_caching = prevent_client_caching
    self.map_bare_names_to_html = map_bare_names_to_html


  def handle_request(self, request:Request) -> Response:
    request.allow_methods('GET', 'HEAD')
    return self.handle_file_request(request, Path('/' + '/'.join(request.path_segments)), as_dir=request.path.endswith('/'))



class FilesHandler(_FilesServing, RoutableHandler):
  '''
  Serve a local directory mounted under a router prefix.
  Mount with a `{subpath:path}` tail route whose handler subclass sets `local_dir`, e.g.:
    class MyStatic(FilesHandler): local_dir = '/path/to/assets'
    routes = { '/static/{subpath:path}': MyStatic }
  The captured `subpath` arrives decoded from the router and is mapped into `local_dir`;
  the full request path is used for directory redirects.
  '''

  local_dir = '' # Set by subclasses.
  prevent_client_caching = False
  map_bare_names_to_html = False
  _methods = frozenset({'GET', 'HEAD'})


  def __init__(self, request:Request, path_params:Mapping[str,object]) -> None:
    self.subpath = str(path_params['subpath'])


  def handle_request(self, request:Request) -> Response:
    return self.handle_file_request(request, Path('/' + self.subpath), as_dir=self.subpath.endswith('/'))


def compute_local_path(*, local_dir:str, norm_path:Path, as_dir:bool, map_bare_names_to_html:bool) -> Path:
  '''
  Map a normalized mount path into `local_dir`.

  Append `.html` to extensionless file names when configured, unless `as_dir` is true.
  '''
  if not norm_path.is_abs: raise ValueError(norm_path)
  if '..' in str(norm_path): raise ResponseError(HTTPStatus.FORBIDDEN)

  if map_bare_names_to_html and not as_dir and norm_path.has_name and not norm_path.ext:
    norm_path = norm_path.replace_ext('.html')

  return Path(local_dir) / norm_path.remove_ancestor(Path('/'))
