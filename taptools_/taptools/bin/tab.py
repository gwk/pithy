# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from sys import stdin, stdout

from pithy.io import write_rows
from pithy.tsv import parse_tsv


def main() -> None:

  parser = ArgumentParser(description='Format TSV, CSV, or other tabular data to aligned columns.')
  parser.add_argument('path', nargs='?', default='-', help='Input file path, or - for stdin. (default: -)')
  parser.add_argument('-max-col-width', type=int, default=64, help='Maximum column width. (default: 64)')
  args = parser.parse_args()

  if args.path == '-':
    f = stdin
  else:
    f = open(args.path)
  with f:
    write_rows(stdout, parse_tsv(f, has_header=False), max_col_width=args.max_col_width)
