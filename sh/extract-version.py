#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Extract a package version from source without importing the package.'

import ast
import re
import sys
from pathlib import Path


def main() -> None:
  if len(sys.argv) != 2 or re.fullmatch(r'[a-z][a-z0-9_]*', sys.argv[1]) is None:
    sys.exit(f'usage: {sys.argv[0]} package')
  package = sys.argv[1]
  path = Path(__file__).resolve().parent.parent / f'{package}_' / package / '__init__.py'
  try:
    tree = ast.parse(path.read_text(), filename=str(path))
    versions = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
      and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)]
    if len(versions) != 1 or not isinstance(versions[0], str) or not versions[0]:
      sys.exit(f'{path}: expected one literal string assignment to __version__.')
    print(versions[0])
  except (OSError, SyntaxError, ValueError) as e:
    sys.exit(f'{path}: {e}')


if __name__ == '__main__': main()
