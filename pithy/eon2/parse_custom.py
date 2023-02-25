# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from typing import Any

from tolkien import Source, Token

from ..buffer import Buffer


class ParseError(Exception): pass


@dataclass
class Parser:
  source: Source
  tokens: list[Token]
  buffer: Buffer[Token]

  def error(self, token:Token, msg:str) -> ParseError:
    return ParseError(self.source.diagnostic_for_syntax(token, msg))

  def parse_head(self) -> Any:
    pass

  def parse_inline(self) -> Any:
    pass

  def parse_key(self) -> Any:
    pass


  def parse_one(self, source: Source, tokens:list[Token], idx:int, depth:int) -> Any:
    token = tokens[idx]
    if depth == 0:
      if token.kind == 'space': raise self.error(token, 'unexpected indent.')
    else:
      assert depth > 0
      if token.kind != 'space': raise self.error(token, f'expected indentation to depth {depth}.')

    while idx < len(tokens):
      pass


  def parse(self) -> Any:
    pass

def main() -> None:
  '''
  Parse specified files (or stdin) as EON and print each result.'
  '''
  from sys import argv

  from ..io import outD
  from .lex import lexer

  args = argv[1:] or ['/dev/stdin']
  for path in args:
    with open(path) as f:
      text = f.read()

    source = Source(name=path, text=text)
    tokens = list(lexer.lex(source=source))
    parser = Parser(source=source, tokens=tokens, buffer=Buffer(tokens))
    try: obj = parser.parse()
    except ParseError as e: exit(e)
    outD(path, obj)


if __name__ == '__main__': main()
