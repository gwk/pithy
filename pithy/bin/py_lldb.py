#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import platform

from os import execv
from shlex import quote as sh_quote
from sys import argv, executable, stderr
from os.path import abspath as abs_path, join as path_join

def main() -> None:
  if len(argv) < 2: exit('usage: py-lldb [script] ...')
  if not executable: exit('py-lldb error: python executable path is not available.')
  exe = executable
  if platform.system() == 'Darwin':
    # Darwin's python3 binary is a wrapper that execs the actual binary.
    # Attempt to use this directly so that lldb debugs the real process.
    exe = abs_path(path_join(exe, '../../Resources/Python.app/Contents/MacOS/Python'))
  lldb = '/usr/bin/lldb'
  lldb_args = ['--batch', '--one-line', 'run', '--', exe, *argv[1:]]
  quoted = ' '.join(sh_quote(a) for a in [lldb, *lldb_args])
  print(f'py-lldb exec: {quoted}', file=stderr)
  execv(lldb, lldb_args)
