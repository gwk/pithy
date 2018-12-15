# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from importlib.util import find_spec as find_module_spec
from pithy.ansi import *
from pithy.io import *
from pithy.path import abs_path, path_name, path_dir
from pithy.lex import Lexer
from pithy.task import runCO
from argparse import ArgumentParser
from os import environ
from typing import Set


def main() -> None:
  arg_parser = ArgumentParser(description='Run mypy, format and colorize output.')
  arg_parser.add_argument('-print-ok', action='store_true')
  arg_parser.add_argument('-python-version')
  arg_parser.add_argument('roots', nargs='+')
  arg_parser.add_argument('-deps', nargs='+', default=[])
  arg_parser.add_argument('-paths', nargs='+', default=[])
  arg_parser.add_argument('-dbg', action='store_true')

  args = arg_parser.parse_args()

  env = environ.copy()

  mypy_path:List[str] = []
  existing_path = env.get('MYPYPATH')
  if existing_path:
    mypy_path.extend(existing_path.split(':'))

  for dep in args.deps:
    spec = find_module_spec(dep)
    if spec is None:
      errL(f'warning: could not find dependency: {dep!r}')
      continue
    while spec.parent != dep:
      s = find_module_spec(spec.parent)
      assert s is not None and s != spec
      spec = s
    path = spec.origin
    assert path_name(path) == '__init__.py'
    search_path = path_dir(path_dir(path))
    mypy_path.append(search_path)

  for p in args.paths:
    if ':' in p: exit(f'bad `-path` argument: {p!r}')
    mypy_path.append(abs_path(p))

  if mypy_path:
    env['MYPYPATH'] = ':'.join(mypy_path)
    if args.dbg: errSL(f'MYPYPATH={mypy_path}')

  version_flag = ['--python-version', args.python_version] if args.python_version else []
  cmd = ['mypy', *version_flag, *args.roots]
  if args.dbg: errSL('cmd:', *cmd)
  c, o = runCO(cmd, env=env)
  for token in lexer.lex(o):
    s = token[0]
    kind = token.lastgroup
    if kind == 'location' and '/' not in s and '<' not in s:
      s = './' + s
    try: color = colors[kind]
    except KeyError: outZ(s)
    else: outZ(color, s, RST)
    stdout.flush()
  if c == 0 and args.print_ok: print('ok.')
  exit(c)

lexer = Lexer(invalid='invalid', patterns=dict(
  newline   = r'\n',
  location  = r'[^\n]+:\d+:(\d+:)?',
  error     = r'error:',
  warning   = r'warning:',
  note      = r'note:',
  quoteD    = r'"[^"]*"',
  quoteS    = r"'[^']*'",
  text      = r'.+?',
))

colors = {
  'invalid'   : INVERT,
  'location'  : TXT_L,
  'error'     : TXT_R,
  'warning'   : TXT_Y,
  'note'      : TXT_L,
  'quoteD'    : TXT_C,
  'quoteS'    : TXT_C,
}

if __name__ == '__main__': main()
