# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from typing import Any, Iterable, cast


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
  'Return a repr of `obj` that is at most `limit` characters long.'
  r = repr(obj)
  if limit > 2 and len(r) > limit:
    q = r[0]
    if q in '\'"': return f'{r[:limit-2]}{q}…'
    else: return f'{r[:limit-1]}…'
  return r


def repr_ml(obj:Any, at_line_start:bool=False, *, indent:int=0, width=128) -> str:
  '''
  Format a compact, multiline repr of `obj`.'
  This is similar to pprint.pformat but with a different indentation style.
  '''
  r = _repr_ml(obj, at_line_start, '  '*indent, width)
  if isinstance(r, str): return r
  return ''.join(r)


def _repr_ml(obj:Any, at_line_start:bool, indent:str, width:int) -> Iterable[str]:
  '''
  `width` is the maximum width of an inline output string; as `indent` increases, `width` decreases.
  Returns (is_inline, parts).
  '''

  if isinstance(obj, (tuple, list, set, frozenset)):
    child_indent = indent + '  '
    opener, closer = brackets_for_iterable_type(type(obj))

    # If the container is unordered, sort it.
    els = sorted(obj, key=lambda el: (type(el).__qualname__, el)) if isinstance(obj, (frozenset, set)) else obj

    reprs = [_repr_ml(el, True, child_indent, width-2) for el in obj]

    if not reprs: return opener + closer
    if all(isinstance(el, str) for el in reprs): # All inline.
      inline_reprs = cast(list[str], reprs)
      l = sum(len(s) for s in inline_reprs) + (len(els)-1) + len(closer)
      if l + 1 <= width: # Half-inlineable.
        contents = ','.join(inline_reprs)
        if len(opener) + l <= width: # Inlineable.
          return f'{opener}{contents}{closer}'
        # Put the opener on its own line and half-indent the inlined remainder.
        return (opener, '\n', f'{indent} {contents}{closer}')
    # Not inlineable.
    return _repr_ml_gen_iterable_lines(reprs, opener, closer, at_line_start, child_indent)

  if isinstance(obj, dict):
    child_indent = indent + '  '
    opener, closer = brackets_for_dict_type(type(obj))
    items = [(repr(k), _repr_ml(v, False, child_indent, width-2)) for k, v in obj.items()]
    if not items: return opener + closer
    if all(isinstance(v, str) for _, v in items): # All values are inline.
      str_items = cast(list[tuple[str,str]], items)
      l = sum(len(k)+1+len(v) for k, v in str_items) + (len(items)-1) + len(closer)
      if l + 1 <= width: # Half-inlineable.
        contents = ','.join(f'{k}:{v}' for k, v in str_items)
        if len(opener) + l <= width: # Inlineable.
          return f'{opener}{contents}{closer}'
        # Put the opener on its own line and half-inline the indented remainder.
        return (opener, '\n', f'{indent} {contents}{closer}')
    # Not inlineable.
    return _repr_ml_gen_dict_lines(items, opener, closer, at_line_start, child_indent)

  return repr(obj)


def brackets_for_iterable_type(t:type) -> tuple[str,str]:
  if t is list: return ('[', ']')
  if t is tuple: return ('(', ',)') # TODO: only use the trailing comma if necessary.
  if t is set: return ('{', '}')
  if issubclass(t, list): return (f'{t.__qualname__}([', '])')
  if issubclass(t, tuple): return (f'{t.__qualname__}(', ')')
  if issubclass(t, (frozenset, set)): return (f'{t.__qualname__}({{', '})')
  raise ValueError(t)


def brackets_for_dict_type(t:type) -> tuple[str,str]:
  if t is dict: return ('{', '}')
  return (f'{t.__qualname__}({{', '})')


def _repr_ml_gen_iterable_lines(reprs:list[Iterable[str]], opener:str, closer:str, at_line_start:bool, indent:str) -> Iterable[str]:
  it = iter(reprs)
  first = next(it) # Guaranteed to have one element.
  yield opener
  if at_line_start and len(opener) == 1: yield ' ' # Inline the opener and first element.
  else: yield '\n' + indent
  if isinstance(first, str): yield first
  else: yield from first
  sep = ',\n' + indent
  for el in it:
    yield sep
    if isinstance(el, str): yield el
    else: yield from el
  yield closer


def _repr_ml_gen_dict_lines(items:list[tuple[str,Iterable[str]]], opener:str, closer:str, at_line_start:bool, indent:str) -> Iterable[str]:
  it = iter(items)
  first = next(it) # Guaranteed to have one element.
  yield opener
  if at_line_start and len(opener) == 1: yield ' ' # Inline the opener and first element.
  else: yield '\n' + indent
  k, v = first
  yield k + ':'
  if isinstance(v, str): yield v
  else: yield from v
  sep = ',\n' + indent
  for k, v in it:
    yield sep
    if isinstance(v, str): yield f'{k}:{v}'
    else:
      yield k
      yield ':'
      yield from v
  yield closer


def test_main() -> None:
  from collections import OrderedDict

  tests:list[Any] = [
    '',
    [],
    [1,2,3],
    [[1,2,3], [4,5,6]],
    { 1, 11, 2, }, # Verify that the set is sorted.

    list(range(45)), # Inline.

    [0, 'x' * 122], # Inline.
    [0, 'x' * 123], # Multiline.

    frozenset({0, 'x' * 111}), # Inline.
    frozenset({0, 'x' * 112}), # Half-inline.
    frozenset({0, 'x' * 121}), # Half-inline.
    frozenset({0, 'x' * 122}), # Multiline.

    {0:'x', 1:'y'*116}, # Inline.
    {0:'x', 1:'y'*117}, # Multiline.

    OrderedDict({0:'x', 1:'y'*103}), # Inline.
    OrderedDict({0:'x', 1:'y'*104}), # Half-inline.
    OrderedDict({0:'x', 1:'y'*115}), # Half-inline.
    OrderedDict({0:'x', 1:'y'*116}), # Multiline.
  ]

  for test in tests:
    print()
    #print(f'test: {test!r}')
    print(repr_ml(test))


if __name__ == '__main__': test_main()