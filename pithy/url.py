# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from urllib.parse import urlsplit as split_url, urlunsplit as compose_url

from .path import path_stem


def url_scheme(url:str) -> str: return split_url(url).scheme

def url_netloc(url:str) -> str: return split_url(url).netloc

def url_path(url:str) -> str: return split_url(url).path

def url_query(url:str) -> str: return split_url(url).query

def url_fragment(url:str) -> str: return split_url(url).fragment


def url_scheme_netloc_path(url:str) -> str:
  scheme, netloc, path, query, fragment = split_url(url)
  return compose_url((scheme, netloc, path, None, None))


def url_netloc_path(url:str) -> str:
  scheme, netloc, path, query, fragment = split_url(url)
  return compose_url((None, netloc, path, None, None))


def drop_url_fragment(url:str) -> str:
  scheme, netloc, path, query, fragment = split_url(url)
  return compose_url((scheme, netloc, path, query, None))


def replace_url_ext(url:str, ext:str) -> str:
  scheme, netloc, path, query, fragment = split_url(url)
  stem = path_stem(path)
  return compose_url((scheme, netloc, stem + ext, query, fragment))

