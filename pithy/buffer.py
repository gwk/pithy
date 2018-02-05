# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, Generic, Iterable, Iterator, List, TypeVar, Union
from .default import Raise, RaiseOr


T = TypeVar('T')


class Buffer(Iterator[T]):
  '''
  Iterable object that buffers an iterable.
  Call push() to push an item into the buffer;
  this will be returned on the subsequent call to next().
  '''


  def __init__(self, iterable: Iterable[T]) -> None:
    self.iterator = iter(iterable)
    self.buffer: List[T] = []


  def __repr__(self) -> str:
    return 'IterBuffer({!r}, buffer={!r})'.format(self.iterator, self.buffer)


  def __iter__(self) -> Iterator[T]: return self


  def __next__(self) -> T:
    try: return self.buffer.pop()
    except IndexError: pass
    return next(self.iterator)


  @property
  def is_live(self) -> bool:
    try: self.peek()
    except StopIteration: return False
    else: return True


  def push(self, item: T) -> None:
    self.buffer.append(item)


  def peek(self, default: RaiseOr[T]=Raise._) -> T:
    try: return self.buffer[-1]
    except IndexError: pass
    try: el = next(self.iterator)
    except StopIteration:
      if isinstance(default, Raise): raise
      else: return default
    self.buffer.append(el)
    return el


  def take_while(self, pred: Callable[[T], bool]) -> Iterator[T]:
    for el in self:
      if pred(el):
        yield el
      else:
        self.buffer.append(el)
        break


  def drop_while(self, pred: Callable[[T], bool]) -> None:
    for el in self:
      if not pred(el):
        self.buffer.append(el)
        break


  def peek_while(self, pred: Callable[[T], bool]) -> List[T]:
    els = list(self.take_while(pred))
    self.buffer.extend(reversed(els))
    return els


  def take(self, count: int, short=False, default: RaiseOr[T]=Raise._) -> List[T]:
    els = []
    for _ in range(count):
      try: els.append(next(self))
      except StopIteration:
        if short: break
        if isinstance(default, Raise): raise
        els.append(default)
    return els


  def peeks(self, count: int, short=False, default: RaiseOr[T]=Raise._) -> List[T]:
    if 0 < count <= len(self.buffer):
      return list(reversed(self.buffer[-count:]))
    els = []
    for _ in range(count):
      try: els.append(next(self))
      except StopIteration:
        if short: break
        if isinstance(default, Raise): raise
        els.append(default)
    self.buffer.extend(reversed(els))
    return els


  def expect(self, pred: Callable[[T], bool]) -> T:
    el = next(self)
    if pred(el): return el
    raise ValueError(el)
