# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import stderr
from time import time as now


class Clock:
  def __init__(self, name:str):
    self.name = name
    self.times = [(now(), 'start')]

  def split(self, label:str):
    t = now()
    print(f'clock: {self.name}: {label}: {t - self.times[-1][0]:.04f}', file=stderr)
    self.times.append((t, label))


  def total(self):
    t = now()
    print(f'clock: {self.name}: TOTAL: {t - self.times[0][0]:.04f}', file=stderr)
