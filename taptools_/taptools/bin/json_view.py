# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
View json or jsonl input as a human-readable indented tree.

Reads one or more json or jsonl files (or stdin if no paths are given) and renders each using `pithy.datatree.render_datatree`.
When multiple files are provided, each file's output is prefixed with a blank line and a `{path}:` header.
For jsonl input, a blank line separates each rendered item.
'''

from argparse import ArgumentParser
from sys import stdin

from pithy.datatree import render_datatree
from pithy.json import load_json, load_jsonl


def main() -> None:
  parser = ArgumentParser(description='View json or jsonl input as a human-readable indented tree.')
  parser.add_argument('paths', nargs='*', default=['-'], help='Input file paths; defaults to stdin.')
  args = parser.parse_args()

  paths:list[str] = args.paths or ['-']
  multi = len(paths) > 1

  for path in paths:
    is_stdin = (path == '-')
    is_jsonl = is_stdin or path.endswith('.jsonl')
    if multi:
      print(f'\n{path}:')
    f = stdin if is_stdin else open(path)
    with f:
      if is_jsonl:
        for idx, item in enumerate(load_jsonl(f)):
          if idx: print()
          print(render_datatree(item), end='')
      else:
        print(render_datatree(load_json(f)), end='')


if __name__ == '__main__': main()
