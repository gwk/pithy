#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from argparse import ArgumentParser, FileType
from dataclasses import dataclass, field
from shlex import quote as sh_quote
from typing import Any, Dict, List, Pattern, Set, Tuple, Union
from urllib.parse import urldefrag, urljoin, urlsplit
from xml.etree.ElementTree import Element

import html5_parser

from pithy.fs import (file_status, is_dir, is_file, make_dir, make_dirs, make_link, move_file, path_descendants, path_dir,
  path_exists, path_ext, path_join, remove_path, remove_path_if_exists)
from pithy.io import errL, errSL, outL, outSL, errD
from pithy.path_encode import COMP, OMIT, SPLIT, SQUASH, path_for_url
from pithy.string import clip_first_prefix
from pithy.task import runO
from pithy.iterable import prefix_tree


def main() -> None:
  arg_parser = ArgumentParser(description='Crawl URLs, using a regex filter for discovered links.')
  arg_parser.add_argument('seeds', nargs='+', help='URLs to crawl.')
  arg_parser.add_argument('-patterns', nargs='*', help='regex predicates that filter discovered links. '
    'A URL matching any pattern will be crawled. Defaults to the seed URLs.')
  arg_parser.add_argument('-clip-paths', nargs='*', help='path prefixes to clip each result with.')
  arg_parser.add_argument('-out', required=True, help='output directory.')
  arg_parser.add_argument('-force', action='store_true', help='always fetch URLs, even when cached results are present.')
  args = arg_parser.parse_args()

  dir = args.out
  seed0 = args.seeds[0]
  seeds = {clean_url(seed0, url) for url in args.seeds}

  ds = file_status(dir, follow=True)
  if ds is None:
    make_dirs(dir)
  elif not ds.is_dir:
    exit(f'output path exists and is not a directory: {dir!r}')

  if not args.patterns: # Default to seed URLs.
    args.patterns = [re.escape(s) for s in seeds]

  patterns:List[Pattern] = []
  for s in args.patterns:
    try: p = re.compile(s)
    except Exception as e: exit(f'bad pattern regex: {e}\n {s}')
    patterns.append(p)


  crawler = Crawler(
    dir=dir,
    patterns=patterns,
    clip_paths=args.clip_paths,
    remaining=set(seeds),
    visited=set(),
    force=args.force)

  crawler.crawl()
  describe_skipped(crawler.skipped)


