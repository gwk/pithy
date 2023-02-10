# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from . import parse_eon, ParseError


def main() -> None:
  '''
  Parse specified files (or stdin) as EON and print each result.'
  '''
  from sys import argv

  from ..io import outD

  args = argv[1:] or ['/dev/stdin']
  for path in args:
    with open(path) as f:
      text = f.read()
    try: obj = parse_eon(path, text, to=object)
    except ParseError as e: e.fail()
    outD(path, obj)


if __name__ == '__main__': main()
