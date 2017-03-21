# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from pithy.iterable import fan_by_key_fn, group_by_heads, OnHeadless
from pithy.lex import *
from pithy.io import *

from unico import codes_for_ranges, ranges_for_codes
from unico.charsets import unicode_charsets

from legs.rules import *


lexer = Lexer('x',
  line        = r'\n',
  space       = r'\ +',
  comment     = r'\# [^\n]*',
  transition  = r'% \s+ (?P<l_name> \w+ (\.\w+)? ) \s+ (?P<r_name> \w+ (\.\w+)? ) \s* (\#[^\n]*)?',
  rule        = r'(?P<name> \w+ (\.\w+)? ) \s* : \s* (?P<pattern> [^\n]*)',
  symbol      = r'\w+',
)


def parse_legs(path, src):
  '''
  Parse the legs source given in `src`,
  returning a dictionary of mode names to rule objects, and a dictionary of mode transitions.
  '''
  rules = {} # keyed by name.
  simple_names = {}
  mode_transitions = {}
  for match in lexer.lex(src, drop={'line', 'space', 'comment'}):
    line_info = (path, match)
    if match.lastgroup == 'transition':
      (src_pair, dst_pair) = parse_mode_transition(match)
      if src_pair in mode_transitions:
        fail_parse(line_info, 0, f'duplicate transition parent name: {src_pair[1]!r}')
      mode_transitions[src_pair] = dst_pair
    else:
      name, rule = parse_rule(path, match)
      if name in ('invalid', 'incomplete'):
        fail_parse(line_info, 0, f'rule name is reserved: {name!r}')
      if name in rules:
        fail_parse(line_info, 0, f'duplicate rule name: {name!r}')
      rules[name] = rule
      for simple in simplified_names(name):
        if simple in simple_names:
          fail_parse(line_info, 0, f'rule name collides when simplified: {simple_names[simple]!r}')
        simple_names[simple] = name
  mode_named_rules = fan_by_key_fn(rules.items(), key=lambda item: mode_for_name(item[0]))
  mode_named_rules.setdefault('main', [])
  return (mode_named_rules, mode_transitions)


def parse_mode_transition(match):
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


def parse_rule(path, match):
  if match.lastgroup == 'rule':
    name = match['name']
    span = match.span('pattern')
  else:
    assert match.lastgroup == 'symbol'
    name = match['symbol']
    span = match.span('symbol')
  return name, parse_rule_pattern(path, match=match, span=span)


_name_re = re.compile(r'\w')

def parse_rule_pattern(path, match, span):
  'Parse a pattern and return a Rule object.'
  line_info = (path, match)
  start_pos, end_pos = span
  parser_stack = [PatternParser(pos=start_pos)]
  # stack of parsers, one for each open nesting syntactic element: root, '(…)', or '[…]'.

  name_pos = None # position of name currently being parsed or None.
  def flush_name(line_info, end):
    nonlocal name_pos
    start = name_pos + 1 # omit leading `$`.
    name = match.string[start:end]
    try: charset = unicode_charsets[name]
    except KeyError: fail_parse(line_info, name_pos, f'unknown charset name: {name!r}')
    parser_stack[-1].parse_charset(line_info, name_pos, charset=charset)
    name_pos = None

  escape = False

  for pos in range(start_pos, end_pos):
    c = match.string[pos]
    if pos < start_pos: continue
    parser = parser_stack[-1]

    if escape:
      escape = False
      try: charset = escape_charsets[c]
      except KeyError: fail_parse(line_info, pos, f'invalid escaped character: {c!r}')
      else: parser.parse_charset(line_info, pos, charset)
      continue

    if name_pos is not None:
      if _name_re.match(c):
        continue
      elif c in ' #)]?*+':
        flush_name(line_info, pos) # then proceed to regular parsing below.
      elif c in '\\$([&-^':
        fail_parse(line_info, pos, 'name must be terminated with a space character for readability.')
      else:
        fail_parse(line_info, pos, f'invalid name character: {c!r}')

    if c == '\\':
      escape = True
    elif c == '#':
      end_pos = pos
      break
    elif c == ' ':
      continue
    elif c == '$':
      name_pos = pos
    elif not c.isprintable():
      fail_parse(line_info, pos, f'invalid non-printing character: {c!r}')
    elif c == parser.terminator:
      parser_stack.pop()
      parent = parser_stack[-1]
      parent.receive(parser.finish(line_info, pos))
    else:
      child = parser.parse(line_info, pos, c)
      if child:
        parser_stack.append(child)

  if escape:
    fail_parse(line_info, pos, 'dangling escape character')
  if name_pos is not None:
    flush_name(line_info, end_pos)

  parser = parser_stack.pop()
  if parser_stack:
    fail_parse(line_info, end_pos, f'expected terminator: {parser.terminator!r}')
  rule = parser.finish(line_info, pos)
  rule.pattern = match.string[start_pos:end_pos]
  return rule


