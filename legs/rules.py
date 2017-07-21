# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import *
from pithy.io import errL, errSL
from pithy.iterable import prefix_tree
from pithy.type_util import is_pair_of_int
from unico import CodeRanges, codes_for_ranges

from .automata import MkNode, empty_symbol
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
]


NfaMutableTransitions = DefaultDict[int, DefaultDict[int, Set[int]]]


class Rule:
  def __init__(self, subs: Tuple['Rule', ...]=()) -> None:
    assert isinstance(subs, tuple)
    for sub in subs: assert isinstance(sub, Rule)
    self.subs = subs

  def __repr__(self) -> str: return f'{type(self).__name__}({self.subs})'

  def describe(self, name: Optional[str], depth=0) -> None:
    n = name + ' ' if name else ''
    errL('  ' * depth, n, type(self).__name__, ':', self.inlineDescription)
    for sub in self.subs:
      sub.describe(name=None, depth=depth+1)

  @property
  def inlineDescription(self) -> str: return ''

  @property
  def isLiteral(self) -> bool: return False

  @property
  def literalPattern(self) -> str: raise AssertionError('not a literal rule: {}'.format(self))

  def genNFA(self, mk_node: MkNode, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    raise NotImplementedError


class Choice(Rule):

  def genNFA(self, mk_node: MkNode, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    for choice in self.subs:
      choice.genNFA(mk_node, transitions, start, end)


class Seq(Rule):

  def genNFA(self, mk_node: MkNode, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    subs = self.subs
    intermediates = [mk_node() for i in range(1, len(subs))]
    for sub, src, dst in zip(subs, [start] + intermediates, intermediates + [end]):
      sub.genNFA(mk_node, transitions, src, dst)

  @property
  def isLiteral(self): return all(sub.isLiteral for sub in self.subs)

  @property
  def literalPattern(self): return ''.join(sub.literalPattern for sub in self.subs)

  @classmethod
  def for_subs(cls, subs: Iterable[Rule]) -> Rule:
    s = tuple(subs)
    return s[0] if len(s) == 1 else cls(subs=s)


class Quantity(Rule):
  @property
  def sub(self) -> Rule: return self.subs[0]


class Opt(Quantity):

  def genNFA(self, mk_node, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    transitions[start][empty_symbol].add(end)
    self.sub.genNFA(mk_node, transitions, start, end)


class Star(Quantity):

  def genNFA(self, mk_node, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    branch = mk_node()
    transitions[start][empty_symbol].add(branch)
    transitions[branch][empty_symbol].add(end)
    self.sub.genNFA(mk_node, transitions, branch, branch)


class Plus(Quantity):

  def genNFA(self, mk_node, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    pre = mk_node()
    post = mk_node()
    transitions[start][empty_symbol].add(pre)
    transitions[post][empty_symbol].add(end)
    transitions[post][empty_symbol].add(pre)
    self.sub.genNFA(mk_node, transitions, pre, post)


class Charset(Rule):

  def __init__(self, ranges: CodeRanges) -> None:
    super().__init__()
    assert isinstance(ranges, tuple)
    assert all(is_pair_of_int(p) for p in ranges)
    assert ranges
    self.ranges = ranges

  def __repr__(self) -> str: return f'{type(self).__name__}({self.inlineDescription})'

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

    walk(prefix_tree(chr(code).encode() for code in codes_for_ranges(self.ranges)), start) # type: ignore # mypy bug?

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
