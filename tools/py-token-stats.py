#!/usr/bin/env python3

from math import ceil, log10
from sys import argv
from typing import Counter

from pithy.io import *
from pithy.lex import Lexer
from pithy.py.lex import lexer
from tolkien import Source, Token


def main() -> None:
  counter = Counter[str]()
  kinds = sorted(lexer.patterns)
  for kind in kinds:
    counter[kind] = 0

  for path in argv[1:]:
    count_tokens(path, counter)

  wk = max(len(k) for k in kinds)
  wc = max(ceil(log10(c or 1)) for c in counter.values())
  wc += wc // 3
  for kind, count in counter.most_common():
    errL(f'{kind:<{wk}} {count:>{wc},}')


def count_tokens(path:str, counter:Counter[str]) -> None:
  source = Source(path, open(path).read())
  for token in lexer.lex(source):
    counter[token.kind] += 1
    #print(source.diagnostic(token, msg=token.kind))
    if token.kind == 'invalid':
      source.fail((token, 'invalid token'))

main()
