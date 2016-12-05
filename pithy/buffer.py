# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, Generic, Iterable, Iterator, List, TypeVar, Union

from .sentinel import Sentinel


T = TypeVar('T')


class Buffer(Generic[T], Iterator[T]):
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


  def push(self, item: T) -> None:
    self.buffer.append(item)


  def peek(self, default: Union[T, Sentinel]=Sentinel()) -> T:
    try: return self.buffer[-1]
    except IndexError: pass
    try: el = next(self.iterator)
    except StopIteration:
      if isinstance(default, Sentinel): raise
      else: return default
    self.buffer.append(el)
    return el


  def take_while(self, predicate: Callable[[T], bool]) -> Iterator[T]:
    for el in self:
      if predicate(el):
        yield el
      else:
        self.buffer.append(el)
        break


  def drop_while(self, predicate: Callable[[T], bool]) -> None:
    for el in self:
      if not predicate(el):
        self.buffer.append(el)
        break


  def peek_while(self, predicate: Callable[[T], bool]) -> List[T]:
    els = list(self.take_while(predicate))
    self.buffer.extend(reversed(els))
    return els


  def take(self, count, short=False, default: Union[T, Sentinel]=Sentinel()) -> List[T]:
    els = []
    for _ in range(count):
      try: els.append(next(self))
      except StopIteration:
        if short: break
        if isinstance(default, Sentinel): raise
        els.append(default)
    return els


  def peeks(self, count: int, short=False, default: Union[T, Sentinel]=Sentinel()) -> List[T]:
    if 0 < count <= len(self.buffer):
      return list(reversed(self.buffer[-count:]))
    els = []
    for _ in range(count):
      try: els.append(next(self))
      except StopIteration:
        if short: break
        if isinstance(default, Sentinel): raise
        els.append(default)
    self.buffer.extend(reversed(els))
    return els


  @property
  def is_live(self) -> bool:
    try: self.peek()
    except StopIteration: return False
    else: return True
