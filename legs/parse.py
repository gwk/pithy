# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from pithy.iterable import fan_by_key_fn, group_by_heads, OnHeadless

from unico import codes_for_ranges, ranges_for_codes
from unico.charsets import unicode_charsets

from legs.rules import *


rule_re = re.compile(r'''(?x)
\s* # ignore leading space.
(?:
  (?P<comment> \# .*)
| % \s+ (?P<l_name> \w+ (\.\w+)? ) \s+ (?P<r_name> \w+ (\.\w+)? ) \s* (\#.*)?
| (?P<name> \w+ (\.\w+)? ) \s* : \s* (?P<pattern> .*)
| (?P<symbol> \w+ )
)
''')


def match_lines(path, lines):
  for line_num, line in enumerate(lines):
    line = line.rstrip() # always strip newline so that missing final newline is consistent.
    if not line: continue
    line_info = (path, line_num, line)
    match = rule_re.fullmatch(line)
    if not match:
      fail_parse((line_info, 0), 'invalid line: neither rule nor mode transition.')
    if match.group('comment'): continue
    yield (line_info, match)


def parse_legs(path, lines):
  '''
  Parse the legs source given in `lines`,
  returning a dictionary of mode names to rule objects, and a dictionary of mode transitions.
  '''
  rules = {} # keyed by name.
  simple_names = {}
  mode_transitions = {}
  for line_info, match in match_lines(path, lines):
    if match.group('l_name'): # mode transition.
      (src_pair, dst_pair) = parse_mode_transition(line_info, match)
      if src_pair in mode_transitions:
        fail_parse((line_info, 0), f'duplicate transition parent name: {src_pair[1]!r}')
      mode_transitions[src_pair] = dst_pair
    else:
      name, rule = parse_rule(line_info, match)
      if name in ('invalid', 'incomplete'):
        fail_parse((line_info, 0), f'rule name is reserved: {name!r}')
      if name in rules:
        fail_parse((line_info, 0), f'duplicate rule name: {name!r}')
      rules[name] = rule
      for simple in simplified_names(name):
        if simple in simple_names:
          fail_parse((line_info, 0), f'rule name collides when simplified: {simple_names[simple]!r}')
        simple_names[simple] = name
  mode_named_rules = fan_by_key_fn(rules.items(), key=lambda item: mode_for_name(item[0]))
  mode_named_rules.setdefault('main', [])
  return (mode_named_rules, mode_transitions)


def parse_mode_transition(line_info, match):
  return (
    mode_and_name(match.group('l_name')),
    mode_and_name(match.group('r_name')))


def mode_and_name(name):
  return mode_for_name(name), name


def mode_for_name(name):
  mode, _, _ = name.rpartition('.')
  return (mode or 'main')


def simplified_names(name):
  n = name.lower()
  return { n.replace('.', '_'), n.replace('.', '') }


def parse_rule(line_info, match):
  name = match.group('name')
  if name: # named pattern.
    start_col = match.start('pattern')
  else:
    symbol = match.group('symbol')
    assert symbol
    name = symbol
    start_col = match.start('symbol')
  return name, parse_rule_pattern(line_info, match, start_col=start_col)


_name_re = re.compile(r'\w')

def parse_rule_pattern(line_info, match, start_col):
  'Parse a pattern and return a Rule object.'
  _, _, line = line_info
  parser_stack = [PatternParser((line_info, start_col))]
  # stack of parsers, one for each open nesting syntactic element: root, '(…)', or '[…]'.

  def flush_name(col):
    nonlocal name_pos
    s = name_pos[1] + 1 # omit leading `$`.
    name = line[s:col]
    try: charset = unicode_charsets[name]
    except KeyError: fail_parse(name_pos, f'unknown charset name: {name!r}')
    parser_stack[-1].parse_charset(pos, charset=charset)
    name_pos = None

  pos = (line_info, start_col)
  escape = False
  end_col = len(line)
  name_pos = None # position of name currently being parsed or None.

  for col, c in enumerate(line):
    if col < start_col: continue
    pos = (line_info, col)
    parser = parser_stack[-1]

    if escape:
      escape = False
      try: charset = escape_charsets[c]
      except KeyError: fail_parse(pos, f'invalid escaped character: {c!r}')
      else: parser.parse_charset(pos, charset)
      continue

    if name_pos is not None:
      if _name_re.match(c):
        continue
      elif c in ' #)]?*+':
        flush_name(col) # then proceed to regular parsing below.
      elif c in '\\$([&-^':
        fail_parse(pos, 'name must be terminated with a space character for readability.')
      else:
        fail_parse(pos, f'invalid name character: {c!r}')

    if c == '\\':
      escape = True
    elif c == '#':
      end_col = col
      break
    elif c == ' ':
      continue
    elif c == '$':
      name_pos = pos
    elif not c.isprintable():
      fail_parse(pos, f'invalid non-printing character: {c!r}')
    elif c == parser.terminator:
      parser_stack.pop()
      parent = parser_stack[-1]
      parent.receive(parser.finish(pos))
    else:
      child = parser.parse(pos, c)
      if child:
        parser_stack.append(child)

  if escape:
    fail_parse(pos, 'dangling escape character')
  if name_pos is not None:
    flush_name(end_col)

  parser = parser_stack.pop()
  if parser_stack:
    fail_parse((line_info, end_col), f'expected terminator: {parser.terminator!r}')
  rule = parser.finish(pos)
  rule.pattern = line[start_col:end_col]
  return rule


def fake_tok(pos): return (pos[0][1], pos[1])

