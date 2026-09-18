# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from pathlib import Path
from tempfile import TemporaryDirectory

from taptools.bin.crawl import Crawler
from utest import utest_run, utest_val


@utest_run
def _() -> None:
  'Extract links without requiring a tree, then resolve and filter the URLs.'
  with TemporaryDirectory() as dir:
    path = Path(dir) / 'index.html'
    path.write_text('''
      <link href="/style.css"/>
      <ul><li><A HREF=one>One<li><a href="two?a=1&amp;b=2#fragment">Two</ul>
      <a href="first" href="ignored">Duplicate attribute</a>
      <a href>Empty</a><a>No href</a>
      <a href="https://other.example/out">External</a>
      <!-- <a href="comment"> -->
      <script>const text = '<a href="script">';</script>
      <style>/* <a href="style"> */</style>
    ''')
    crawler = Crawler(dir=dir, patterns=[re.compile(r'https://example\.com/')], clip_paths=[], remaining=set(),
      visited=set(), force=False)
    crawler.try_scrape('https://example.com/docs/index.html', str(path))
    utest_val({
      'https://example.com/style.css',
      'https://example.com/docs/one',
      'https://example.com/docs/two?a=1&b=2',
      'https://example.com/docs/first',
      'https://example.com/docs/index.html',
    }, crawler.remaining)
    utest_val({'https://other.example/out'}, crawler.skipped)
    crawler.remaining.clear()
    path.write_text('')
    crawler.try_scrape('https://example.com/docs/index.html', str(path))
    utest_val(set(), crawler.remaining)
