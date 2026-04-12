# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from statistics import fmean, median, stdev, variance
from typing import Sequence


@dataclass(frozen=True)
class BasicStats:
  count:int
  min:float
  max:float
  mean:float
  median:float
  variance:float
  std_dev:float

  def __str__(self) -> str:
    return f'count: {self.count};  min: {self.min:.4f};  max: {self.max:4f};  mean: {self.mean:.4f};  median: {self.median:.4f};' \
      f'variance: {self.variance:.4f};  std_dev: {self.std_dev:.4f}'


def basic_stats(values:Sequence[float]) -> BasicStats:
  c = len(values)
  return BasicStats(
    count=c,
    min=min(values) if c > 0 else 0,
    max=max(values) if c > 0 else 0,
    mean=fmean(values) if c > 0 else 0.0,
    median=median(values) if c > 0 else 0.0,
    variance=variance(values) if c > 1 else 0.0,
    std_dev=stdev(values) if c > 1 else 0.0)
