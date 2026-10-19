# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from urllib.parse import unquote as url_unquote

from .errors import BadRequestError


_context_keywords_ = ['path segments', 'percent decoding', 'urllib.parse.unquote']


def decode_path_segments(path:str) -> list[str]:
  '''
  Split a raw request path on '/' and percent-decode each segment separately.

  Decoding per segment preserves the distinction between a '/' separator and an encoded '%2F' within a segment,
  which decoding the whole path first would erase. The leading slash is dropped; a trailing slash yields a trailing
  empty segment, so '/' decodes to [''] and '/a/' decodes to ['a', ''].
  Raises BadRequestError if a segment is not valid percent-encoded UTF-8, or decodes to a NUL character,
  which no file system or route name can contain, or decodes to a '/'.
  An encoded slash is refused because a handler would not expect a path parameter to contain a separator;
  if a route ever needs one, add a converter kind that opts in rather than relaxing this check for every route.
  '''
  segments = []
  for raw in path.removeprefix('/').split('/'):
    try: segment = url_unquote(raw, errors='strict')
    except UnicodeDecodeError as e: raise BadRequestError(f'Path segment is not valid percent-encoded UTF-8: {raw!r}.') from e
    if '\0' in segment: raise BadRequestError(f'Path segment contains a NUL character: {raw!r}.')
    if '/' in segment: raise BadRequestError(f'Path segment contains an encoded slash: {raw!r}.')
    segments.append(segment)
  return segments
