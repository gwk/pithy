# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.ansi import *
from pithy.io import *
from pithy.lex import Lexer
from pithy.task import runCO
from argparse import ArgumentParser


def main() -> None:
  arg_parser = ArgumentParser(description='Run mypy, format and colorize output.')
  arg_parser.add_argument('-print-ok', action='store_true')
  arg_parser.add_argument('roots', nargs='+')
  args = arg_parser.parse_args()

  c, o = runCO(['mypy', *args.roots])
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
  location  = r'[^:\n]+:\d+:(\d+:)?',
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
