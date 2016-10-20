# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.io import errFL, errL, errSL, errLL
from pithy.seq import seq_prefix_tree, seq_first

from .automata import empty_symbol


class Rule:
  def __init__(self, pos, subs=None):
    if subs is not None:
      assert isinstance(subs, tuple)
      for sub in subs: assert isinstance(sub, Rule)
    self.pos = pos
    self.subs = subs
    self.name = None
    self.mode = None
    self.pattern = None

  def describe(self, depth=0):
    (_, line_num, _), col = self.pos
    n = self.name + ' ' if self.name else ''
    errFL('{}{}{}:{}:{}:{}', '  ' * depth, n, type(self).__name__, line_num + 1, col + 1, self.inlineDescription)
    if self.subs:
      for sub in self.subs:
        sub.describe(depth + 1)

  @property
  def inlineDescription(self): return ''

  @property
  def isLiteral(self): return False

  @property
  def literalPattern(self): raise AssertionError('not a literal rule: {}'.format(self))


class Choice(Rule):

  def genNFA(self, mk_node, transitions, start, end):
    for choice in self.subs:
      choice.genNFA(mk_node, transitions, start, end)


class Seq(Rule):

  def genNFA(self, mk_node, transitions, start, end):
    subs = self.subs
    intermediates = [mk_node() for i in range(1, len(subs))]
    for sub, src, dst in zip(subs, [start] + intermediates, intermediates + [end]):
      sub.genNFA(mk_node, transitions, src, dst)

  @property
  def isLiteral(self): return all(sub.isLiteral for sub in self.subs)

  @property
  def literalPattern(self): return ''.join(sub.literalPattern for sub in self.subs)


class Quantity(Rule):
  @property
  def sub(self): return self.subs[0]


class Opt(Quantity):

  def genNFA(self, mk_node, transitions, start, end):
    transitions[start][empty_symbol].add(end)
    self.sub.genNFA(mk_node, transitions, start, end)


class Star(Quantity):

  def genNFA(self, mk_node, transitions, start, end):
    branch = mk_node()
    transitions[start][empty_symbol].add(branch)
    transitions[branch][empty_symbol].add(end)
    self.sub.genNFA(mk_node, transitions, branch, branch)


class Plus(Quantity):

  def genNFA(self, mk_node, transitions, start, end):
    pre = mk_node()
    post = mk_node()
    transitions[start][empty_symbol].add(pre)
    transitions[post][empty_symbol].add(end)
    transitions[post][empty_symbol].add(pre)
    self.sub.genNFA(mk_node, transitions, pre, post)


class Charset(Rule):

  def __init__(self, pos, codes):
    super().__init__(pos=pos)
    assert isinstance(codes, list)
    assert codes
    self.codes = codes

  def genNFA(self, mk_node, transitions, start, end):

    def walk(seq_map, node):
      for byte, sub_map in seq_map.items():
        if byte is None: continue # handled by parent frame of `walk`.
        if None in sub_map:
          transitions[node][byte].add(end)
          if len(sub_map) == 1: continue # no need to recurse.
        next_node = mk_node()
        transitions[node][byte].add(next_node)
        walk(sub_map, next_node)

    walk(seq_prefix_tree(chr(code).encode() for code in self.codes), start)

  @property
  def isLiteral(self): return len(self.codes) == 1

  @property
  def literalPattern(self): return chr(seq_first(self.codes))

  @property
  def inlineDescription(self): return ' ' + codes_desc(self.codes)


