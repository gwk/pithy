# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from argparse import ArgumentParser
from itertools import chain
from json import loads as parse_json
from typing import Iterable, Iterator, Match, Tuple, Union

from pithy.ansi import RST, TXT_B, TXT_D, TXT_L, TXT_M, TXT_R, TXT_Y
from pithy.fs import path_rel_to_current_or_abs
from pithy.interactive import ExitOnKeyboardInterrupt
from pithy.io import errL, outZ, stdout
from pithy.iterable import OnHeadless, group_by_heads
from pithy.lex import Lexer, Token
from pithy.task import run_gen

from .. import load_craft_config


def main() -> None:
  arg_parser = ArgumentParser(description='Swift compiler wrapper.')
  arg_parser.add_argument('-product', default=None)
  arg_parser.add_argument('-target', default=None)
  arg_parser.add_argument('-xctest', action='store_true')
  arg_parser.add_argument('args', nargs='*')
  args = arg_parser.parse_args()

  conf = load_craft_config()

  sub_cmd = 'test' if args.xctest else 'build'
  errL(f'swift compiler: {conf.swift_path}')

  cmd = ['swift', sub_cmd, '--package-path='+conf.project_dir, '--build-path='+conf.build_dir]
  if args.product: cmd.extend(['--product', args.product])
  if args.target: cmd.extend(['--target', args.target])
  cmd.extend(args.args)
  errL(TXT_D, ' '.join(cmd), RST)

  with ExitOnKeyboardInterrupt():
    for token in lex_compiler_output(run_gen(cmd, merge_err=True, exits=True)):
      kind = token.kind
      if kind in diag_kinds:
        diag_m = diag_re.fullmatch(token.text)
        if diag_m:
          path_abs, pos, msg = diag_m.groups()
          path = path_rel_to_current_or_abs(path_abs)
          color = colors[kind]
          outZ(TXT_L, path, pos, color, msg, RST)
        else:
          outZ(token.text)
      else:
        color = colors[kind]
        rst = color or RST
        outZ(color, token.text, rst)
      stdout.flush()


def lex_compiler_output(stream:Iterable[str]) -> Iterator[Token]:
  '''
  Yield the toplevel heads, e.g. "Compile Swift Module ..." immediately.
  Aggregate diagnostics into a buffer, then group by path heads.
  '''
  return lexer.lex_stream(stream)


lexer = Lexer(invalid='invalid',
  patterns=dict(
    newline   = r'\n',
    top_step  = r'\[\d+/\d+\] .+',
    error     = r'[^:\n]+:\d+:\d+: error: .+',
    warning   = r'[^:\n]+:\d+:\d+: warning: .+',
    note      = r'[^:\n]+:\d+:\d+: note: .+',
    unknown_error   = '<unknown>:0: error: .+',
    unknown_warning = '<unknown>:0: warning: .+',
    error_terminated = r'error: terminated.+', # comes in on stderr.
    underline = r'[ ]*[~^][~^ ]*',
    other     = r'.+',
))

diag_re = re.compile(r'([^:]+)(:\d+:\d+: )(\w+: .+)')

head_kinds = set(lexer.patterns) - {'newline', 'note', 'other'}
diag_head_kinds = {'error', 'warning', 'unknown_error', 'unknown_warning'}
diag_kinds = {*diag_head_kinds, 'note'}

def is_head(token:Match) -> bool:
  return token.lastgroup in head_kinds

def is_diag_head(token:Match) -> bool:
  return token.lastgroup in diag_head_kinds

def is_diag(token:Match) -> bool:
  return token.lastgroup in diag_kinds

def key_by_splitting_ints(string:str) -> Tuple[Union[str,int],...]:
  return tuple(int(s) if s.isnumeric() else s for s in int_re.split(string))

int_re = re.compile(r'(\d+)')


colors = {
  'newline'   : '',
  'top_step'  : TXT_M,
  'error'     : TXT_R,
  'warning'   : TXT_Y,
  'note'      : TXT_L,
  'unknown_error' : TXT_R,
  'unknown_warning' : TXT_Y,
  'error_terminated' : TXT_D,
  'underline' : TXT_B,
  'other'     : '',
}


if __name__ == '__main__': main()