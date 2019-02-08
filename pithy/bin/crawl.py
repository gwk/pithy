#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser, FileType
from dataclasses import dataclass
from pithy.io import errL, errSL, errP, stdin
from pithy.fs import (file_status, is_dir, is_file, make_dir, make_dirs, make_link, move_file,
  path_descendants, path_dir, path_exists, path_ext, path_join, remove_path_if_exists)
from pithy.path_encode import path_for_url, OMIT, COMP, SQUASH
from pithy.string import replace_prefix
from pithy.task import runO
from shlex import quote as sh_quote
from typing import Any, Dict, List, Pattern, Set, Tuple, Union
from urllib.parse import urldefrag, urljoin, urlsplit
from xml.etree.ElementTree import Element
import html5_parser
import re


def main() -> None:
  arg_parser = ArgumentParser(description='Crawl URLs, using a regex filter for discovered links.')
  arg_parser.add_argument('urls', nargs='+', help='URLs to scrape.')
  arg_parser.add_argument('-link-filter', required=True, help='regex predicate for determining discovered links to crawl.')
  arg_parser.add_argument('-out', required=True, help='output directory.')
  arg_parser.add_argument('-force', action='store_true', help='always fetch URLs, even when cached results are present.')
  args = arg_parser.parse_args()

  dir = args.out
  url0 = args.urls[0]
  seeds = {clean_url(url0, url) for url in args.urls}

  ds = file_status(dir)
  if ds is None:
    make_dirs(dir)
  elif not ds.is_dir:
    exit(f'output path exists and is not a directory: {dir!r}')

  crawler = Crawler(
    dir=dir,
    link_filter=re.compile(args.link_filter),
    remaining=seeds,
    visited=set(),
    force=args.force)

  crawler.crawl()


@dataclass(frozen=True)
class Crawler:
  dir:str
  link_filter:Pattern
  remaining:Set[str]
  visited:Set[str]
  force:bool


  def crawl(self) -> None:
    while self.remaining:
      url = self.remaining.pop()
      self.crawl_url(url=url)


  def crawl_url(self, url:str) -> None:
    assert url not in self.remaining
    assert url not in self.visited

    path = self.path_for_url(url)
    tmp_path = self.tmp_path_for_url(url)
    if is_dir(tmp_path): exit(f'error: please remove the directory existing at tmp path: {tmp_path}')

    if self.force or not is_file(path):
      make_dirs(path_dir(tmp_path))
      remove_path_if_exists(tmp_path)

      cmd = ['curl', '-L', url, '-o', tmp_path]
      errSL('\ncrawl:', *[sh_quote(word) for word in cmd])
      cmd.extend(['--progress-bar', '--write-out', curl_output_fmt])
      output = runO(cmd)
      errL(output)
      results = parse_curl_output(output)

      final_url = results['url_effective']
      final_path = self.path_for_url(final_url)
      move_file(tmp_path, to=final_path, overwrite=True)

      errSL(f'{final_url} : {final_path}')
      if path != final_path: # add symlink.
        errSL(f'{url} > {path}')
        remove_path_if_exists(path)
        make_link(orig=final_path, link=path)
        self.visited.add(final_url)

    self.visited.add(url)

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
    if url not in self.remaining and url not in self.visited and self.link_filter.match(url):
      self.remaining.add(url)


  def path_for_url(self, url:str) -> str:
    p = path_for_url(url, normalize=True, split_path=True, lead_path_slash=False,
      scheme=OMIT, host=COMP, path=COMP, query=SQUASH, fragment=OMIT)
    return self.resolve_dir_collisions(path_join(self.dir, p))


  def tmp_path_for_url(self, url:str) -> str:
    p = path_for_url(url, normalize=True, split_path=False, lead_path_slash=False,
      scheme=OMIT, host=COMP, path=SQUASH, query=SQUASH, fragment=OMIT)
    return path_join(self.dir, p) + '.tmp'


  def resolve_dir_collisions(self, path:str) -> str:
    '''
    If any intermediate paths are occupied by files, rename those files and create directories.
    Return the path to use.
    '''
    # Resolve intermediates.
    for intermediate in path_descendants(self.dir, path, include_start=False, include_end=False):
      s = file_status(intermediate)
      if s is None:
        make_dir(intermediate)
      elif not s.is_dir:
        tmp_path = path_join(self.dir, '_resolving_dir_collision.tmp')
        final_path = intermediate + '/+'
        move_file(intermediate, tmp_path)
        make_dir(intermediate)
        move_file(tmp_path, final_path)
    # Resolve tip.
    s = file_status(path)
    if s is None or not s.is_dir: return path
    path += '/+'
    if is_dir(path): exit(f'error: path collision could not be resolved. Please remove the directory at {path!r}')
    return path


curl_output_fmt = '|'.join(f'{k}:%{{{k}}}' for k in [
  'http_code',
  'num_redirects',
  'content_type',
  'size_download',
  'time_total',
  'url_effective',
])


def parse_curl_output(output:str) -> Dict[str,str]:
  triples = [word.partition(':') for word in output.split('|')]
  return { k:v for k,_,v in triples }


def clean_url(base:str, url:str='') -> str:
  res = urljoin(base, url)
  return urldefrag(res)[0] # type: ignore


html5_re = re.compile(r'(?ix) \s* <!doctype \s+ html>')



if __name__ == '__main__': main()
