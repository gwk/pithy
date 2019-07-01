# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Print indented object descriptions.
like `pprint` but streaming, and with a more compact, minimal style.
'''


import re
from itertools import count
from dataclasses import fields as _dc_fields, is_dataclass
from sys import stderr, stdout
from typing import Any, Iterable, Iterator, List, Mapping, NamedTuple, Optional, Set, TextIO, Tuple, Union

from .iterable import known_leaf_types


# Special handling for annoying types that show up in Python scopes.
_Printer = type(copyright)
_Quitter = type(quit) # Also the type of `exit`.
_BadRepr = (_Printer, _Quitter)


def writeD(file:TextIO, *labels_and_obj:Any, indent='', exact=False) -> None:
  'Write a description to a file.'
  obj = labels_and_obj[-1]
  labels = labels_and_obj[:-1]
  if labels: print(*labels, end=': ', file=file)
  for part in gen_desc(obj, indent=indent, exact=exact):
    print(part, end='', file=file)
  print(file=file)


def errD(*labels_and_obj:Any, indent='', exact=False) -> None:
  'Write a description to `stderr`.'
  writeD(stderr, *labels_and_obj, indent=indent, exact=exact)


def outD(*labels_and_obj:Any, indent='', exact=False) -> None:
  'Write a description to `stdout`.'
  writeD(stdout, *labels_and_obj, indent=indent, exact=exact)


_DescEl = Union[str,'_Desc']

class _Desc(NamedTuple):
  'Temporary description object.'
  opener:str # Opening character, e.g. '('.
  closer:str # Closing character, e.g. ')'.
  it:Iterator # TODO: when mypy supports recursive types, fully annotate with `['_DescEl']`.
  buffer:List[str] # Holds leading elements obtained from `it`.

  def scan_inlineables(self, max_width:int) -> bool:
    'Determine if this description can be rendered inline.'
    width = 0
    for el in self.it:
      self.buffer.append(el)
      if not isinstance(el, str) or ',' in el: # Comma heuristic could be configurable.
        return False
      width += len(el)
      if width > max_width: return False
    return True # Inlineable.

  def children(self) -> Iterable[_DescEl]:
    yield from self.buffer
    del self.buffer[:] # Makes the single-use semantics a bit more explicit, but not perfect.
    yield from self.it


def gen_desc(obj:Any, indent:str='', exact=False) -> Iterator[str]:
  '''
  Generate description parts. Does not include final newline.
  '''
  yield from _gen_desc(_obj_desc(obj, prefix='', visited_ids=set(), simple_keys=(not exact)), indent=indent, exact=exact)


def _gen_desc(d:_DescEl, indent:str, exact:bool) -> Iterator[str]:
  '''
  Generate description parts. Does not include final newline.
  '''
  if indent: yield indent

  if isinstance(d, str):
    yield d
    return

  yield d.opener

  if d.scan_inlineables(max_width=128): # Inlineable.
    if d.buffer: # Nonempty.
      yield ' '
      comma_joiner = ', ' if exact else ' '
      yield comma_joiner.join(d.buffer)
      yield ' '

  else: # Not inlineable.
    indent1 = indent + '  '
    is_leaf = False
    is_subsequent = False
    for el in d.children():
      yield ',\n' if (exact and is_subsequent) else '\n'
      is_subsequent = True
      is_leaf = isinstance(el, str)
      if is_leaf:
        yield indent1
        yield el # type: ignore
      else:
        yield from _gen_desc(el, indent1, exact)
    if is_leaf: yield ' ' # Final space before closer.

  yield d.closer


def _obj_desc(obj:Any, prefix:str, visited_ids:Set[int], simple_keys:bool) -> _DescEl:
  '''
  Main description generator function. This dispatches out to others using various criteria.
  '''

  if isinstance(obj, known_leaf_types):
    return prefix + repr(obj)

  i = id(obj)
  if i in visited_ids:
    return f'^0x{i:x}:{type(obj).__name__}'

  # TODO: add singledispatch override here?

  if is_dataclass(obj):
    visited_ids1 = visited_ids.copy()
    visited_ids1.add(i)
    items:_Items = ((f.name, getattr(obj, f.name)) for f in _dc_fields(obj))
    return _record_desc(obj, prefix, visited_ids1, items, simple_keys)

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
      try: items = iter(obj.items()) # The outer call to `iter` guards against badly formed items() functions.
      except (AttributeError, TypeError): # Treat as iterable.
        return _iterable_desc(obj, prefix, visited_ids1, iter(obj), simple_keys)
      else: # Treat as a mapping.
        return _mapping_desc(obj, prefix, visited_ids1, items, simple_keys)

  if isinstance(obj, _BadRepr):
    return f'{prefix}{type(obj).__name__}<{repr(obj)!r}>'
  return prefix + repr(obj)


def _iterable_desc(obj:Any, prefix:str, visited_ids:Set[int], it:Iterator, simple_keys:bool) -> _Desc:
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

  it = (_obj_desc(el, prefix='', visited_ids=visited_ids, simple_keys=simple_keys) for el in it)
  return _Desc(opener=prefix+opener, closer=closer, it=it, buffer=[])


_Items = Iterator[Tuple[Any,Any]]


def _mapping_desc(obj:Mapping, prefix:str, visited_ids:Set[int], items:_Items, simple_keys:bool) -> _Desc:
  t = type(obj)
  if t is dict:
    opener = '{'
    closer = '}'
  else:
    opener = t.__qualname__ + '({'
    closer = '})'

  it = _gen_item_descs(visited_ids, items, simple_keys, key_sep=':')
  return _Desc(opener=prefix+opener, closer=closer, it=it, buffer=[])


def _record_desc(obj:Any, prefix:str, visited_ids:Set[int], items:_Items, simple_keys:bool) -> _Desc:
  it = _gen_item_descs(visited_ids, items, simple_keys, key_sep='=')
  return _Desc(opener=f'{prefix}{type(obj).__qualname__}(', closer=')', it=it, buffer=[])


def _gen_item_descs(visited_ids:Set[int], items:_Items, simple_keys:bool, key_sep:str) -> Iterator[_DescEl]:
  for pair in items:
    try: k, v = pair
    except (TypeError, ValueError): # Guard against a weird items() iterator.
      yield f'! {pair!r}'
      continue
    if simple_keys:
      ks = str(k)
      if not _word_re.fullmatch(ks): ks = repr(k)
    else:
      ks = repr(k)
    yield _obj_desc(v, prefix=ks+key_sep, visited_ids=visited_ids, simple_keys=simple_keys)


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
_word_re = re.compile(r'[-\w]+')


def repr_lim(obj:Any, limit=64) -> str:
  r = repr(obj)
  if limit > 2 and len(r) > limit:
    q = r[0]
    if q in '\'"': return f'{r[:limit-2]}{q}…'
    else: return f'{r[:limit-1]}…'
  return r
