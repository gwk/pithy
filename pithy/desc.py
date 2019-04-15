# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Print indented object descriptions.
like `pprint` but streaming, and with a more compact, lisp-like style.
'''


import re
from itertools import count
from sys import stderr, stdout
from typing import Any, Iterable, Iterator, List, Mapping, NamedTuple, Optional, Set, TextIO, Tuple, Union

from .tree import known_leaf_types


def writeD(file:TextIO, *labels_and_obj:Any, indent='', commas=False) -> None:
  obj = labels_and_obj[-1]
  labels = labels_and_obj[:-1]
  if labels: print(*labels, end=': ', file=file)
  for part in gen_desc(obj, indent=indent, commas=commas):
    print(part, end='', file=file)
  print(file=file)


def errD(*labels_and_obj:Any, indent='', commas=False) -> None:
  writeD(stderr, *labels_and_obj, indent=indent, commas=commas)


def outD(*labels_and_obj:Any, indent='', commas=False) -> None:
  writeD(stdout, *labels_and_obj, indent=indent, commas=commas)


class _Desc(NamedTuple):
  opener:str
  closer:str
  it:Iterator # _DescEl
  buffer:List[str]

  def scan_inlineables(self) -> bool:
    for el in self.it:
      self.buffer.append(el)
      if not isinstance(el, str) or ',' in el: # Comma heuristic could be configurable.
        return False
    return True # Inlineable.

  def children(self) -> Iterable['_DescEl']:
    yield from self.buffer
    del self.buffer[:] # Makes the single-use semantics a bit more explicit, but not perfect.
    yield from self.it

_DescEl = Union[str,_Desc]



def gen_desc(obj:Any, indent:str='', commas=False) -> Iterator[str]:
  '''
  Generate description parts. Does not include final newline.
  '''
  yield from _gen_desc(_obj_desc(obj, prefix='', visited_ids=set()), indent=indent, commas=commas)


def _gen_desc(d:_DescEl, indent:str, commas:bool) -> Iterator[str]:
  '''
  Generate description parts. Does not include final newline.
  '''
  if indent: yield indent

  if isinstance(d, str):
    yield d
    return

  yield d.opener

  if d.scan_inlineables(): # Inlineable.
    if d.buffer: # Nonempty.
      yield ' '
      comma_joiner = ', ' if commas else ' '
      yield comma_joiner.join(d.buffer)
      yield ' '

  else: # Not inlineable.
    indent1 = indent + '  '
    is_leaf = False
    for i, el in enumerate(d.children()):
      yield ',\n' if (commas and i) else '\n'
      is_leaf = isinstance(el, str)
      if is_leaf:
        yield indent1
        yield el # type: ignore
      else:
        yield from _gen_desc(el, indent1, commas)
    if is_leaf: yield ' ' # Final space before closer.

  yield d.closer


def _obj_desc(obj:Any, prefix:str, visited_ids:Set[int]) -> _DescEl:
  if isinstance(obj, known_leaf_types):
    return prefix + repr(obj)

  i = id(obj)
  if i in visited_ids:
    return f'^0x{i:x}:{type(obj).__name__}'

  # Most objects in a tree are leaves; we minimize tests for the leaf case by nesting the mapping test inside the iter test.
  # This has the debatable side effect of ignoring non-iterable classes that have an items() function.

  # Use an explicit test for __iter__ because iter() will return for objects without __iter__ but with __getitem__;
  # this includes typing._SpecialForm, which fails when we attempt to iterate.
  if hasattr(obj, '__iter__'):
    try: it = iter(obj)
    except TypeError: pass
    else:
      visited_ids1 = visited_ids.copy()
      visited_ids1.add(i)
      # Attempt to distinguish between mapping and sequence types.
      try: items = iter(obj.items()) # Wrapping `iter` guards against badly formed items() functions.
      except (AttributeError, TypeError): # Treat as iterable.
        return _iterable_desc(obj, prefix, visited_ids1, iter(obj))
      else: # Treat as a mapping.
        return _mapping_desc(obj, prefix, visited_ids1, items)

  return prefix + repr(obj)


def _iterable_desc(obj:Any, prefix:str, visited_ids:Set[int], it:Iterator) -> _Desc:
  t = type(obj)
  if t is tuple:
    opener = '('
    closer = ',)' if len(obj) == 1 else ')'
  elif t is list:
    opener = '['
    closer = ']'
  elif t is set:
    if obj:
      opener = '{'
      closer = '}'
    else:
      opener = 'set('
      closer = ')'
  else:
    opener = t.__qualname__ + '(['
    closer = '])'

  it = (_obj_desc(el, prefix='', visited_ids=visited_ids) for el in it)
  return _Desc(opener=prefix+opener, closer=closer, it=it, buffer=[])


_Items = Iterator[Tuple[Any,Any]]


def _mapping_desc(obj:Mapping, prefix:str, visited_ids:Set[int], items:_Items) -> _Desc:
  t = type(obj)
  if t is dict:
    opener = '{'
    closer = '}'
  else:
    opener = t.__qualname__ + '({'
    closer = '})'

  it = _gen_item_descs(items, key_joiner=':', visited_ids=visited_ids)
  return _Desc(opener=prefix+opener, closer=closer, it=it, buffer=[])


def _gen_item_descs(items:_Items, key_joiner:str, visited_ids:Set[int]) -> Iterator[_DescEl]:
  for pair in items:
    try: k, v = pair
    except (TypeError, ValueError): # Guard against a weird items() iterator.
      yield f'! {pair!r}'
      continue
    yield _obj_desc(v, prefix=f'{k!r}{key_joiner}', visited_ids=visited_ids)


def repr_clean(obj:Any) -> str:
  '''
  Attempt to ensure that an object gets printed with a decent repr.
  Some third-party libraries print unconventional reprs that are confusing inside of collection descriptions.
  '''
  r = repr(obj)
  if type(obj) in _literal_repr_types or _decent_repr_re.fullmatch(r): return r
  return f'{type(obj).__name__}({r})'

_literal_repr_types = { bytes,str,list,dict,set,tuple }
_decent_repr_re = re.compile(r'[a-zA-Z][.\w]*\(.*\)')


def repr_lim(obj:Any, limit=64) -> str:
  r = repr(obj)
  if len(r) <= limit: return r
  return r[:limit-1] + '…'
