# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from sys import stdin, stdout

from pithy.json.fmt import write_formatted_json_bytes


def main() -> None:
  parser = ArgumentParser(description='Format JSON input.')
  parser.add_argument('paths', nargs='*', default=['-'], help='input file paths; defaults to stdin.')
  parser.add_argument('-fix', action='store_true', help='fix malformed JSON (missing/extra commas; comments).')
  parser.add_argument('-trailing-commas', action='store_true', help='allow trailing commas in fixed output.')
  parser.add_argument('-comments', action='store_true', help='preserve comments instead of stripping them.')
  args = parser.parse_args()

  out_raw = stdout.buffer
  for path in args.paths:
    f = stdin.buffer if path == '-' else open(path, 'rb')
    with f:
      write_formatted_json_bytes(out_raw, f, fix=args.fix, allow_trailing_commas=args.trailing_commas,
        allow_comments=args.comments)


if __name__ == '__main__': main()
