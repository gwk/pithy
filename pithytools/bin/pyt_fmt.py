# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from sys import stdout

from pithy.loader import load


def main() -> None:
  parser = ArgumentParser(description='Format a Python template file.')
  parser.add_argument('template', help='the template file.')
  parser.add_argument('-args', required=True,
    help='path to a file containing argument data for the template. Supports all pithy.loader formats that return dictionaries.')
  parser.add_argument('-output', help='path to write the formatted output; defaults to stdout.')

  args = parser.parse_args()

  with open(args.template) as f:
    template_content = f.read()

  args_content = load(args.args)

  if not isinstance(args_content, dict):
    exit(f'pyt_fmt error: args file must contain a dictionary; received: {type(args_content).__name__}')

  formatted_content = template_content.format(**args_content)

  if args.output:
    with open(args.output, 'w') as f:
      f.write(formatted_content)
  else:
    stdout.write(formatted_content)
