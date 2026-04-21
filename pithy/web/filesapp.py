# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import mimetypes
from html import escape as html_escape
from http import HTTPStatus
from io import BufferedReader
from typing import cast
from urllib.parse import quote as url_quote, unquote as url_unquote

from ..fs import is_dir, path_exists, scan_dir
from ..logs import logE
from ..path import path_ext, path_join
from .app import WebApp
from .errors import ResponseError
from .request import Request
from .response import html_media_type, Response
from .util import norm_url_path


class FilesApp(WebApp):


  def __init__(self, local_dir:str|None=None, prevent_client_caching:bool=False, map_bare_names_to_html:bool=False) -> None:

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


  def handle_request(self, request:Request) -> Response:
    request.allow_methods('GET', 'HEAD')
    return self.serve_content_from_local_fs(request)


  def serve_content_from_local_fs(self, request:Request, *, raw_path:str='') -> Response:
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
        query = '?' + request.query_str if request.query_str else ''
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
    ext = path_ext(path).lower()
    try: return self.ext_media_types[ext]
    except KeyError: return self.ext_media_types['']
    except KeyError: return self.ext_media_types['']


def compute_local_path(*, local_dir:str, norm_path:str, map_bare_names_to_html:bool) -> str:
  '''
  Compute local_path from a normalized url path (result of `norm_url_path`).
  If `map_bare_names_to_html` is True, then a path without a file extension has '.html' appended.
  '''

  if not local_dir or local_dir.endswith('/'): raise ValueError(local_dir)

  if not norm_path.startswith('/'): raise ValueError(norm_path)
  if '..' in norm_path: raise ResponseError(HTTPStatus.FORBIDDEN)

  if map_bare_names_to_html and not norm_path.endswith('/') and not path_ext(norm_path):
    norm_path += '.html'

  return local_dir + norm_path
