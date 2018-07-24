# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import *
from pithy.io import errL, errSL
from pithy.iterable import prefix_tree
from pithy.types import is_pair_of_int
from .unico import CodeRange, CodeRanges, codes_for_ranges

from .nfa import empty_symbol
from .codepoints import codes_desc


__all__ = [
  'Charset',
  'Choice',
  'Opt',
  'Plus',
  'Quantity',
  'Rule',
  'Seq',
  'Star',
  'NfaMutableTransitions',
  'empty_choice',
  'empty_seq',
]


MkNode = Callable[[], int]

NfaMutableTransitions = DefaultDict[int, DefaultDict[int, Set[int]]]


class Rule(tuple):

  precedence: int = -1

  def __repr__(self) -> str: return f'{type(self).__name__}{super().__repr__()}'

  def describe(self, name: Optional[str], depth=0) -> None:
    n = name + ' ' if name else ''
    errL('  ' * depth, n, type(self).__name__, ':', self.inlineDescription)
    for sub in self:
      sub.describe(name=None, depth=depth+1)

  @property
  def inlineDescription(self) -> str: return '' if self else ' Ø'

  @property
  def isLiteral(self) -> bool: return False

  @property
  def literalPattern(self) -> str: raise AssertionError('not a literal rule: {}'.format(self))

  @property
  def literalDesc(self) -> Optional[str]:
    if not self.isLiteral: return None
    p = self.literalPattern
    if not all(0x21 <= ord(char) <= 0x7E for char in p): return None
    s = p.replace('\\', '\\\\').replace('`', '\\`')
    return f'`{s}`'

  def genNFA(self, mk_node: MkNode, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    raise NotImplementedError

  def genRegex(self, flavor: str) -> str: raise NotImplementedError

  def genRegexSub(self, flavor: str, precedence: int) -> str:
    pattern = self.genRegex(flavor=flavor)
    if precedence < self.precedence: return pattern
    return f'(?:{pattern})'

  def __or__(self, r: 'Rule') -> 'Rule':
    tl = type(self)
    tr = type(r)
    if tl.precedence > tr.precedence: return r | self
    if tl is Choice:
      if tr is Choice: return Choice(*self, *r)
      return Choice(*self, r)
    return Choice(self, r)

  def __lt__(self, r: Any) -> bool:
    if not isinstance(r, Rule): return NotImplemented
    return self.precedence < r.precedence or self.precedence == r.precedence and tuple.__lt__(self, r)


class Choice(Rule):

  precedence = 1

  def __init__(cls, *subs: Rule) -> None: pass # for mypy only.

  def __new__(cls, *subs: Rule):
    for sub in subs:
      if not isinstance(sub, Rule):
        raise ValueError(f'{cls.__name__} received non-Rule sub: {sub}')
    return tuple.__new__(cls, sorted(set(subs))) # type: ignore

  def genNFA(self, mk_node: MkNode, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    for sub in self:
      sub.genNFA(mk_node, transitions, start, end)

  def genRegex(self, flavor: str) -> str:
    sub_patterns = [sub.genRegexSub(flavor=flavor, precedence=self.precedence) for sub in self]
    return '|'.join(sub_patterns)


class Seq(Rule):

  precedence = 2

  def __init__(cls, *subs: Rule) -> None: pass # for mypy only.

  def __new__(cls, *subs: Rule):
    for sub in subs:
      if not isinstance(sub, Rule):
        raise ValueError(f'{cls.__name__} received non-Rule sub: {sub}')
    return tuple.__new__(cls, subs) # type: ignore

  def genNFA(self, mk_node: MkNode, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    if not self:
      transitions[start][empty_symbol].add(end)
      return
    intermediates = [mk_node() for i in range(1, len(self))]
    for sub, src, dst in zip(self, [start] + intermediates, intermediates + [end]):
      sub.genNFA(mk_node, transitions, src, dst)

  def genRegex(self, flavor: str) -> str:
    sub_patterns = [sub.genRegexSub(flavor=flavor, precedence=self.precedence) for sub in self]
    return ''.join(sub_patterns)

  @property
  def isLiteral(self): return all(sub.isLiteral for sub in self)

  @property
  def literalPattern(self): return ''.join(sub.literalPattern for sub in self)

  @staticmethod
  def of(*subs: Rule) -> Rule:
    for sub in subs:
      assert isinstance(sub, Rule), sub
    return subs[0] if len(subs) == 1 else Seq(*subs)

  @staticmethod
  def of_iter(subs: Iterable[Rule]) -> Rule:
    return Seq.of(*subs)


class Quantity(Rule):

  precedence = 3
  operator: str = ''

  def __init__(cls, sub: Rule) -> None: pass # for mypy only.

  def __new__(cls, *subs):
    if len(subs) != 1:
      raise ValueError(f'{cls.__name__} expcets single sub; received: {subs}')
    if not isinstance(subs[0], Rule):
      raise ValueError(f'{cls.__name__} received non-Rule sub: {subs[0]}')
    return tuple.__new__(cls, subs) # type: ignore

  def genRegex(self, flavor: str) -> str:
    sub_pattern = self[0].genRegexSub(flavor=flavor, precedence=self.precedence)
    return sub_pattern + self.operator # type: ignore


class Opt(Quantity):

  operator = '?'

  def genNFA(self, mk_node, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    transitions[start][empty_symbol].add(end)
    self[0].genNFA(mk_node, transitions, start, end)


class Star(Quantity):

  operator = '*'

  def genNFA(self, mk_node, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    branch = mk_node()
    transitions[start][empty_symbol].add(branch)
    transitions[branch][empty_symbol].add(end)
    self[0].genNFA(mk_node, transitions, branch, branch)

  @staticmethod
  def of(rule: Rule) -> Rule:
    if isinstance(rule, (Plus, Star)): return rule
    return Star(rule)


class Plus(Quantity):

  operator = '+'

  def genNFA(self, mk_node, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    pre = mk_node()
    post = mk_node()
    transitions[start][empty_symbol].add(pre)
    transitions[post][empty_symbol].add(end)
    transitions[post][empty_symbol].add(pre)
    self[0].genNFA(mk_node, transitions, pre, post)


class Charset(Rule):

  precedence = 4

  def __new__(cls, ranges):
    for r in ranges:
      if not isinstance(r, tuple):
        raise ValueError(f'{cls.__name__} received non-tuple range: {r}')
    return tuple.__new__(cls, ranges) # type: ignore


  def __init__(self, ranges: CodeRanges) -> None:
    super().__init__()
    assert isinstance(ranges, tuple)
    assert all(is_pair_of_int(p) for p in ranges)
    assert ranges
    self.ranges = ranges

  def __repr__(self) -> str: return f'{type(self).__name__}({self.inlineDescription})'


  def describe(self, name: Optional[str], depth=0) -> None:
    n = name + ' ' if name else ''
    errL('  ' * depth, n, type(self).__name__, ':', self.inlineDescription)


  def genNFA(self, mk_node: MkNode, transitions: NfaMutableTransitions, start: int, end: int) -> None:

    def walk(seq_map: Dict[Optional[int], Optional[Dict]], node: int) -> None:
      for byte, sub_map_ in seq_map.items():
        if byte is None: continue # handled by parent frame of `walk`.
        sub_map = cast(Dict[Optional[int], Optional[Dict]], sub_map_)
        if None in sub_map:
          transitions[node][byte].add(end)
          if len(sub_map) == 1: continue # no need to recurse.
        next_node = mk_node()
        transitions[node][byte].add(next_node)
        walk(sub_map, next_node)

    walk(prefix_tree(chr(code).encode() for code in codes_for_ranges(self.ranges)), start)


  def genRegex(self, flavor: str) -> str:
    ranges = self.ranges
    if len(ranges) == 1:
      r = ranges[0]
      if r[0] + 1 == r[1]: # single character.
        return pattern_for_code(r[0], flavor)
    p = ''.join(pattern_for_code_range(r, flavor) for r in ranges)
    return f'[{p}]'

  @property
  def isLiteral(self) -> bool:
    if len(self.ranges) != 1: return False
    s, e = self.ranges[0]
    return (e - s) == 1

  @property
  def literalPattern(self) -> str: return chr(self.ranges[0][0])

  @property
  def inlineDescription(self) -> str: return ' ' + codes_desc(self.ranges)

  @classmethod
  def for_char(cls: Type['Charset'], char: str) -> 'Charset':
    code = ord(char)
    return cls(ranges=((code, code + 1),))

  @classmethod
  def for_code(cls: Type['Charset'], code: int) -> 'Charset':
    return cls(ranges=((code, code + 1),))



def pattern_for_code(code: int, flavor: str) -> str:
  if 0x30 <= code <= 0x39 or 0x41 <= code <= 0x5A or 0x61 <= code <= 0x7A or code == 0x5F:
    return chr(code) # ASCII alphanumeric or underscore.
  if code < 0x100: return f'\\x{code:02x}'
  if code < 0x10000: return f'\\u{code:04x}'
  return f'\\U{code:08x}'


def pattern_for_code_range(code_range: CodeRange, flavor: str) -> str:
  s, e = code_range
  if s + 1 == e: return pattern_for_code(s, flavor)
  return f'{pattern_for_code(s, flavor)}-{pattern_for_code(e - 1, flavor)}'

empty_choice = Choice()
empty_seq = Seq()
