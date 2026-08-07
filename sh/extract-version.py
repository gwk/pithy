#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Extract a package version from source without importing the package.
A package that builds a Rust extension takes its version from `Cargo.toml`, which is where maturin reads it;
the version must be written so that it is also a normalized Python version, because it appears in the distribution file names.
A pure Python package takes it from `__version__` in the package `__init__.py`, which is where flit reads it.
'''

import ast
import re
import sys
from pathlib import Path
from tomllib import load as load_toml, TOMLDecodeError


def main() -> None:
  if len(sys.argv) != 2 or re.fullmatch(r'[a-z][a-z0-9_]*', sys.argv[1]) is None:
    sys.exit(f'usage: {sys.argv[0]} package')
  package = sys.argv[1]
  package_dir = Path(__file__).resolve().parent.parent / f'{package}_'
  cargo_path = package_dir / 'Cargo.toml'
  if cargo_path.exists(): print(cargo_version(cargo_path))
  else: print(init_version(package_dir / package / '__init__.py'))


def cargo_version(path:Path) -> str:
  try:
    with path.open('rb') as f: version = load_toml(f).get('package', {}).get('version')
  except (OSError, TOMLDecodeError) as e:
    sys.exit(f'{path}: {e}')
  if not isinstance(version, str) or not version:
    sys.exit(f'{path}: expected a literal string `package.version`.')
  return version


def init_version(path:Path) -> str:
  try:
    tree = ast.parse(path.read_text(), filename=str(path))
    versions = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
      and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)]
    if len(versions) != 1 or not isinstance(versions[0], str) or not versions[0]:
      sys.exit(f'{path}: expected one literal string assignment to __version__.')
    return versions[0]
  except (OSError, SyntaxError, ValueError) as e:
    sys.exit(f'{path}: {e}')


if __name__ == '__main__': main()
