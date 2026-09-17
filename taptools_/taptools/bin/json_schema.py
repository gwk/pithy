# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Produce a schema from input json.
'''

import json
from argparse import ArgumentParser
from sys import stderr, stdin, stdout

from pithy.fs import walk_files
from pithy.schema import compile_schema, write_schema


def main() -> None:
  parser = ArgumentParser(description='Count lines of source code.')
  parser.add_argument('-count-atoms', action='store_true')
  parser.add_argument('paths', nargs='*', default=['-'], help='Directories to explore.')
  args = parser.parse_args()

  schema = None
  for path in walk_files(*args.paths, file_exts=['.json']):
    with (stdin if path == '-' else open(path)) as f:
      try: j = json.load(f)
      except json.JSONDecodeError as e:
        print('error: {}: {}'.format(path, e), file=stderr)
        continue
      schema = compile_schema(j, schema=schema)

  write_schema(stdout, schema, count_atoms=args.count_atoms)


if __name__ == '__main__': main()
