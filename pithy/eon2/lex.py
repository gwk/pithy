# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..lex import Lexer, LexMode, LexTrans


'''
The default Eon language lexer.
Eon is designed to accommodate different lexers, but that feature has yet to be implemented.
'''

lexer = Lexer(flags='mx',
  patterns=dict(
    newline = r'\n',
    spaced_eq = r'\ +=(?:\ +|(?=\n))',
    spaces  = r'\ +',
    comment = r'//[^\n]*\n',

    section = r'^\#+',

    sym = r'[A-Za-z_][0-9A-Za-z_\-\./]*',
    flt = r'[0-9]+\.[0-9]+',
    int = r'[0-9]+',

    eq = r'=',
    dash = r'-',
    brace_o = r'\{',
    brace_c = r'\}',
    brack_o = r'\[',
    brack_c = r'\]',
    paren_o = r'\(',
    paren_c = r'\)',
    dq = r'"',
    sq = r"'",


    esc_char=r'\\[n\\"\']',
    chars_dq=r'[^\n\\"]+',
    chars_sq=r"[^\n\\']+",

    other = r'[!-~]+',
  ),
  modes=[
    LexMode('main',
      kinds=[
        'newline', 'spaces', 'comment',
        'spaced_eq',
        'section', 'sym', 'flt', 'int', 'eq', 'dash',
        'brace_o', 'brace_c', 'brack_o', 'brack_c', 'paren_o', 'paren_c',
        'dq', 'sq', 'other'],
      indents=True),
    LexMode('string_dq', kinds=['chars_dq', 'esc_char', 'dq']),
    LexMode('string_sq', kinds=['chars_sq', 'esc_char', 'sq']),
  ],
  transitions=[
    LexTrans('main', kind='dq', mode='string_dq', pop='dq', consume=True),
    LexTrans('main', kind='sq', mode='string_sq', pop='sq', consume=True),
  ],
)




def main() -> None:
  '''
  Parse specified files (or stdin) as EON and print each result.'
  '''
  from sys import argv

  from tolkien import Source

  from ..ansi import RST, TXT_R

  args = argv[1:] or ['/dev/stdin']
  for path in args:
    with open(path) as f:
      text = f.read()
    source = Source(name=path, text=text)
    for token in lexer.lex(source):
      if token.kind == 'invalid':
        color, rst = (TXT_R, RST)
      else:
        color, rst = ('', '')
      print(f'{color}{token}: {source[token]!r}{rst}')


if __name__ == '__main__': main()
