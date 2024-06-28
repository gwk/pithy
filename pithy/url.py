# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit as url_split, urlunsplit as url_unsplit

from .path import path_stem


def fmt_url(url:str, *path_parts:str, **params:Any) -> str:
  '''
  Path parts and params are escaped.
  '''
  if path_parts:
    url = '/'.join((url.rstrip('/'), *(quote(part) for part in path_parts)))
  if params:
    url = f'{url}?{urlencode(tuple((k, str(v)) for k, v in params.items()))}'
  return url


def url_scheme(url:str) -> str: return url_split(url).scheme

def url_netloc(url:str) -> str: return url_split(url).netloc

def url_path(url:str) -> str: return url_split(url).path

def url_query(url:str) -> str: return url_split(url).query

def url_fragment(url:str) -> str: return url_split(url).fragment


def url_query_params(url:str) -> dict[str,str]:
  return dict(parse_qsl(url_split(url).query))


def url_drop_scheme_fragment(url:str) -> str:
  return url_unsplit(url_split(url)._replace(scheme='', fragment=''))

def url_drop_scheme_query_fragment(url:str) -> str:
  return url_unsplit(url_split(url)._replace(scheme='', query='', fragment=''))

def url_drop_query_fragment(url:str) -> str:
  return url_unsplit(url_split(url)._replace(query='', fragment=''))

def url_drop_fragment(url:str) -> str:
  return url_unsplit(url_split(url)._replace(fragment=''))


def url_replace(url:str, **replacements:str) -> str:
  u = url_split(url)
  r = u._replace(**replacements)
  return url_unsplit(r)


def url_replace_ext(url:str, ext:str) -> str:
  u = url_split(url)
  stem = path_stem(u.path)
  return url_unsplit(u._replace(path=stem+ext))


def url_compose(scheme:str='', netloc:str='', path:str='', query:str='', fragment:str='') -> str:
  return url_unsplit((scheme, netloc, path, query, fragment))


def url_assuming_netloc(url:str) -> str:
  '''
  Sanitize a URL string by assuming that it has a netloc/host.
  This is important because a string like 'x.com' will be treated by urlparse/urlsplit as consisting only of a path,
  whereas a human assumes that it represents a host.

  This is essentially in direct contravention of urlparse compliance with the RFC:
  > Following the syntax specifications in RFC 1808, urlparse recognizes a netloc only if it is properly introduced by "//".
  > Otherwise the input is presumed to be a relative URL and thus to start with a path component.
  '''
  u = url_split(url)
  if u.netloc: return url
  # The URL does not have a netloc. This is usually because it was not preceded with the "//" prefix.
  netloc, _slash, path = u.path.partition('/')
  return url_unsplit(u._replace(netloc=netloc, path=path))
