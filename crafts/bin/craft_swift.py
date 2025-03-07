# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-swift` is a build tool wrapper around the swift compiler.
'''

import re
from argparse import ArgumentParser

from pithy.ansi import RST, RST_TXT, TXT_B, TXT_D, TXT_L, TXT_M, TXT_R, TXT_Y
from pithy.interactive import ExitOnKeyboardInterrupt
from pithy.io import errL, outZ, stdout
from pithy.iterable import group_by_heads, OnHeadless
from pithy.lex import Lexer
from pithy.path import path_rel_to_current_or_abs
from pithy.task import runC, runCO
from tolkien import Source, Token

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

  cmd = ['swift', sub_cmd, '--package-path='+conf.project_dir]
  if conf.build_dir != '.build':
    cmd.append('--build-path='+conf.build_dir)
  if args.product: cmd.extend(['--product', args.product])
  if args.target: cmd.extend(['--target', args.target])
  cmd.extend(args.args)
  errL(TXT_D, ' '.join(cmd), RST)

  with ExitOnKeyboardInterrupt():
    should_filter = True
    if should_filter:
      # As of Swift 5.9.0 (2023-09-30), swift build generates duplicate build messages. Deduplicate these.
      c, o = runCO(cmd)
      source = Source(name='swift', text=o)
      token_stream = lexer.lex(source)
      head_texts:set[str] = set()
      for g in group_by_heads(token_stream, is_head=is_pair_group_head, headless=OnHeadless.keep):
        head_token = g[0]
        head_text = source[head_token]
        if head_text in head_texts:
          continue
        head_texts.add(head_text)
        for token in g:
          kind = token.kind
          text = source[token]
          color = colors[kind]
          if kind in diag_kinds:
            if diag_m := diag_re.fullmatch(text):
              path_abs, pos, msg = diag_m.groups()
              path = path_rel_to_current_or_abs(path_abs)
              outZ(TXT_L, path, pos, color, msg, RST)
            else:
              outZ(color, text, RST)
          else:
            rst = color or RST
            outZ(color, text, rst)
          stdout.flush()
    else:
      c = runC(cmd)
    exit(c)


lexer = Lexer(
  patterns=dict(
    newline   = r'\n',
    top_step  = r'\[\d+/\d+\] .+',
    error     = r'[^:\n]+:\d+:\d+: error: .+',
    warning   = r'[^:\n]+:\d+:\d+: warning: .+',
    note      = r'[^:\n]+:\d+:\d+: note: .+',
    unknown_error   = '<unknown>:0: error: .+',
    unknown_warning = '<unknown>:0: warning: .+',
    underline = r'[ ]*[~^][~^ ]*',
    other     = r'.+',
))


def is_pair_group_head(token:Token) -> bool:
  return (token.kind in group_head_kinds)

group_head_kinds = { 'top_step', 'error', 'warning', 'unknown_error', 'unknown_warning', 'error_terminated' }


diag_re = re.compile(r'([^:]+)(:\d+:\d+: )(\w+: .+)')

diag_head_kinds = {'error', 'warning', 'unknown_error', 'unknown_warning'}
diag_kinds = {*diag_head_kinds, 'note'}


def key_by_splitting_ints(string:str) -> tuple[str|int,...]:
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