@dataclass(frozen=True)
class Crawler:
  dir:str
  patterns:List[Pattern]
  clip_paths:List[str]
  remaining:Set[str]
  visited:Set[str]
  force:bool
  skipped:Set[str] = field(default_factory=set)
  max_redirects = 8

  def crawl(self) -> None:
    while self.remaining:
      url = self.remaining.pop()
      self.crawl_url(url=url)


  def crawl_url(self, url:str, redirects=0) -> None:
    assert url not in self.remaining
    assert url not in self.visited

    if redirects > self.max_redirects:
      errSL('too many redirects:', url)
      return

    self.visited.add(url)

    path = self.path_for_url(url)
    tmp_path = self.tmp_path_for_url(url)
    if is_dir(tmp_path, follow=False): exit(f'error: please remove the directory existing at path: {path}')
    if is_dir(tmp_path, follow=False): exit(f'error: please remove the directory existing at tmp path: {tmp_path}')

    if self.force or not is_file(path, follow=True):
      make_dirs(path_dir(tmp_path))
      remove_path_if_exists(tmp_path)

      cmd = ['curl', url, '-o', tmp_path]
      errSL('\ncrawl:', *[sh_quote (word) for word in cmd])
      cmd.extend(['--progress-bar', '--write-out', curl_output_fmt])
      output = runO(cmd)
      errL(output)
      results = parse_curl_output(output)
      code = results['http_code']

      if code in http_redirect_codes:
        redirect_url = clean_url(base=url, url=results['redirect_url'])
        if redirect_url == url:
          errSL(f'CIRCULAR redirect: {url} -> {redirect_url}')
          return
        errSL(f'redirect: {url} -> {redirect_url}')
        redirect_path = self.path_for_url(redirect_url)
        make_link(orig=redirect_path, link=path, allow_nonexistent=True, overwrite=True)
        remove_path(tmp_path)
        if redirect_url not in self.visited and redirect_url not in self.remaining:
          self.crawl_url(redirect_url, redirects=redirects+1)

      elif code in http_success_codes:
        move_file(tmp_path, to=path, overwrite=True)

      else:
        errSL('bad result:', code)
        return

      errSL(f'{url} : {path}')

    # Determine if we should scrape this document for links.
    url = url.partition('?')[0]
    ext = path_ext(url)
    should_scrape = (ext in ('', '.html', '.htm'))
    if should_scrape:
      self.try_scrape(url, path)


  def try_scrape(self, url:str, path:str) -> None:
    try: text = open(path).read()
    except IsADirectoryError: raise
    except Exception as e:
      errSL(f'{path}: could not read contents as text: {e}')
      return
    scraped_urls:Set[str] = set()
    if html5_re.match(text):
      self.scrape_html5(url=url, text=text)
    else:
      raise Exception('non-html5 parsing is not supported.')


  def scrape_html5(self, url:str, text:str) -> None:
    html = html5_parser.parse(text, return_root=True, line_number_attr='#', sanitize_names=False)
    self.walk_html_hrefs(url=url, node=html)

  def walk_html_hrefs(self, url:str, node:Any) -> None:
    href = node.get('href')
    if href is not None:
      self.add_url(base=url, url=href)
    for child in node:
      self.walk_html_hrefs(url=url, node=child)


  def add_url(self, base:str, url:str) -> None:
    url = clean_url(base, url)
    if url in self.skipped or url in self.remaining or url in self.visited: return
    for p in self.patterns:
      if p.match(url):
        self.remaining.add(url)
        return
    #if url not in self.skipped: outSL('skipping:', url)
    self.skipped.add(url)


  def path_for_url(self, url:str) -> str:
    p = path_for_url(url, normalize=True, scheme=OMIT, host=COMP, path=SPLIT, query=SQUASH, fragment=OMIT)
    p = clip_first_prefix(p, self.clip_paths, req=False)
    return self.resolve_dir_collisions(path_join(self.dir, p))


  def tmp_path_for_url(self, url:str) -> str:
    p = path_for_url(url, normalize=True, scheme=OMIT, host=COMP, path=SQUASH, query=SQUASH, fragment=OMIT)
    return path_join(self.dir, p) + '.tmp'


  def resolve_dir_collisions(self, path:str) -> str:
    '''
    If any intermediate paths are occupied by files, rename those files and create directories.
    Return the path to use.
    '''
    # Resolve intermediates.
    for intermediate in path_descendants(self.dir, path, include_start=False, include_end=False):
      s = file_status(intermediate, follow=True)
      if s is None:
        make_dir(intermediate)
      elif not s.is_dir:
        tmp_path = path_join(self.dir, '_resolving_dir_collision.tmp')
        final_path = intermediate + '/+'
        move_file(intermediate, tmp_path)
        make_dir(intermediate)
        move_file(tmp_path, final_path)
    # Resolve tip.
    # TODO: improve confidence that this does the right thing in the presence of symlinks.
    s = file_status(path, follow=False)
    if s is None or not s.is_dir: return path
    path += '/+'
    if is_dir(path, follow=False):
      exit(f'error: path collision could not be resolved. Please remove the directory at {path!r}')
    return path


curl_output_fmt = '|'.join(f'{k}:%{{{k}}}' for k in [
  'http_code',
  'num_redirects',
  'content_type',
  'size_download',
  'time_total',
  'redirect_url',
])


def parse_curl_output(output:str) -> Dict[str,str]:
  triples = [word.partition(':') for word in output.split('|')]
  return { k:v for k,_,v in triples }


http_redirect_codes = {
  '301',
  '302',
  '303',
  '307',
  '308',
}

http_success_codes = {
  '200', # Standard.
  '203', # Transforming proxy is returning a modified version.
}


def clean_url(base:str, url:str='') -> str:
  res = urljoin(base, url)
  return urldefrag(res)[0] # type: ignore


def describe_skipped(skipped:Set[str]) -> None:
  'Describe URLs that were skipped by building a prefix tree.'
  tree = prefix_tree(_split_skipped(url) for url in skipped)
  _simplify(tree)
  outL('\nSkipped URLs:')
  _describe_skipped(tree, indent='')


def _split_skipped(url:str) -> List[str]:
  '''
  Split a skipped URL into parts for the purpose of building an informative prefix tree.
  We only omit the http and https schemes, because other schemes are unusual and should be reported.
  '''
  url = clip_first_prefix(url, ['https://', 'http://'], req=False)
  return url_parts_re.split(url)


def _simplify(tree:Dict) -> None:
  try: del tree[None]
  except KeyError: pass
  for child in tree.values(): _simplify(child)


def _describe_skipped(tree:Dict, indent:str) -> None:
  if len(tree) == 1:
    k, v = next(iter(tree.items()))
    _describe_skipped(v, indent=f'{indent}{k}/')
  elif tree and not any(tree.values()):
    outL(indent, ', '.join(k or repr(k) for k in tree))
  else:
    for k, v in sorted(tree.items()):
      outL(indent, k or repr(k))
      _describe_skipped(v, indent+'  ')


url_parts_re = re.compile(r'(?x) [/]+')

html5_re = re.compile(r'(?ix) \s* <!doctype \s+ html>')


if __name__ == '__main__': main()
