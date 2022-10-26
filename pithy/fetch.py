# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus
from random import uniform as rand_uniform
from shlex import quote as sh_quote
from time import sleep
from typing import Any, Dict
from urllib.parse import urlencode, urlparse

from .fs import make_dirs, move_file, path_dir, path_exists, path_ext, path_join
from .io import errSL
from .path_encode import path_for_url
from .task import runCO


class HTTPError(Exception):
  def __init__(self, msg:str, curl_code:int=0, status_code:int=-1):
    super().__init__(msg)
    self.curl_code = curl_code
    self.status_code = status_code


def fetch(url:str, cache_path:str='', params:Dict[str, str]={}, headers:Dict[str, str]={}, expected_status_code=200, timeout=30, delay=0, delay_range=0, spoof_ua=False) -> str:
  "Fetch the data at `url` and save it to a path in the '_fetch' directory derived from the URL."
  if params:
    if '?' in url: raise ValueError("params specified but url already contains '?'")
    url += '?' + urlencode(params)
  if not cache_path:
    cache_path = path_for_url(url)
  path = path_join('_fetch', cache_path)
  path_tmp = path_join('_fetch/tmp', cache_path)
  if not path_exists(path, follow=False):
    cmd = ['curl', url, '--write-out', '%{http_code}', '--output', path_tmp]
    if spoof_ua:
      h = spoofing_headers()
      h.update(headers) # any explicit headers override the spoofing values.
      headers = h
    for k, v in headers.items():
      cmd.extend(('--header', f'{k}: {v}'))
    make_dirs(path_dir(path_tmp))
    errSL('fetch:', *[sh_quote(word) for word in cmd])
    curl_code, output = runCO(cmd)
    if curl_code != 0:
      raise HTTPError(f'curl failed with code: {curl_code}', curl_code=curl_code)
      # TODO: copy the error code explanations from `man curl`? Or parse them on the fly?
    try:
      status_code = int(output)
      status = HTTPStatus(status_code)
    except ValueError as e:
      raise HTTPError(f'curl returned strange HTTP code: {repr(output)}') from e
    if status_code != expected_status_code:
      raise HTTPError(msg=f'fetch failed with HTTP code: {status.value}: {status.phrase}; {status.description}.',
        status_code=status_code)
    make_dirs(path_dir(path))
    move_file(path_tmp, path)
    sleep_min = delay - delay_range * 0.5
    sleep_max = delay + delay_range * 0.5
    sleep_time = rand_uniform(sleep_min, sleep_max)
    if sleep_time > 0:
      sleep(sleep_time)
  return path


def load_url(url:str, ext:str='', cache_path:str='', params:Dict[str, str]={}, headers:Dict[str, str]={}, expected_status_code=200, timeout=30, delay=0, delay_range=0, spoof_ua=False, **kwargs:Any) -> Any:
  'Fetch the data at `url` and then load using `loader.load`.'
  from .loader import load
  if not ext:
    if cache_path:
      ext = path_ext(cache_path)
    else:
      # extract the extension from the url path;
      # we cannot leave it to load because it sees the encoded path,
      # which may have url parameters/query/fragment.
      parts = urlparse(url)
      ext = path_ext(parts.path) # TODO: support compound extensions, e.g. 'tar.gz'.
  path = fetch(url, cache_path=cache_path, params=params, headers=headers, expected_status_code=expected_status_code,
    timeout=timeout, delay=delay, delay_range=delay_range, spoof_ua=spoof_ua)
  return load(path, ext=ext, **kwargs)


def spoofing_headers() -> Dict[str, str]:
  # Headers that Safari sent at one point. Not sure how up-to-date these ought to be.
  # TODO: allow imitating other browsers?
  return {
    'DNT': '1',
    'Upgrade-Insecure-Requests': '1',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Cache-Control': 'max-age=0',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_2) AppleWebKit/602.3.12 (KHTML, like Gecko) Version/10.0.2 Safari/602.3.12',
  }
