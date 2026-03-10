# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from urllib.parse import unquote as url_unquote, urlsplit as url_split

from ..path import norm_path


def norm_url_path(url:str) -> str:
  '''
  Compute a normalized path from the argument url.
  The path is not safe to use as is: it can still contain '..'.
  `compute_local_path` will sanitize the path.
  '''
  path = url_split(url).path
  if not path.startswith('/'): raise ValueError(path)
  trailing_slash = '/' if (path != '/' and path.endswith('/')) else ''
  path = url_unquote(path)
  path = norm_path(path)
  if path != '/' and path.endswith('/'): raise ValueError(path) # Should be guaranteed by norm_path.
  return path + trailing_slash
