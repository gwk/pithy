# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from .lex import Lexer
from legs import ploy_repr, Source

def test_main() -> None:
  from sys import argv
  _, *args = argv
  for path in args:
    source = Source(name=path, text=open(path, 'rb').read())
    for token in Lexer(source=source):
      kind_desc = Lexer.pattern_descs[token.kind]
      text = source.bytes_for(token).decode()
      if token.kind == 'visible':
        print(source.diagnostic_for_token(token, msg=kind_desc))

