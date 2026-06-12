# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser

from playwright.sync_api import sync_playwright
from utest.proctest import TestProcess

from ..fs import make_dirs
from ..path import path_dir, path_join
from ..path_encode import path_encode_url


def main() -> None:

  parser = ArgumentParser()
  parser.add_argument('-cmd', nargs='+', help='The server command to invoke.')
  parser.add_argument('-module', action='store_true', help='Whether to treate cmd as a python module to invoke.')
  parser.add_argument('-url', default='', help='The base URL to visit.')
  parser.add_argument('-out-dir', required=True, help='The output directory to use.')
  parser.add_argument('-pages', nargs='*', default=[], help='The pages to visit.')
  parser.add_argument('-pages-list-file', help='The file containing the list of pages to visit.')
  parser.add_argument('-browsers', nargs='+', default=['chromium'], help='The browsers to use.')
  parser.add_argument('-widths', nargs='+', type=int, default=[1024], help='The view widths to use.')
  parser.add_argument('-height', type=int, default=1024, help='The view height to use.')
  parser.add_argument('-wait', type=float, default=0.0, help='The wait time to use.')

  args = parser.parse_args()
  server_cmd = args.cmd
  server_url = args.url.rstrip('/')
  out_dir = args.out_dir

  make_dirs(out_dir)

  pages = list(args.pages)
  if args.pages_list_file:
    with open(args.pages_list_file, 'r') as f:
      pages.extend(f.read().splitlines())

  if not pages: exit('No pages specified.')

  for browser_name in args.browsers:
    if browser_name not in ('chromium', 'firefox', 'webkit'):
      raise ValueError(f"Unknown browser: {browser_name}")

  if server_cmd:
    with TestProcess(server_cmd, module=args.module, merge_stderr=True) as server_proc:
      if not server_url:
        m = server_proc.wait_for_pattern(r'"url":"(http://localhost:\d+)"')
        server_url = m.group(1)
      take_screenshots(server_url=server_url, pages=pages, out_dir=out_dir, browsers=args.browsers, widths=args.widths, height=args.height, wait=args.wait)
  else:
    if not server_url: exit('Either a server URL or a server command must be specified.')
    take_screenshots(server_url=server_url, pages=pages, out_dir=out_dir, browsers=args.browsers, widths=args.widths, height=args.height, wait=args.wait)


def take_screenshots(*, server_url:str, pages:list[str], out_dir:str, browsers:list[str], widths:list[int], height:int, wait:float) -> None:
  width0 = widths[0]
  with sync_playwright() as pw:
    for browser_name in browsers:
      browser = getattr(pw, browser_name).launch()
      for page in pages:
        page = page.lstrip('/')
        page_url = f'{server_url}/{page}'
        page_path = path_encode_url(page).lstrip(',/') # path_encode_url returns leading ',,/'.
        page_out_prefix = path_join(out_dir, page_path)
        page_out_dir = path_dir(page_out_prefix)
        make_dirs(page_out_dir)
        with browser.new_page(viewport=dict(width=width0, height=height)) as page:
          page.goto(page_url, wait_until='networkidle')
          if wait:
            page.wait_for_timeout(int(wait * 1000))
          for i, width in enumerate(widths):
            out_path = f"{page_out_prefix}__w{width}_{browser_name}.png"
            if i: page.set_viewport_size(dict(width=width, height=height))
            print(page_url, width, out_path)
            page.screenshot(path=out_path, full_page=True)
      browser.close()


if __name__ == "__main__": main()
