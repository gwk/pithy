# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from dataclasses import fields, is_dataclass
from typing import Any, cast, Iterable


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


def repr_ml(obj:Any, at_line_start:bool=False, *, indent:int=0, width=128, spaced=True) -> str:
  '''
  Format a compact, multiline repr of `obj`.'
  This is similar to pprint.pformat but with a different indentation style.
  '''
  comma = ', ' if spaced else ','
  r = _repr_ml(obj, at_line_start, '  '*indent, width, comma)
  if isinstance(r, str): return r
  return ''.join(r)


def _repr_ml(obj:Any, at_line_start:bool, indent:str, width:int, comma:str) -> Iterable[str]:
  '''
  `width` is the maximum width of an inline output string; as `indent` increases, `width` decreases.
  Returns (is_inline, parts).
  '''

  if is_dataclass_or_namedtuple(obj):
    child_indent = indent + '  '
    opener = f'{type(obj).__qualname__}('
    closer = ')'

    def _el_repr(el:Any) -> Iterable[str]: return _repr_ml(el, False, child_indent, width-2, comma)

    if is_dataclass(obj):
      vis_items = [(f.name, _el_repr(getattr(obj, f.name))) for f in fields(obj) if getattr(obj, f.name) != f.default]
    else:
      # At present there is no clear way to get the default values of a namedtuple.
      # * Get_annotations does not return default values.
      # * Attempting to getattr on the class returns a `_tuplegetter` object.
      vis_items = [(name, _el_repr(val)) for name, val in zip(obj._fields, obj)]

    if not vis_items: return opener + closer

    if all(isinstance(v, str) for _, v in vis_items):
      str_items = cast(list[tuple[str,str]], vis_items)
      l = sum(len(k)+1+len(v) for k, v in str_items) + (len(str_items)-1)*len(comma) + len(closer)
      if l + 1 <= width: # Half-inlineable.
        contents = comma.join(f'{k}={v}' for k, v in str_items)
        if len(opener) + l <= width: # Inlineable.
          return f'{opener}{contents}{closer}'
        # Put the opener on its own line and half-indent the remainder.
        return (opener, '\n', f'{indent} {contents}{closer}')
    # Not inlineable.
    return _repr_ml_gen_kv_lines(vis_items, opener, closer, '=', at_line_start, child_indent)

  if isinstance(obj, (tuple, list, set, frozenset)):
    child_indent = indent + '  '
    opener, closer = brackets_for_iterable_type(type(obj))
    if not obj: return opener + closer

    # If the container is unordered, sort it.
    els = sorted(obj, key=lambda el: (type(el).__qualname__, el)) if isinstance(obj, (frozenset, set)) else obj

    reprs = [_repr_ml(el, True, child_indent, width-2, comma) for el in obj]

    if all(isinstance(el, str) for el in reprs): # All inline.
      str_reprs = cast(list[str], reprs)
      l = sum(len(s) for s in str_reprs) + (len(els)-1)*len(comma) + len(closer)
      if l + 1 <= width: # Half-inlineable.
        contents = comma.join(str_reprs)
        if len(opener) + l <= width: # Inlineable.
          return f'{opener}{contents}{closer}'
        # Put the opener on its own line and half-indent the inlined remainder.
        return (opener, '\n', f'{indent} {contents}{closer}')
    # Not inlineable.
    return _repr_ml_gen_iterable_lines(reprs, opener, closer, at_line_start, child_indent)

  if isinstance(obj, dict):
    child_indent = indent + '  '
    opener, closer = brackets_for_dict_type(type(obj))
    if not obj: return opener + closer

    items = [(repr(k), _repr_ml(v, False, child_indent, width-2, comma)) for k, v in obj.items()]
    if all(isinstance(v, str) for _, v in items): # All values are inline.
      str_items = cast(list[tuple[str,str]], items)
      l = sum(len(k)+1+len(v) for k, v in str_items) + (len(items)-1)*len(comma) + len(closer)
      if l + 1 <= width: # Half-inlineable.
        contents = comma.join(f'{k}:{v}' for k, v in str_items)
        if len(opener) + l <= width: # Inlineable.
          return f'{opener}{contents}{closer}'
        # Put the opener on its own line and half-indent the remainder.
        return (opener, '\n', f'{indent} {contents}{closer}')
    # Not inlineable.
    return _repr_ml_gen_kv_lines(items, opener, closer, ':', at_line_start, child_indent)

  if isinstance(obj, type): return obj.__qualname__

  # Default for all other types.
  return repr(obj)


def is_dataclass_or_namedtuple(obj:Any) -> bool:
  return is_dataclass(obj) or (isinstance(obj, tuple) and hasattr(obj, '_fields'))


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
  nl_indent = ',\n' + indent
  for el in it:
    yield nl_indent
    if isinstance(el, str): yield el
    else: yield from el
  yield closer


def _repr_ml_gen_kv_lines(items:list[tuple[str,Iterable[str]]], opener:str, closer:str, sep:str, at_line_start:bool, indent:str) -> Iterable[str]:
  it = iter(items)
  first = next(it) # Guaranteed to have one element.
  yield opener
  if at_line_start and len(opener) == 1: yield ' ' # Inline the opener and first element.
  else: yield '\n' + indent
  k, v = first
  yield k
  yield sep
  if isinstance(v, str): yield v
  else: yield from v
  nl_indent = ',\n' + indent
  for k, v in it:
    yield nl_indent
    yield k
    yield sep
    if isinstance(v, str): yield v
    else: yield from v
  yield closer


def test_main() -> None:
  from collections import OrderedDict
  from dataclasses import dataclass, field

  @dataclass
  class Test:
    a:int = 0
    b:str = ''
    c:list = field(default_factory=list)

  tests:list[Any] = [
    '',
    [],
    [1,2,3],
    [[1,2,3], [4,5,6]],
    { 1, 11, 2, }, # Verify that the set is sorted.

    list(range(34)), # Inline.
    list(range(35)), # Multiline.

    [0, 'x' * 121], # Inline.
    [0, 'x' * 122], # Multiline.

    frozenset({0, 'x' * 110}), # Inline.
    frozenset({0, 'x' * 111}), # Half-inline.
    frozenset({0, 'x' * 120}), # Half-inline.
    frozenset({0, 'x' * 121}), # Multiline.

    {0:'x', 1:'y'*116}, # Inline.
    {0:'x', 1:'y'*117}, # Multiline.

    OrderedDict({0:'x', 1:'y'*102}), # Inline.
    OrderedDict({0:'x', 1:'y'*103}), # Half-inline.
    OrderedDict({0:'x', 1:'y'*114}), # Half-inline.
    OrderedDict({0:'x', 1:'y'*115}), # Multiline.

    [Test(), Test(1), Test(1, 'x'*110), Test(1, 'x'*111), Test(1, 'x'*120), Test(1, 'x'*121)],
  ]

  for test in tests:
    print(' '*127, '|', sep='')
    #print(f'test: {test!r}')
    print(repr_ml(test))


if __name__ == '__main__': test_main()
