# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, Iterable, Iterator, List, TypeVar

from .default import Raise, RaiseOr


_T = TypeVar('_T')


class Buffer(Iterator[_T]):
  '''
  Iterable object that buffers an iterable.
  Call push() to push an item into the buffer;
  this will be returned on the subsequent call to __next__().
  '''


  def __init__(self, iterable: Iterable[_T]):
    self.iterator = iter(iterable)
    self.buffer: List[_T] = []


  def __repr__(self) -> str:
    return 'IterBuffer({!r}, buffer={!r})'.format(self.iterator, self.buffer)


  def __bool__(self) -> bool:
    try: self.peek()
    except StopIteration: return False
    else: return True


  def __iter__(self) -> Iterator[_T]: return self


  def __next__(self) -> _T:
    try: return self.buffer.pop()
    except IndexError: pass
    return next(self.iterator)


  def push(self, el:_T) -> None:
    self.buffer.append(el)


  def peek(self, default: RaiseOr[_T]=Raise._) -> _T:
    try: return self.buffer[-1]
    except IndexError: pass
    try: el = next(self.iterator)
    except StopIteration:
      if isinstance(default, Raise): raise
      else: return default
    self.buffer.append(el)
    return el


  def take_while(self, pred: Callable[[_T], bool]) -> Iterator[_T]:
    for el in self:
      if pred(el):
        yield el
      else:
        self.buffer.append(el)
        break


  def drop_while(self, pred: Callable[[_T], bool]) -> None:
    for el in self:
      if not pred(el):
        self.buffer.append(el)
        break


  def peek_while(self, pred: Callable[[_T], bool]) -> List[_T]:
    els = list(self.take_while(pred))
    self.buffer.extend(reversed(els))
    return els


  def take(self, count: int, short=False, default: RaiseOr[_T]=Raise._) -> List[_T]:
    els = []
    for _ in range(count):
      try: els.append(next(self))
      except StopIteration:
        if short: break
        if isinstance(default, Raise): raise
        els.append(default)
    return els


  def peeks(self, count: int, short=False, default: RaiseOr[_T]=Raise._) -> List[_T]:
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


  def peek_all(self) -> List[_T]:
    return self.peeks(count=1<<63, short=True)


  def expect(self, pred: Callable[[_T], bool]) -> _T:
    el = next(self)
    if pred(el): return el
    raise ValueError(el)
