#!/usr/bin/env python3

from math import sqrt
from sys import argv
from time import perf_counter
from typing import List

from pithy.task import communicate, DEVNULL, launch


def main() -> None:
  if len(argv) < 3: exit(f'error: usage: time-runs NUM_RUNS CMD ...')

  _, num_runs_str, *cmd = argv
  try: num_runs = int(num_runs_str)
  except ValueError: exit(f'error: first argument must be an integer; received {argv[1]!r}.')
  if num_runs < 1: exit(f'error: first argument must be positive: received {num_runs}.')

  tot_times:List[float] = []
  wait_times:List[float] = []
  for i in range(num_runs):
    pre_launch_time = perf_counter()
    _cmd, proc, _input = launch(cmd, err=DEVNULL, out=DEVNULL)
    post_launch_time = perf_counter()
    status, _, _ = communicate(proc)
    end_time = perf_counter()
    tot_time = end_time - pre_launch_time
    wait_time = end_time - post_launch_time
    tot_times.append(tot_time)
    wait_times.append(wait_time)
    print(f'{i:3d}: total: {tot_time:8.3f}; wait: {wait_time:8.3f}; exit status: {status}.')

  calc_stats(tot_times, label='total')
  calc_stats(wait_times, label='wait')


def calc_stats(times:List[float], label:str) -> None:
  l = len(times)
  avg = sum(times) / l
  std_dev = sqrt(sum((t-avg)**2 for t in times))
  print(f'{label:5}: avg: {avg:7.3f}; std-dev: {std_dev:6.3f}.')
