# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import *
from pithy.io import errL, errSL
from pithy.iterable import prefix_tree
from pithy.type_util import is_pair_of_int
from unico import CodeRange, CodeRanges, codes_for_ranges

from .dfa import empty_symbol
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


MkNode = Callable[[], int]

NfaMutableTransitions = DefaultDict[int, DefaultDict[int, Set[int]]]
ModeNamedRules = Dict[str, List[Tuple[str, 'Rule']]]


class Rule:

  precedence: int = -1

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

  def genRegex(self, flavor: str) -> str: raise NotImplementedError

  def genRegexSub(self, flavor: str, precedence: int) -> str:
    pattern = self.genRegex(flavor=flavor)
    if precedence < self.precedence: return pattern
    return f'(?:{pattern})'


class Choice(Rule):

  precedence = 1

  def genNFA(self, mk_node: MkNode, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    for choice in self.subs:
      choice.genNFA(mk_node, transitions, start, end)

  def genRegex(self, flavor: str) -> str:
    sub_patterns = [sub.genRegexSub(flavor=flavor, precedence=self.precedence) for sub in self.subs]
    return '|'.join(sub_patterns)


class Seq(Rule):

  precedence = 2

  def genNFA(self, mk_node: MkNode, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    subs = self.subs
    intermediates = [mk_node() for i in range(1, len(subs))]
    for sub, src, dst in zip(subs, [start] + intermediates, intermediates + [end]):
      sub.genNFA(mk_node, transitions, src, dst)

  def genRegex(self, flavor: str) -> str:
    sub_patterns = [sub.genRegexSub(flavor=flavor, precedence=self.precedence) for sub in self.subs]
    return ''.join(sub_patterns)

  @property
  def isLiteral(self): return all(sub.isLiteral for sub in self.subs)

  @property
  def literalPattern(self): return ''.join(sub.literalPattern for sub in self.subs)

  @classmethod
  def for_subs(cls, subs: Iterable[Rule]) -> Rule:
    s = tuple(subs)
    return s[0] if len(s) == 1 else cls(subs=s)


class Quantity(Rule):

  precedence = 3
  operator: str = ''

  @property
  def sub(self) -> Rule: return self.subs[0]

  def genRegex(self, flavor: str) -> str:
    sub_pattern = self.sub.genRegexSub(flavor=flavor, precedence=self.precedence)
    return sub_pattern + self.operator


class Opt(Quantity):

  operator = '?'

  def genNFA(self, mk_node, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    transitions[start][empty_symbol].add(end)
    self.sub.genNFA(mk_node, transitions, start, end)


class Star(Quantity):

  operator = '*'

  def genNFA(self, mk_node, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    branch = mk_node()
    transitions[start][empty_symbol].add(branch)
    transitions[branch][empty_symbol].add(end)
    self.sub.genNFA(mk_node, transitions, branch, branch)


class Plus(Quantity):

  operator = '+'

  def genNFA(self, mk_node, transitions: NfaMutableTransitions, start: int, end: int) -> None:
    pre = mk_node()
    post = mk_node()
    transitions[start][empty_symbol].add(pre)
    transitions[post][empty_symbol].add(end)
    transitions[post][empty_symbol].add(pre)
    self.sub.genNFA(mk_node, transitions, pre, post)


class Charset(Rule):

  precedence = 4

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


  def genRegex(self, flavor: str) -> str:
    ranges = self.ranges
    if len(ranges) == 1 and ranges[0][0] + 1 == ranges[0][1]: # single character.
      return pattern_for_code(ranges[0][0], flavor)
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


def pattern_for_code(code: int, flavor: str) -> str:
  if 0x30 <= code <= 0x39 or 0x41 <= code <= 0x5A or 0x61 <= code <= 0x7A: # ASCII alphanumeric.
    return chr(code)
  if code < 0x100: return f'\\x{code:02x}'
  if code < 0x10000: return f'\\u{code:04x}'
  return f'\\U{code:08x}'


def pattern_for_code_range(code_range: CodeRange, flavor: str) -> str:
  s, e = code_range
  return f'{pattern_for_code(s, flavor)}-{pattern_for_code(e - 1, flavor)}'
