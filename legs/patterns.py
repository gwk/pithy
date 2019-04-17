# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Callable, DefaultDict, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple, cast

from pithy.io import errL, errSL
from pithy.types import is_pair_of_int

from .nfa import empty_symbol
from .unicode import CodeRange, CodeRanges, codes_for_ranges, ranges_for_codes
from .unicode.codepoints import codes_desc


__all__ = [
  'Charset',
  'Choice',
  'LegsPattern',
  'NfaMutableTransitions',
  'Opt',
  'Plus',
  'QuantityPattern',
  'Seq',
  'Star',
  'regex_for_codes',
]


MkNode = Callable[[], int]

NfaMutableTransitions = DefaultDict[int, DefaultDict[int, Set[int]]]


class LegsPattern:

  precedence:int = -1

  def describe(self, name:Optional[str], depth=0) -> None: raise NotImplementedError

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

  def gen_incomplete(self) -> Optional['LegsPattern']: raise NotImplementedError(self)


class StructPattern(LegsPattern):

  def __iter__(self) -> Iterator[LegsPattern]: raise NotImplementedError

  def describe(self, name:Optional[str], depth=0) -> None:
    n = name + ' ' if name else ''
    subs = tuple(self)
    errL('  ' * depth, n, type(self).__name__, ':', '' if subs else ' Ø')
    for sub in self:
      sub.describe(name=None, depth=depth+1)


