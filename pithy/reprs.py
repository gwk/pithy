# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from functools import cache
from typing import Any, cast, Iterable, NamedTuple

from .ansi import RST_TXT, TXT_B, TXT_C, TXT_G, TXT_M, TXT_R, TXT_Y
from .types import is_dataclass_or_namedtuple


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


class _Colors(NamedTuple):
  'Colors for reprs.'
  attr:str
  brace:str
  brack:str
  paren:str
  sep:str
  type:str
  rst:str

_colors = _Colors(
  attr=TXT_G,
  brace=TXT_Y,
  brack=TXT_R,
  paren=TXT_M,
  sep=TXT_B,
  type=TXT_C,
  rst=RST_TXT)

_plain = _Colors(
  attr='',
  brace='',
  brack='',
  paren='',
  sep='',
  type='',
  rst='')


assert all(len(s) == 5 for s in _colors) # This is important because we subtract this length from the width for every occurence.

def len_clr(s:str) -> int:
  '''
  Returns the length of s, ignoring ANSI color codes.
  Note: this assumes that each color code is 5 characters long.
  '''
  return len(s) - s.count('\x1b[') * 5


def repr_ml(obj:Any, at_line_start:bool=False, *, indent:int=0, width=128, spaced=True, color=False) -> str:
  '''
  Format a compact, multiline repr of `obj`.'
  This is similar to pprint.pformat but with a different indentation style.
  '''
  colors = _colors if color else _plain
  inl_comma = colors.sep + (', ' if spaced else ',')
  r = _repr_ml(obj, at_line_start, '  '*indent, width, inl_comma, colors)
  if isinstance(r, str): return r + colors.rst
  return ''.join(r) + colors.rst


def _repr_ml(obj:Any, at_line_start:bool, indent:str, width:int, inl_comma:str, colors:_Colors) -> Iterable[str]:
  '''
  `width` is the maximum width of an inline output string; as `indent` increases, `width` decreases.
  Returns (is_inline, parts).
  '''

  is_mapping = isinstance(obj, Mapping)

  if is_mapping or is_dataclass_or_namedtuple(obj):
    child_indent = indent + '  '
    typename, opener, closer, sep = syntax_for_kv_type(type(obj), colors) # type: ignore[arg-type]

    def _el_repr(el:Any) -> Iterable[str]: return _repr_ml(el, False, child_indent, width-2, inl_comma, colors)

    if is_mapping:
      items = [(repr(k), _el_repr(v)) for k, v in obj.items()]
    elif is_dataclass(obj):
      items = [(f.name, _el_repr(getattr(obj, f.name))) for f in fields(obj) if getattr(obj, f.name) != f.default]
    else:
      items = [(name, _el_repr(val)) for name, val in zip(obj._fields, obj) if val != obj._field_defaults.get(name, _not_present)]

    if not items: return f'{typename}{opener}{closer}'

    if all(isinstance(v, str) for _, v in items):
      str_items = cast(list[tuple[str,str]], items)
      l = sum(len(k)+1+len_clr(v) for k, v in str_items) + (len(str_items)-1)*len_clr(inl_comma) + len_clr(closer)
      if l + 1 <= width: # Half-inlineable.
        contents = inl_comma.join(f'{colors.attr}{k}{colors.sep}{sep}{colors.rst}{v}' for k, v in str_items)
        if len_clr(typename) + len_clr(opener) + l <= width: # Inlineable.
          return f'{typename}{opener}{contents}{closer}'
        # Put the typename/opener on its own line and half-indent the remainder.
        return (typename, opener, colors.rst, '\n', indent, ' ', contents, closer)
    # Not inlineable.
    return _repr_ml_gen_kv_lines(typename, opener, items, sep, closer, at_line_start, child_indent, colors)


  if isinstance(obj, (tuple, list, set, frozenset)):
    child_indent = indent + '  '
    typename, opener, closer = syntax_for_iterable_type(type(obj), colors)
    if not obj: return opener + closer

    # If the container is unordered, sort it.
    els = sorted(obj, key=lambda el: (type(el).__name__, str(el))) if isinstance(obj, (frozenset, set)) else obj

    reprs = [_repr_ml(el, True, child_indent, width-2, inl_comma, colors) for el in els]

    if all(isinstance(el, str) for el in reprs): # All inline.
      str_reprs = cast(list[str], reprs)
      l = sum(len_clr(s) for s in str_reprs) + (len(els)-1)*len_clr(inl_comma) + len_clr(closer)
      if l + 1 <= width: # Half-inlineable.
        contents = inl_comma.join(str_reprs)
        if type(obj) is tuple and len(els) == 1: # Special case for single-element tuples.
          contents += colors.sep+','
          l += 1
        if len_clr(typename) + len_clr(opener) + l <= width: # Inlineable.
          return f'{typename}{opener}{contents}{closer}'
        # Put the typename/opener on its own line and half-indent the remainder.
        return (colors.type, typename, colors.paren, opener, colors.rst, '\n', indent, ' ', contents, colors.paren, closer)
    # Not inlineable.
    return _repr_ml_gen_iterable_lines(typename, opener, reprs, closer, at_line_start, child_indent, colors)

  if isinstance(obj, type): return obj.__qualname__

  # Default for all other types.
  return colors.rst + repr(obj)


_not_present = object()


