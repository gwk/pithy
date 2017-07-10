#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.lex import *
from pithy.ansi import *
from pithy.io import *
from sys import stdin


def main():
  while True:
    line = stdin.readline()
    if not line: break
    for token in lexer.lex(line):
      color = colors.get(token.lastgroup, '')
      outZ(color, token[0], RST)
      stdout.flush()


patterns=dict(
  newline   = r'\n',
  compile   = r'Compile Swift Module .+',
  linking   = r'Linking .+',
  path      = r'[^:]+:\d+:\d+: ',
  error     = r'error: .+',
  warning   = r'warning: .+',
  note      = r'note: .+',
  hint      = r'.+',
  underline = r'[ ]*[~^][~^ ]*',
  line      = r'.+',
)

colors = {
  'invalid'   : INVERT,
  'compile'   : TXT_M,
  'linking'   : TXT_M,
  'path'      : TXT_L,
  #'line_col'  : TXT_C, # disabled because VSCode cannot parse paths with ANSI codes splitting path from line/col.
  'error'     : TXT_R,
  'warning'   : TXT_Y,
  'note'      : TXT_L,
  'hint'      : TXT_G,
  'line'      : '',
  'underline' : TXT_B,
}


lexer = Lexer(invalid='invalid', patterns=patterns,
  modes=dict(
    main={
      'newline',
      'compile',
      'linking',
      'path',
      #'line_col',
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


if __name__ == '__main__': main()
