# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import argv
from typing import Counter
from legs import Source


def main() -> None:
  counts = Counter[str]()
  for i, path in enumerate(argv):
    if i == 0: continue
    parse(path, counts)

  for (kind, count) in sorted(counts.items()):
    print(f'{kind}: {count}')


def parse(path:str, counts:Counter[str]) -> None:
  text = open(path, 'rb').read()
  source = Source(name=path, text=text)
  for token in Lexer(source=source):
    counts[token.kind] += 1
    if token.kind == 'invalid':
      print(source.diagnostic(token, msg='invalid'))


if __name__ == '__main__': main()
