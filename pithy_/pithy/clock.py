# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import stderr
from time import perf_counter as now
from typing import Self

from .typing_utils import OptBaseExc, OptTraceback, OptTypeBaseExc


class Clock:
  '''
  A simple ContextManager for timing code blocks.
  '''

  def __init__(self, name:str, quiet:bool=False) -> None:
    self.name = name
    self.quiet = quiet
    self.times:list[tuple[float,str]] = [(now(), 'start')]


  def __enter__(self) -> Self: return self


  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> None:
    self.total()


  def split(self, label:str) -> None:
    t = now()
    self.times.append((t, label))
    if not self.quiet:
      prev_time, prev_label = self.times[-2]
      print(f'clock: {self.name}: {prev_label} -> {label}: {t - prev_time:.04f}', file=stderr)


  def total(self) -> None:
    t = now()
    self.times.append((t, 'end'))
    if not self.quiet:
      print(f'clock: {self.name}: TOTAL: {t - self.times[0][0]:.04f}', file=stderr)


  def report(self) -> list[tuple[float,str]]:
    times = self.times
    rows = [(times[i][0] - times[i-1][0], f'{times[i-1][1]} -> {times[i][1]}') for i in range(1, len(times))]
    if self.times[-1][1] == 'end':
      rows.append((times[-1][0] - times[0][0], 'TOTAL'))
    return rows
