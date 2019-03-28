# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Callable, DefaultDict, Dict, Iterable, Optional, Set, cast

from pithy.io import errL, errSL
from pithy.types import is_pair_of_int

from .nfa import empty_symbol
from .unicode import CodeRange, CodeRanges, codes_for_ranges
from .unicode.codepoints import codes_desc


__all__ = [
  'Charset',
  'Choice',
  'Opt',
  'Plus',
  'Quantity',
  'LegsPattern',
  'Seq',
  'Star',
  'NfaMutableTransitions',
  'empty_choice',
  'empty_seq',
]


MkNode = Callable[[], int]

NfaMutableTransitions = DefaultDict[int, DefaultDict[int, Set[int]]]


class LegsPattern(tuple):

  precedence:int = -1

  def __repr__(self) -> str: return f'{type(self).__name__}{super().__repr__()}'

  def describe(self, name:Optional[str], depth=0) -> None:
    n = name + ' ' if name else ''
    errL('  ' * depth, n, type(self).__name__, ':', self.inline_description)
    for sub in self:
      sub.describe(name=None, depth=depth+1)

  @property
  def inline_description(self) -> str: return '' if self else ' Ø'

  @property
  def is_literal(self) -> bool: return False

  @property
  def literal_pattern(self) -> str: raise AssertionError('not a literal pattern: {}'.format(self))

  @property
  def literal_desc(self) -> Optional[str]:
    if not self.is_literal: return None
    p = self.literal_pattern
    if not all(0x21 <= ord(char) <= 0x7E for char in p): return None
    s = p.replace('\\', '\\\\').replace('`', '\\`')
    return f'`{s}`'

  def gen_nfa(self, mk_node:MkNode, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    raise NotImplementedError

  def gen_regex(self, flavor:str) -> str: raise NotImplementedError

  def gen_regex_sub(self, flavor:str, precedence:int) -> str:
    pattern = self.gen_regex(flavor=flavor)
    if precedence < self.precedence: return pattern
    return f'(?:{pattern})'

  def __or__(self, r: 'LegsPattern') -> 'LegsPattern':
    tl = type(self)
    tr = type(r)
    if tl.precedence > tr.precedence: return r | self
    if tl is Choice:
      if tr is Choice: return Choice(*self, *r)
      return Choice(*self, r)
    return Choice(self, r)

  def __lt__(self, r:Any) -> bool:
    if not isinstance(r, LegsPattern): return NotImplemented
    return self.precedence < r.precedence or self.precedence == r.precedence and tuple.__lt__(self, r)


class Choice(LegsPattern):

  precedence = 1

  def __init__(cls, *subs:LegsPattern) -> None: pass # for mypy only.

  def __new__(cls, *subs:LegsPattern):
    for sub in subs:
      if not isinstance(sub, LegsPattern):
        raise ValueError(f'{cls.__name__} received non-LegsPattern sub: {sub}')
    return tuple.__new__(cls, sorted(set(subs)))

  def gen_nfa(self, mk_node:MkNode, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    for sub in self:
      sub.gen_nfa(mk_node, transitions, start, end)

  def gen_regex(self, flavor:str) -> str:
    sub_patterns = [sub.gen_regex_sub(flavor=flavor, precedence=self.precedence) for sub in self]
    return '|'.join(sub_patterns)


class Seq(LegsPattern):

  precedence = 2

  def __init__(cls, *subs:LegsPattern) -> None: pass # for mypy only.

  def __new__(cls, *subs:LegsPattern):
    for sub in subs:
      if not isinstance(sub, LegsPattern):
        raise ValueError(f'{cls.__name__} received non-LegsPattern sub: {sub}')
    return tuple.__new__(cls, subs)

  def gen_nfa(self, mk_node:MkNode, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    if not self:
      transitions[start][empty_symbol].add(end)
      return
    intermediates = [mk_node() for i in range(1, len(self))]
    for sub, src, dst in zip(self, [start] + intermediates, intermediates + [end]):
      sub.gen_nfa(mk_node, transitions, src, dst)

  def gen_regex(self, flavor:str) -> str:
    sub_patterns = [sub.gen_regex_sub(flavor=flavor, precedence=self.precedence) for sub in self]
    return ''.join(sub_patterns)

  @property
  def is_literal(self): return all(sub.is_literal for sub in self)

  @property
  def literal_pattern(self): return ''.join(sub.literal_pattern for sub in self)

  @staticmethod
  def of(*subs:LegsPattern) -> LegsPattern:
    for sub in subs:
      assert isinstance(sub, LegsPattern), sub
    return subs[0] if len(subs) == 1 else Seq(*subs)

  @staticmethod
  def of_iter(subs:Iterable[LegsPattern]) -> LegsPattern:
    return Seq.of(*subs)


class Quantity(LegsPattern):

  precedence = 3
  operator:str = ''

  def __init__(cls, sub:LegsPattern) -> None: pass # for mypy only.

  def __new__(cls, *subs):
    if len(subs) != 1:
      raise ValueError(f'{cls.__name__} expcets single sub; received: {subs}')
    if not isinstance(subs[0], LegsPattern):
      raise ValueError(f'{cls.__name__} received non-LegsPattern sub: {subs[0]}')
    return tuple.__new__(cls, subs)

  def gen_regex(self, flavor:str) -> str:
    sub_pattern = self[0].gen_regex_sub(flavor=flavor, precedence=self.precedence)
    return sub_pattern + self.operator # type: ignore


class Opt(Quantity):

  operator = '?'

  def gen_nfa(self, mk_node, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    transitions[start][empty_symbol].add(end)
    self[0].gen_nfa(mk_node, transitions, start, end)


class Star(Quantity):

  operator = '*'

  def gen_nfa(self, mk_node, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    branch = mk_node()
    transitions[start][empty_symbol].add(branch)
    transitions[branch][empty_symbol].add(end)
    self[0].gen_nfa(mk_node, transitions, branch, branch)

  @staticmethod
  def of(pattern:LegsPattern) -> LegsPattern:
    if isinstance(pattern, (Plus, Star)): return pattern
    return Star(pattern)


class Plus(Quantity):

  operator = '+'

  def gen_nfa(self, mk_node, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    pre = mk_node()
    post = mk_node()
    transitions[start][empty_symbol].add(pre)
    transitions[post][empty_symbol].add(end)
    transitions[post][empty_symbol].add(pre)
    self[0].gen_nfa(mk_node, transitions, pre, post)


class Charset(LegsPattern):

  precedence = 4

  def __new__(cls, ranges):
    for r in ranges:
      if not isinstance(r, tuple):
        raise ValueError(f'{cls.__name__} received non-tuple range: {r}')
    return tuple.__new__(cls, ranges)


  def __init__(self, ranges:CodeRanges) -> None:
    super().__init__()
    assert isinstance(ranges, tuple)
    assert all(is_pair_of_int(p) for p in ranges)
    assert ranges
    self.ranges = ranges

  def __repr__(self) -> str: return f'{type(self).__name__}({self.inline_description})'


  def describe(self, name:Optional[str], depth=0) -> None:
    n = name + ' ' if name else ''
    errL('  ' * depth, n, type(self).__name__, ':', self.inline_description)


  def gen_nfa(self, mk_node:MkNode, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    node_byte_nodes = DefaultDict[int,Dict[int,int]](dict)
    for code in codes_for_ranges(self.ranges):
      node = start
      enc_bytes = chr(code).encode()
      for i, byte in enumerate(enc_bytes, 1-len(enc_bytes)):
        if i: # Not the final byte.
          byte_nodes = node_byte_nodes[node]
          try: n = byte_nodes[byte]
          except KeyError:
            n = mk_node()
            byte_nodes[byte] = n
            transitions[node][byte].add(n)
          node = n
        else: # Final byte.
          transitions[node][byte].add(end)


  def gen_regex(self, flavor:str) -> str:
    ranges = self.ranges
    if len(ranges) == 1:
      r = ranges[0]
      if r[0] + 1 == r[1]: # single character.
        return pattern_for_code(r[0], flavor)
    p = ''.join(pattern_for_code_range(r, flavor) for r in ranges)
    return f'[{p}]'

  @property
  def is_literal(self) -> bool:
    if len(self.ranges) != 1: return False
    s, e = self.ranges[0]
    return (e - s) == 1

  @property
  def literal_pattern(self) -> str: return chr(self.ranges[0][0])

  @property
  def inline_description(self) -> str: return ' ' + codes_desc(self.ranges)

  @staticmethod
  def for_char(char:str) -> 'Charset':
    code = ord(char)
    return Charset(ranges=((code, code + 1),))

  @staticmethod
  def for_code(code:int) -> 'Charset':
    return Charset(ranges=((code, code + 1),))



def pattern_for_code(code:int, flavor:str) -> str:
  if 0x30 <= code <= 0x39 or 0x41 <= code <= 0x5A or 0x61 <= code <= 0x7A or code == 0x5F:
    return chr(code) # ASCII alphanumeric or underscore.
  if code < 0x100: return f'\\x{code:02x}'
  if code < 0x10000: return f'\\u{code:04x}'
  return f'\\U{code:08x}'


def pattern_for_code_range(code_range:CodeRange, flavor:str) -> str:
  s, e = code_range
  if s + 1 == e: return pattern_for_code(s, flavor)
  return f'{pattern_for_code(s, flavor)}-{pattern_for_code(e - 1, flavor)}'

empty_choice = Choice()
empty_seq = Seq()
