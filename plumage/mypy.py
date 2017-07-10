#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.lex import *
from pithy.ansi import *
from pithy.io import *
from pithy.task import runCO
from sys import stdin


def main():
  c, o = runCO(['mypy', *argv[1:]])
  for token in lexer.lex(o):
    color = colors[token.lastgroup]
    outZ(color, token[0], RST)


lexer = Lexer(invalid='invalid', patterns=dict(
  newline = r'\n',
  path    = r'[^:\n]+:\d+:(\d+:)?',
  error   = r'error:',
  warning = r'warning:',
  note    = r'note:',
  quoteD  = r'"[^"]*"',
  quoteS  = r"'[^']*'",
  text    = r'.+?',
))

colors = {
  'invalid' : INVERT,
  'newline' : '',
  'path'    : TXT_L,
  'error'   : TXT_R,
  'warning' : TXT_Y,
  'note'    : TXT_L,
  'quoteD'  : TXT_C,
  'quoteS'  : TXT_C,
  'text'    : '',
}

if __name__ == '__main__': main()
