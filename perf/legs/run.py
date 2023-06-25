#!/usr/bin/env python3

from os import environ
from sys import argv
from typing import Any

from perf import Runner  # type: ignore
from pithy.io import errSL
from pithy.path import path_name


def main() -> None:
  # Runner invokes itself as a subprocess with '--worker --pipe'.
  # This makes specifying command line arguments tricky.
  #errSL('ARGV', argv)
  cmd = argv[1:]
  perf_args:list[str] = [argv[0]]
  for i, arg in enumerate(cmd):
    if arg.startswith('-'): # Beginning of perf args.
      perf_args.extend(cmd[i:])
      cmd = cmd[:i]
      break
  if not cmd:
    exit(f'error: no command specified; usage: run.py [CMD...] [PERF FLAGS...].')

  name = path_name(cmd[0])

  def add_cmdline_args(worker_cmds:list[str], args:Any) -> None:
    worker_cmds[2:2] = cmd
    #errSL('WORKER', worker_cmds)

  #errSL('CMD', cmd)
  #errSL('PERF', perf_args)
  argv[:] = perf_args
  r = Runner(program_args=perf_args, add_cmdline_args=add_cmdline_args)
  r.bench_command(name, cmd)

main()
