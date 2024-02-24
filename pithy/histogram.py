# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter
from typing import ItemsView, Iterable, Iterator, Mapping


class Histogram(Mapping[float,int]):

  def __init__(self, iterable_or_mapping:Iterable[float]|Mapping[float,int]=(), *, bin_width:float):
    self.bin_width = bin_width
    self.counter = Counter[float]()
    self.update(iterable_or_mapping)


  def __getitem__(self, key:float) -> int:
    return self.counter[key]


  def __setitem__(self, key:float, value:int) -> None:
    if (key // self.bin_width) * self.bin_width != key: raise KeyError(key)
    self.counter[key] = value


  def __iter__(self) -> Iterator[float]:
    return iter(self.counter.keys())


  def __len__(self) -> int:
    return len(self.counter)


  def __repr__(self) -> str:
    items = ', '.join(f'{k!r}:{v!r}' for k, v in sorted(self.items()))
    return f'{self.__class__.__name__}({{{items}}}, bin_width={self.bin_width!r})'

  def update(self, iterable_or_mapping:Iterable[float]|Mapping[float,int]) -> None:
    if isinstance(iterable_or_mapping, Mapping):
      for x, count in iterable_or_mapping.items():
        self.increment(x, count)
    else:
      for x in iterable_or_mapping:
        self.increment(x)


  def increment(self, x:float, count=1) -> None:
    key = (x // self.bin_width) * self.bin_width
    self.counter[key] += count


  def key(self, x:float) -> float:
    return (x // self.bin_width) * self.bin_width


  def items(self) -> ItemsView[float,int]:
    return self.counter.items()
