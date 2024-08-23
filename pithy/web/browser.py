# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser

from pithy.task import run


def add_browser_args(parser:ArgumentParser, add_browse:bool=False) -> None:
  '''
  Add browser selection arguments to the parser.
  '''

  browsers = parser.add_mutually_exclusive_group()

  def add_browser(name:str, browser:str) -> None:
    browsers.add_argument(name, dest='browser', action='store_const', const=browser, help=f'Launch {browser}')

  if add_browse:
    add_browser('-browse', 'default browser')

  add_browser('-chrome', 'Google Chrome')
  add_browser('-firefox', 'Firefox')
  add_browser('-safari', 'Safari')
  add_browser('-stp', 'Safari Technology Preview')



def launch_browser(url:str, browser:str|None) -> None:

  # Note: this is macOS specific. It is simpler than the webbrowser module, which uses osascript.
  cmd = ['open']
  if browser and browser != 'default browser':
    cmd.extend(['-a', browser])
  cmd.append(url)
  run(cmd)
