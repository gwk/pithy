# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import argv, stderr, stdin


def main() -> None:
  args = argv[1:] or list(stdin)
  number_strings = [a.replace(',', '_') for arg in args for a in arg.split()]
  print(number_strings, file=stderr)
  try: total = sum(float(s) for s in number_strings)
  except ValueError as e: exit(f'sum error: {e}')
  print(total)
