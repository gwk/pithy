#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import scandir
from sys import stderr

from pithy.cmdparse import Cmd, pos


def main() -> None:
  args = CheckCollisions.parse_or_exit()
  collisions:list[tuple[str,str]] = []
  for path in args.paths: check_dir(path, collisions)
  for module, directory in sorted(collisions):
    print(f'{module}: same-stem directory {directory}/ hides this module from mypy discovery; rename the directory.',
      file=stderr)
  if collisions: raise SystemExit(1)


class CheckCollisions(Cmd):
  'Check for Python modules hidden by same-stem directories during mypy discovery.'
  paths:list[str] = pos(doc='Source directories to check recursively.')


def check_dir(path:str, collisions:list[tuple[str,str]]) -> bool:
  'Collect collisions and return whether this directory contains discoverable Python sources.'
  with scandir(path) as entries:
    children = list(entries)
  dirs:dict[str,str] = {}
  modules:list[tuple[str,str]] = []
  for entry in children:
    if entry.name.startswith('.') or entry.name in ('__pycache__', 'site-packages', 'node_modules'): continue
    if entry.is_dir():
      if check_dir(entry.path, collisions): dirs[entry.name] = entry.path
    elif entry.name.endswith(('.py', '.pyi')):
      stem = entry.name.rsplit('.', 1)[0]
      modules.append((stem, entry.path))
  for stem, module in modules:
    if directory := dirs.get(stem): collisions.append((module, directory))
  return bool(dirs or modules)


if __name__ == '__main__': main()
