#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.ansi import *
from pithy.io import *
from pithy.fs import path_rel_to_current_or_abs
from pithy.iterable import group_by_heads
from pithy.lex import Lexer
from sys import stdin


def main():
    for token in lex_groups():
      if token.lastgroup == 'path':
        s = path_rel_to_current_or_abs(token[0])
      else:
        s = token[0]
      try: color = colors[token.lastgroup]
      except KeyError: outZ(s)
      else: outZ(color, s, RST)
      stdout.flush()


def lex_groups():
  it = lexer.lex_stream(read_stdin_lines())
  for token in it:
    yield token
    if is_token_head(token): break

  group = []

  for token in it:
    if is_token_head(token):
      yield from group
      del group[:]
      yield token
    else:
      group.append(token)
  yield from group


def read_stdin_lines():
  '''
  Read stdin iteratively using readline.
  This reads incrementally when stdin is connected to a pipe,
  whereas using the file's iterator blocks.
  '''
  while True:
    line = stdin.readline()
    if not line: return
    yield line


def is_token_head(token) -> bool:
  return token.lastgroup in head_tokens


head_tokens = {'compile', 'linking', 'error_terminated', 'path'}


lexer = Lexer(invalid='invalid',
  patterns=dict(
    newline   = r'\n',
    compile   = r'Compile Swift Module .+',
    linking   = r'Linking .+',
    error_terminated = r'error: terminated.+',
    path      = r'[^:]+:\d+:\d+: ', # note: do not highlight line/col separately; VSCode will not recognize the paths.
    error     = r'error: .+',
    warning   = r'warning: .+',
    note      = r'note: .+',
    hint      = r'.+',
    underline = r'[ ]*[~^][~^ ]*',
    line      = r'.+',
  ),
  modes=dict(
    main={
      'newline',
      'compile',
      'linking',
      'error_terminated',
      'path',
      'error',
      'warning',
      'note',
      'hint',
    },
    code={
      'newline',
      'line',
      'underline'
    },
  ),
  transitions={
    ('main', 'error')   : ('code', 'underline'),
    ('main', 'warning') : ('code', 'underline'),
    ('main', 'note')    : ('code', 'underline'),
  })


colors = {
  'invalid'   : INVERT,
  'compile'   : TXT_M,
  'linking'   : TXT_M,
  'error_terminated' : TXT_D,
  'path'      : TXT_L,
  #'line_col'  : TXT_C, # disabled
  'error'     : TXT_R,
  'warning'   : TXT_Y,
  'note'      : TXT_L,
  'hint'      : TXT_G,
  'underline' : TXT_B,
}


if __name__ == '__main__': main()
