# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


_raise = object()

class Buffer():
  '''
  Iterable object that buffers an iterable.
  Call push() to push an item into the buffer;
  this will be returned on the subsequent call to next().
  '''


  def __init__(self, iterable):
    self.iterator = iter(iterable)
    self.buffer = []


  def __repr__(self):
    return 'IterBuffer({!r}, buffer={!r})'.format(self.iterator, self.buffer)


  def __iter__(self): return self


  def __next__(self):
    try: return self.buffer.pop()
    except IndexError: pass
    return next(self.iterator)


  def push(self, item):
    self.buffer.append(item)


  def peek(self, default=_raise):
    try: return self.buffer[-1]
    except IndexError: pass
    try: el = next(self.iterator)
    except StopIteration:
      if default is _raise: raise
      else: return default
    self.buffer.append(el)
    return el


  def take_while(self, predicate):
    for el in self:
      if predicate(el):
        yield el
      else:
        self.buffer.append(el)
        break


  def drop_while(self, predicate):
    for el in self:
      if not predicate(el):
        self.buffer.append(el)
        break


  def peek_while(self, predicate):
    els = list(self.take_while(predicate))
    self.buffer.extend(reversed(els))
    return els


  def take(self, count, short=False, default=_raise):
    els = []
    for _ in range(count):
      try: els.append(next(self))
      except StopIteration:
        if short: break
        if default is _raise: raise
        els.append(default)
    return els


  def peeks(self, count, short=False, default=_raise):
    if 0 < count <= len(self.buffer):
      return reversed(self.buffer[-count:])
    els = []
    for _ in range(count):
      try: els.append(self.next())
      except StopIteration:
        if short: break
        if default is _raise: raise
        els.append(default)
    self.buffer.extend(reversed(els))
    return els


  @property
  def is_live(self):
    try: self.peek()
    except StopIteration: return False
    else: return True