def fail_parse(pos, *items):
  'Print a formatted parsing failure to std err and exit.'
  (line_info, col) = pos
  (path, line_num, line_text) = line_info
  indent = ' ' * col
  exit(f'{path}:{line_num+1}:{col+1}: ' + ''.join(items) + f'\n{line_text}\n{indent}^')


def ranges_from_strings(*interval_strings):
  "Return a `str` object containing the specified range of characters denoted by each character pair."
  return tuple((ord(start), ord(last) + 1) for start, last in interval_strings)

def ranges_for_char(char):
  code = ord(char)
  return ((code, code + 1),)

escape_charsets = {
  'n': ranges_for_char('\n'),
  's': ranges_for_char(' '), # nonstandard space escape.
  't': ranges_for_char('\t'),
}
escape_charsets.update((c, ranges_for_char(c)) for c in '\\#|$?*+()[]&-^')

if False:
  for k, v in sorted(escape_charsets.items()):
    errL(f'{k}: {v!r}')


class PatternParser:

  def __init__(self, pos, terminator=None):
    self.pos = pos
    self.terminator = terminator
    self.choices = []
    self.seq = []
    self.seq_pos = pos

  def parse(self, pos, char):
    if char == '(':
      return PatternParser(pos, terminator=')')
    elif char == '[':
      return CharsetParser(pos)
    elif char == '|':
      self.flush_seq(pos)
    elif char == '?': self.quantity(pos, char, Opt)
    elif char == '*': self.quantity(pos, char, Star)
    elif char == '+': self.quantity(pos, char, Plus)
    else:
      self.seq.append(Charset(pos, ranges=ranges_for_char(char)))

  def parse_charset(self, pos, charset):
    self.seq.append(Charset(pos, ranges=charset))

  def finish(self, pos):
    self.flush_seq(pos)
    choices = self.choices
    return choices[0] if len(choices) == 1 else Choice(token=fake_tok(self.pos), subs=tuple(choices))

  def flush_seq(self, pos):
    seq = self.seq
    if not seq: fail_parse(self.seq_pos, 'empty sequence.')
    rule = seq[0] if len(seq) == 1 else Seq(token=fake_tok(self.seq_pos), subs=tuple(seq))
    self.choices.append(rule)
    self.seq = []
    self.seq_pos = pos

  def quantity(self, pos, char, T):
    try: el = self.seq.pop()
    except IndexError: fail_parse(pos, f"'{char}' does not follow any pattern.")
    else: self.seq.append(T(token=fake_tok(pos), subs=(el,)))

  def receive(self, result):
    self.seq.append(result)


class CharsetParser():
  '''
  The Legs character set syntax is different from traditional regular expressions.
  * `[...]` introduces a nested character set.
  * `&` binary operator: set intersection.
  * `-` binary operator: set difference.
  * `^` binary operator: set symmetric difference.
  Multiple intersection operators can be chained together,
  but if a difference or set difference operator is used,
  it must be the only operator to appear witihin the character set;
  more complex expressions must be explicitly grouped.
  Thus, the set expression syntax has no operator precedence or associativity.
  '''

  def __init__(self, pos):
    self.pos = pos
    self.terminator = ']'
    self.codes = set()
    self.codes_left = None  # left operand to current operator.
    self.operator = None # current operator waiting to finish parsing right side.
    self.operator_pos = None
    self.parsed_op = False
    self.parsed_diff_op = False

  def add_code(self, pos, code):
    if code in self.codes:
      fail_parse(pos, f'repeated character in set: {ord(code)!r}')
    self.codes.add(code)

  def flush_left(self, pos, msg_context):
    if not self.codes:
      fail_parse(pos, 'empty charset preceding ', msg_context)
    op = self.operator
    if op is None: # first operator encountered.
      assert self.codes_left is None
      self.codes_left = self.codes
    elif op == '&': self.codes_left &= self.codes
    elif op == '-': self.codes_left -= self.codes
    elif op == '^': self.codes_left ^= self.codes
    else: raise ValueError(op) # internal error.
    self.codes = set()

  def push_operator(self, pos, op):
    self.flush_left(pos, msg_context='operator')
    is_diff_op = self.operator in ('-', '^')
    if self.parsed_diff_op or (self.parsed_op and is_diff_op):
      fail_parse(pos, 'compound set expressions containing `-` or `^` operators must be grouped with `[...]`: ', op)
    self.parsed_op = True
    self.parsed_diff_op |= is_diff_op
    self.operator = op
    self.operator_pos = pos

  def parse(self, pos, char):
    if char == '[':
      return CharsetParser(pos)
    elif char in '&-^':
      self.push_operator(pos, char)
    else:
      self.add_code(pos, ord(char))

  def parse_charset(self, pos, charset):
    for code in codes_for_ranges(charset):
      self.add_code(pos, code)

  def parse_name(self, pos, name):
    assert self.current_name_pos is not None
    assert self.current_name_chars is not None
    if not self.current_name_chars:
      fail_parse(self.current_name_pos, 'empty charset name.')
    name = ''.join(self.current_name_chars)
    try: named_charset = unicode_charsets[name]
    except KeyError: fail_parse(self.current_name_pos, 'unknown charset name.')
    self.codes.update(codes_for_ranges(named_charset))
    self.current_name_pos = None
    self.current_name_chars = None

  def finish(self, pos):
    if self.operator: self.flush_left(pos, msg_context='terminator')
    codes = self.codes_left or self.codes
    if not codes: fail_parse(self.pos, 'empty character set.')
    return Charset(self.pos, ranges=tuple(ranges_for_codes(sorted(codes))))