@cache
def syntax_for_iterable_type(t:type, c:_Colors) -> tuple[str,str,str]:
  if t is list: return ('', c.brace+'[', c.brace+']')
  if t is tuple: return ('', c.paren+'(', c.paren+')')
  if t is set: return ('', c.brack+'{', c.brack+'}')
  if issubclass(t, list): return (c.type+t.__name__, c.paren+'('+c.brack+'[', c.brack+']'+c.paren+')')
  if issubclass(t, tuple): return (c.type+t.__name__, c.paren+'(', c.paren+')')
  if issubclass(t, (frozenset, set)): return (c.type+t.__name__, c.paren+'('+c.brace+'{', c.brace+'}'+c.paren+')')
  raise ValueError(t)


@cache
def syntax_for_kv_type(t:type, c:_Colors) -> tuple[str,str,str, str]:
  if t is dict: return ('', c.paren+'{', c.paren+'}', c.sep+':')
  if is_dataclass_or_namedtuple(t): return (c.type+t.__name__, c.paren+'(', c.paren+')', c.sep+'=')
  return (c.type+t.__name__, c.paren+'({', c.paren+'})', c.sep+':') # Some dict subclass.


def _repr_ml_gen_iterable_lines(typename:str, opener:str, reprs:list[Iterable[str]], closer:str, at_line_start:bool, indent:str,
 colors:_Colors) -> Iterable[str]:
  it = iter(reprs)
  first = next(it) # Guaranteed to have one element.
  if typename:
    yield colors.type
    yield typename
  yield colors.paren
  yield opener
  yield colors.rst
  if at_line_start and not typename:
    yield ' ' # Inline the opener and first element.
  else:
    yield f'\n{indent}'
  if isinstance(first, str): yield first
  else: yield from first
  nl_indent = f'{colors.sep},{colors.rst}\n{indent}'
  single_el = True
  for el in it:
    single_el = False
    yield nl_indent
    if isinstance(el, str): yield el
    else: yield from el
  if single_el and not typename and opener == '(': # tuple requires a trailing comma.
    yield colors.sep
    yield ','
  yield colors.paren
  yield closer


def _repr_ml_gen_kv_lines(typename:str, opener:str, items:list[tuple[str,Iterable[str]]], sep:str, closer:str,
 at_line_start:bool, indent:str, colors:_Colors) -> Iterable[str]:
  it = iter(items)
  first = next(it) # Guaranteed to have one element.
  if typename:
    yield colors.type
    yield typename
  yield colors.paren
  yield opener
  yield colors.rst
  if at_line_start and not typename:
    yield ' ' # Inline the opener and first element.
  else:
    yield f'\n{indent}'
  k, v = first
  yield colors.attr
  yield k
  yield sep
  if isinstance(v, str): yield v
  else: yield from v
  nl_indent = f'{colors.sep},{colors.rst}\n{indent}{colors.attr}'
  for k, v in it:
    yield nl_indent
    yield k
    yield sep
    if isinstance(v, str): yield v
    else: yield from v
  yield colors.paren
  yield closer



def test_main() -> None:
  from collections import OrderedDict
  from dataclasses import dataclass, field

  @dataclass
  class Test:
    a:int = 0
    b:str = ''
    c:list = field(default_factory=list)

  class Test2(NamedTuple):
    a:str = ''
    b:tuple = ()

  tests:list[tuple[Any,str]] = [
    ('', 'empty str.'),
    (0, 'zero.'),
    ((), 'empty tuple.'),


    (frozenset({}), 'Empty frozenset.'),

    (frozenset({1}), 'single-element frozenset.'),


    # Long single elements should not spill.
    ((1,), 'single-element tuple.'),
    (('x'*128,), 'long single-element tuple.'),

    ([], 'empty list.'),
    ([1,2,3], 'short list.'),
    ([[1,2,3], [4,5,6]], 'short nested list.'),
    ({ 1, 11, 2, }, 'Short out-of-order set. Verify that the set is sorted.'),

    (list(range(34)), 'Inline list.'),
    (list(range(35)), 'Multiline list.'),

    ([0, 'x' * 121], 'Inline.'),
    ([0, 'x' * 122], 'Multiline.'),

    (frozenset({0, 'x' * 110}), 'Inline.'),
    (frozenset({0, 'x' * 111}), 'Half-inline.'),
    (frozenset({0, 'x' * 120}), 'Half-inline.'),
    (frozenset({0, 'x' * 121}), 'Multiline.'),

    ({0:'x', 1:'y'*116}, 'Inline.'),
    ({0:'x', 1:'y'*117}, 'Multiline.'),

    (OrderedDict({0:'x', 1:'y'*102}), 'Inline.'),
    (OrderedDict({0:'x', 1:'y'*103}), 'Half-inline.'),
    (OrderedDict({0:'x', 1:'y'*114}), 'Half-inline.'),
    (OrderedDict({0:'x', 1:'y'*115}), 'Multiline.'),

    ([Test(), Test(1), Test(1, 'x'*110), Test(1, 'x'*111), Test(1, 'x'*120), Test(1, 'x'*121)], 'List of Test instances.'),

    ( [
        Test2('x'*110),
        Test2('x'*128),
        Test2(b=('x'*129,)),
      ], 'List of Test2 instances.'),
  ]

  for obj, desc in tests:
    print()
    #print(f'test: {obj!r}')
    print(repr_ml(obj, at_line_start=True, color=True))
    print(' '*127, '| ', desc, sep='')


if __name__ == '__main__': test_main()
