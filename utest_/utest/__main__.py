#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from os import environ, getcwd
from time import perf_counter

from pithy.fs import make_dirs, path_rel_to_dir, walk_files
from pithy.task import runC


def main() -> None:
  arg_parser = ArgumentParser(description='Find and run utest unit tests with the extension ".ut.py", defaulting to  "test/".')
  arg_parser.add_argument('paths', nargs='*', default=['test'])
  args = arg_parser.parse_args()
  paths = list(walk_files(*args.paths, file_exts='.ut.py'))
  path_width = max(map(len, paths), default=0) + 2

  env = dict(environ)
  env.setdefault('UTEST_WORK_DIR', getcwd())

  utest_cwd = '_build/_utest'
  make_dirs(utest_cwd)
  ok = True

  for path in paths:
    exe_path = path_rel_to_dir(path, utest_cwd)
    start_time = perf_counter()
    c = runC(['python3', '-P', exe_path], cwd=utest_cwd, env=env)
    elapsed = perf_counter() - start_time
    print(f'{path:{path_width}}{elapsed:.2f} sec.', flush=True)
    if c != 0:
      ok = False
      print()

  exit(0 if ok else 1)


if __name__ == '__main__': main()