def fake_tok(line_info, pos): return (line_info[1], pos)

def fail_parse(line_info, pos, *items):
  'Print a formatted parsing failure to std err and exit.'
  (path, match) = line_info
  pos = match.start() + pos
  exit(msg_for_match(match, prefix=path, msg=''.join(items), pos=pos, end=pos))


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

  def parse(self, line_info, pos, char):
    if char == '(':
      return PatternParser(pos=pos, terminator=')')
    elif char == '[':
      return CharsetParser(pos=pos)
    elif char == '|':
      self.flush_seq(line_info, pos)
    elif char == '?': self.quantity(line_info, pos, char, Opt)
    elif char == '*': self.quantity(line_info, pos, char, Star)
    elif char == '+': self.quantity(line_info, pos, char, Plus)
    else:
      self.seq.append(Charset(token=fake_tok(line_info, pos), ranges=ranges_for_char(char)))

  def parse_charset(self, line_info, pos, charset):
    self.seq.append(Charset(token=fake_tok(line_info, pos), ranges=charset))

  def finish(self, line_info, pos):
    self.flush_seq(line_info, pos)
    choices = self.choices
    return choices[0] if len(choices) == 1 else Choice(token=fake_tok(line_info, self.pos), subs=tuple(choices))

  def flush_seq(self, line_info, pos):
    seq = self.seq
    if not seq: fail_parse(line_info, self.seq_pos, 'empty sequence.')
    rule = seq[0] if len(seq) == 1 else Seq(token=fake_tok(line_info, self.seq_pos), subs=tuple(seq))
    self.choices.append(rule)
    self.seq = []
    self.seq_pos = pos

  def quantity(self, line_info, pos, char, T):
    try: el = self.seq.pop()
    except IndexError: fail_parse(line_info, pos, f"'{char}' does not follow any pattern.")
    else: self.seq.append(T(token=fake_tok(line_info, pos), subs=(el,)))

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
    self.parsed_op = False
    self.parsed_diff_op = False

  def add_code(self, line_info, pos, code):
    if code in self.codes:
      fail_parse(line_info, pos, f'repeated character in set: {ord(code)!r}')
    self.codes.add(code)

  def flush_left(self, line_info, pos, msg_context):
    if not self.codes:
      fail_parse(line_info, pos, 'empty charset preceding ', msg_context)
    op = self.operator
    if op is None: # first operator encountered.
      assert self.codes_left is None
      self.codes_left = self.codes
    elif op == '&': self.codes_left &= self.codes
    elif op == '-': self.codes_left -= self.codes
    elif op == '^': self.codes_left ^= self.codes
    else: raise ValueError(op) # internal error.
    self.codes = set()

  def push_operator(self, line_info, pos, op):
    self.flush_left(line_info, pos, msg_context='operator')
    is_diff_op = self.operator in ('-', '^')
    if self.parsed_diff_op or (self.parsed_op and is_diff_op):
      fail_parse(line_info, pos, 'compound set expressions containing `-` or `^` operators must be grouped with `[...]`: ', op)
    self.parsed_op = True
    self.parsed_diff_op |= is_diff_op
    self.operator = op

  def parse(self, line_info, pos, char):
    if char == '[':
      return CharsetParser(line_info, pos)
    elif char in '&-^':
      self.push_operator(line_info, pos, char)
    else:
      self.add_code(line_info, pos, ord(char))

  def parse_charset(self, line_info, pos, charset):
    for code in codes_for_ranges(charset):
      self.add_code(line_info, pos, code)

  def parse_name(self, line_info, pos, name):
    assert self.current_name_pos is not None
    assert self.current_name_chars is not None
    if not self.current_name_chars:
      fail_parse(line_info, self.current_name_pos, 'empty charset name.')
    name = ''.join(self.current_name_chars)
    try: named_charset = unicode_charsets[name]
    except KeyError: fail_parse(line_info, self.current_name_pos, 'unknown charset name.')
    self.codes.update(codes_for_ranges(named_charset))
    self.current_name_pos = None
    self.current_name_chars = None

  def finish(self, line_info, pos):
    if self.operator: self.flush_left(line_info, pos, msg_context='terminator')
    codes = self.codes_left or self.codes
    if not codes: fail_parse(line_info, self.pos, 'empty character set.')
    return Charset(token=fake_tok(line_info, self.pos), ranges=tuple(ranges_for_codes(sorted(codes))))
