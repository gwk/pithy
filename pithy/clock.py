# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import stderr
from time import time as now
from typing import List, Tuple

from .typing import OptBaseExc, OptTraceback, OptTypeBaseExc


class Clock:

  def __init__(self, name:str) -> None:
    self.name = name
    self.times: List[Tuple[float, str]] = [(now(), 'start')]


  def __enter__(self) -> 'Clock': return self


  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> None:
    self.total()


  def split(self, label:str) -> None:
    t = now()
    print(f'clock: {self.name}: {label}: {t - self.times[-1][0]:.04f}', file=stderr)
    self.times.append((t, label))


  def total(self) -> None:
    t = now()
    print(f'clock: {self.name}: TOTAL: {t - self.times[0][0]:.04f}', file=stderr)