class Choice(StructPattern):

  precedence = 1

  def __init__(self, hd:LegsPattern, tl:LegsPattern, *rem:LegsPattern) -> None:
    self.hd = hd
    self.tl = Choice(tl, *rem) if rem else tl

  def __iter__(self) -> Iterator[LegsPattern]:
    link:LegsPattern = self
    while isinstance(link, Choice):
      yield link.hd
      link = link.tl
    yield link

  def gen_nfa(self, mk_node:MkNode, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    for sub in self:
      sub.gen_nfa(mk_node, transitions, start, end)

  def gen_regex(self, flavor:str) -> str:
    sub_patterns = [sub.gen_regex_sub(flavor=flavor, precedence=self.precedence) for sub in self]
    return '|'.join(sub_patterns)

  def gen_incomplete(self) -> Optional[LegsPattern]:
    hd = self.hd.gen_incomplete()
    tl = self.tl.gen_incomplete()
    if not tl: return hd
    if not hd: return tl
    return Choice(hd, tl)

  @staticmethod
  def from_opts(subs:Iterable[Optional[LegsPattern]]) -> Optional[LegsPattern]:
    l = [s for s in subs if s]
    if not l: return None
    if len(l) == 1: return l[0]
    return Choice(*l)


class Seq(StructPattern):

  precedence = 2

  def __init__(self, els:Iterable[LegsPattern]) -> None:
    self.els = tuple(els)
    if len(self.els) < 2: raise ValueError(els)

  def __iter__(self) -> Iterator[LegsPattern]:
    return iter(self.els)

  def gen_nfa(self, mk_node:MkNode, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    if not self:
      transitions[start][empty_symbol].add(end)
      return
    intermediates = [mk_node() for i in range(1, len(self.els))]
    for sub, src, dst in zip(self.els, [start] + intermediates, intermediates + [end]):
      sub.gen_nfa(mk_node, transitions, src, dst)

  def gen_regex(self, flavor:str) -> str:
    sub_patterns = [sub.gen_regex_sub(flavor=flavor, precedence=self.precedence) for sub in self]
    return ''.join(sub_patterns)

  def gen_incomplete(self) -> Optional[LegsPattern]:
    els = self.els
    incs:List[LegsPattern] = []
    for i in range(len(els)):
      inc_els = list(els[:i])
      inc_tail = els[i].gen_incomplete()
      if inc_tail is not None:
        inc_els.append(inc_tail)
      inc = Seq.from_opts(inc_els)
      if inc: incs.append(inc)
    # TODO: any non-tail element in the sequence must be expanded out.
    # Reverse so that the most complete match is preferred.
    return Choice.from_opts(reversed(incs))

  @property
  def is_literal(self): return all(sub.is_literal for sub in self)

  @property
  def literal_pattern(self): return ''.join(sub.literal_pattern for sub in self)

  @staticmethod
  def from_list(els:List[LegsPattern]) -> LegsPattern:
    if len(els) == 1: return els[0]
    return Seq(els)

  @staticmethod
  def from_opts(els:Iterable[Optional[LegsPattern]]) -> Optional[LegsPattern]:
    l = list(filter(None, els))
    if not l: return None
    return Seq.from_list(l)


class QuantityPattern(StructPattern):

  precedence = 3
  operator:str = ''

  def __init__(self, sub:LegsPattern) -> None:
    self.sub = sub

  def __iter__(self) -> Iterator[LegsPattern]:
    yield self.sub

  def gen_regex(self, flavor:str) -> str:
    sub_pattern = self.sub.gen_regex_sub(flavor=flavor, precedence=self.precedence)
    return sub_pattern + self.operator


class Opt(QuantityPattern):

  operator = '?'

  def gen_nfa(self, mk_node, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    transitions[start][empty_symbol].add(end)
    self.sub.gen_nfa(mk_node, transitions, start, end)

  def gen_incomplete(self) -> Optional[LegsPattern]:
    return self.sub.gen_incomplete()


class Star(QuantityPattern):

  operator = '*'

  def gen_nfa(self, mk_node, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    branch = mk_node()
    transitions[start][empty_symbol].add(branch)
    transitions[branch][empty_symbol].add(end)
    self.sub.gen_nfa(mk_node, transitions, branch, branch)

  def gen_incomplete(self) -> Optional[LegsPattern]:
    sub_inc = self.sub.gen_incomplete()
    if sub_inc is None: return None
    return Seq.from_opts((self, sub_inc))


class Plus(QuantityPattern):

  operator = '+'

  def gen_nfa(self, mk_node, transitions:NfaMutableTransitions, start:int, end:int) -> None:
    pre = mk_node()
    post = mk_node()
    transitions[start][empty_symbol].add(pre)
    transitions[post][empty_symbol].add(end)
    transitions[post][empty_symbol].add(pre)
    self.sub.gen_nfa(mk_node, transitions, pre, post)

  def gen_incomplete(self) -> Optional[LegsPattern]:
    return Star(self.sub).gen_incomplete()


class Charset(LegsPattern):

  precedence = 4

  def __init__(self, ranges:Iterable[CodeRange]) -> None:
    self.ranges = tuple(ranges)

  def describe(self, name:Optional[str], depth=0) -> None:
    n = name + ' ' if name else ''
    errL('  ' * depth, n, type(self).__name__, ': ', codes_desc(self.ranges))


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
    if flavor.endswith('.bytes') and any(r[1] >= 0x80 for r in ranges):
      # Some code points exceed ASCII range; need to encode char-by-char.
      s = '|'.join(''.join(regex_for_code(byte, flavor) for byte in chr(code).encode()) for r in ranges for code in r)
      return f'(?:{s})'
    return regex_for_code_ranges(ranges, flavor)


  def gen_incomplete(self) -> Optional[LegsPattern]:
    return None


  @property
  def is_literal(self) -> bool:
    if len(self.ranges) != 1: return False
    s, e = self.ranges[0]
    return (e - s) == 1

  @property
  def literal_pattern(self) -> str: return chr(self.ranges[0][0])

  @staticmethod
  def for_char(char:str) -> 'Charset':
    code = ord(char)
    return Charset(ranges=((code, code + 1),))

  @staticmethod
  def for_code(code:int) -> 'Charset':
    return Charset(ranges=((code, code + 1),))



def regex_for_code(code:int, flavor:str) -> str:
  if 0x30 <= code <= 0x39 or 0x41 <= code <= 0x5A or 0x61 <= code <= 0x7A or code == 0x5F:
    return chr(code) # ASCII alphanumeric or underscore.
  if code < 0x100: return f'\\x{code:02x}'
  if code < 0x10000: return f'\\u{code:04x}'
  return f'\\U{code:08x}'


def regex_for_code_range(code_range:CodeRange, flavor:str) -> str:
  start, end = code_range
  last = end - 1
  if start == last: return regex_for_code(start, flavor)
  return f'{regex_for_code(start, flavor)}-{regex_for_code(last, flavor)}'


def regex_for_code_ranges(ranges:Sequence[CodeRange], flavor:str) -> str:
  if len(ranges) == 1:
    r = ranges[0]
    if r[0] + 1 == r[1]: # single character.
      return regex_for_code(r[0], flavor)
  p = ''.join(regex_for_code_range(r, flavor) for r in ranges)
  return f'[{p}]'


def regex_for_codes(codes:Iterable[int], flavor:str) -> str:
  return regex_for_code_ranges(tuple(ranges_for_codes(codes)), flavor)


def gen_incomplete_pattern(kinds_greedy_ordered:List[str], patterns:Dict[str,LegsPattern]) -> Optional[LegsPattern]:
  incompletes:List[LegsPattern] = []
  for kind in kinds_greedy_ordered:
    pattern = patterns[kind]
    incomplete = pattern.gen_incomplete()
    if incomplete: incompletes.append(incomplete)
  return Choice.from_opts(incompletes)
