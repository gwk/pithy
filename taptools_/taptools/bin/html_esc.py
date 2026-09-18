# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from html import escape
from sys import argv


def main() -> None:
  for arg in argv[1:]:
    print(escape(arg, quote=True))


if __name__ == '__main__': main()
