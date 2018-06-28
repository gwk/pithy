#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from argparse import ArgumentParser
from itertools import chain
from json import loads as parse_json
from typing import *
from pithy.ansi import *
from pithy.io import *
from pithy.fs import *
from pithy.iterable import group_by_heads, OnHeadless
from pithy.lex import Lexer
from pithy.task import run_gen
from craft import *


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

  cmd = ['swift', sub_cmd, '--package-path='+conf.project_dir, '--build-path='+conf.build_dir,
    '-Xswiftc=-target', '-Xswiftc='+conf.target_triple_macOS]
  if args.product: cmd.extend(['--product', args.product])
  if args.target: cmd.extend(['--target', args.target])
  cmd.extend(args.args)
  errSL(TXT_D, *cmd, RST)

  for token in lex_deduplicate_reorder(run_gen(cmd, merge_err=True, exits=True)):
    if token.lastgroup in diag_kinds:
      path_abs, pos, msg = diag_re.fullmatch(token[0]).groups()
      path = path_rel_to_current_or_abs(path_abs)
      color = colors[token.lastgroup]
      outZ(TXT_L, path, pos, color, msg, RST)
    else:
      s = token[0]
      try: color = colors[token.lastgroup]
      except KeyError: outZ(s)
      else: outZ(color, s, RST)
    stdout.flush()


def lex_deduplicate_reorder(swift_output_stream):
  '''
  Yield the toplevel heads, e.g. "Compile Swift Module ..." immediately.
  Aggregate diagnostics into a buffer, then group by path heads.
  These need to be deduplicated as of Xcode 9.0 GM.
  '''
  it = lexer.lex_stream(swift_output_stream)
  for token in it:
    yield token
    if is_toplevel(token): break

  group = []
  def flush():
    subgroups = list(group_by_heads(group, is_head=is_diag_head, headless=OnHeadless.keep))
    group.clear()
    d = { ''.join(t[0] for t in sg) : sg for sg in subgroups } # deduplicates.
    return chain.from_iterable(v for (_, v) in sorted(d.items(), key=lambda p: key_by_splitting_ints(p[0])))

  for token in it:
    if is_toplevel(token):
      yield from flush()
      yield token
    else:
      group.append(token)
  yield from flush()


lexer = Lexer(invalid='invalid',
  patterns=dict(
    newline   = r'\n',
    compile   = r'Compile Swift Module .+\n',
    linking   = r'Linking .+',
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

diag_kinds = ('error', 'warning', 'note')

def is_toplevel(token) -> bool:
  return token.lastgroup in {'compile', 'linking', 'error_terminated'}

def is_diag_head(token) -> bool:
  return token.lastgroup in {'error', 'warning', 'unknown_error', 'unknown_warning'}

def key_by_splitting_ints(string: str) -> Tuple[Union[str, int], ...]:
  return tuple(int(s) if s.isnumeric() else s for s in int_re.split(string))

int_re = re.compile(r'(\d+)')


colors = {
  'invalid'   : INVERT,
  'compile'   : TXT_M,
  'linking'   : TXT_M,
  'error'     : TXT_R,
  'warning'   : TXT_Y,
  'note'      : TXT_L,
  'unknown_error' : TXT_R,
  'unknown_warning' : TXT_Y,
  'error_terminated' : TXT_D,
  'underline' : TXT_B,
}


if __name__ == '__main__': main()
