#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from os import environ, getcwd

from pithy.fs import make_dirs, walk_files
from pithy.path import path_rel_to_dir
from pithy.task import runC


def main() -> None:
  arg_parser = ArgumentParser(description='Find and run utest unit tests with the extension ".ut.py", defaulting to  "test/".')
  arg_parser.add_argument('paths', nargs='*', default=['test'])
  args = arg_parser.parse_args()
  paths = walk_files(*args.paths, file_exts='.ut.py')

  env = dict(environ)
  env.setdefault('UTEST_WORK_DIR', getcwd())

  utest_cwd = '_build/_utest'
  make_dirs(utest_cwd)
  ok = True
  for path in paths:
    print(path)
    exe_path = path_rel_to_dir(path, utest_cwd)
    c = runC(['python3', exe_path], cwd=utest_cwd, env=env)
    if c != 0:
      ok = False
      print()

  exit(0 if ok else 1)


if __name__ == '__main__': main()
