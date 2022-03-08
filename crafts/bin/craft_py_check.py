# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-py-check` is a wrapper around the MyPy type checker.
It originally worked around some rather frustrating usability bugs in `mypy`,
many of which have since been fixed.
Now its main utility is in providing some additional smarts for finding dependencies,
and for converting the output diagnostic file/line info into the same format as used by clang and swift.
'''

from argparse import ArgumentParser
from importlib.util import find_spec as find_module_spec
from os import environ
from sys import stdout
from typing import List

from mypy import api

from pithy.ansi import INVERT, RST, TXT_C, TXT_L, TXT_R, TXT_Y
from pithy.io import errL, errSL, outZ
from pithy.lex import Lexer
from pithy.path import abs_path, path_dir, path_join, path_name
from tolkien import Source


def main() -> None:
  arg_parser = ArgumentParser(description='Run mypy, format and colorize output.')
  arg_parser.add_argument('roots', nargs='+')
  arg_parser.add_argument('-dmypy', '-d', action='store_true', help='Use dmypy daemon to speed up repeated typechecking runs.')
  arg_parser.add_argument('-deps', nargs='+', default=[], help='Names of package dependencies to typecheck against.')
  arg_parser.add_argument('-paths', nargs='+', default=[], help='Package search paths to add to MYPY_PATH to typecheck against.')
  arg_parser.add_argument('-print-ok', action='store_true', help='Print an "ok" message when exiting with no errors.')
  arg_parser.add_argument('-python-version', help='Python version to pass to mypy.')
  arg_parser.add_argument('-dbg', action='store_true', help='Print debug messages.')
  arg_parser.add_argument('-mypy-dbg', action='store_true', help='Pass debugging flags to mypy.')

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
      assert spec.parent
      p_spec = find_module_spec(spec.parent)
      assert p_spec is not None and p_spec != spec
      spec = p_spec
    path = spec.origin
    assert path
    assert path_name(path) == '__init__.py'
    search_path = path_dir(path_dir(path))
    mypy_path.append(search_path)
    typestubs_path = path_join(search_path, 'typestubs')
    mypy_path.append(typestubs_path)

  for p in args.paths:
    if ':' in p: exit(f'bad `-path` argument: {p!r}')
    mypy_path.append(abs_path(p))

  if mypy_path:
    env['MYPYPATH'] = ':'.join(mypy_path)
    if args.dbg: errSL(f'MYPYPATH={mypy_path}')

  version_flag = ['--python-version', args.python_version] if args.python_version else []
  run_fn = api.run_dmypy if args.dmypy else api.run # type: ignore
  mypy_args = [*version_flag, *args.roots]
  if args.mypy_dbg: mypy_args.append('--show-traceback')
  if args.dbg: errSL('args:', *mypy_args)
  (o, e, c) = run_fn(mypy_args)

  # Lex the output from mypy.
  source = Source(name='mypy', text=o)
  for token in lexer.lex(source):
    s = source[token]
    kind = token.kind
    if kind == 'location' and '/' not in s and '<' not in s:
      s = './' + s
    try: color = colors[kind]
    except KeyError: outZ(s)
    else: outZ(color, s, RST)
    stdout.flush()
  if c == 0 and args.print_ok: print('ok.')
  exit(c)

lexer = Lexer(patterns=dict(
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
