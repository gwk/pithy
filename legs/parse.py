# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from pithy.iterable import fan_by_key_fn, group_by_heads, OnHeadless
from pithy.lex import *
from pithy.io import *

from unico import codes_for_ranges, ranges_for_codes
from unico.charsets import unicode_charsets

from legs.rules import *


lexer = Lexer('x',
  comment     = r'\s* \# [^\n]* \n?',
  transition  = r'\s* % \s+ (?P<l_name> \w+ (\.\w+)? ) \s+ (?P<r_name> \w+ (\.\w+)? ) \s* (\#[^\n]*)? \n?',
  rule        = r'\s* (?P<name> \w+ (\.\w+)? ) \s* : \s* (?P<pattern> [^\n]*) \n?',
  symbol      = r'\s* (?P<sym_name>\w+) \n?',
)


def parse_legs(path, src):
  '''
  Parse the legs source given in `src`,
  returning a dictionary of mode names to rule objects, and a dictionary of mode transitions.
  '''
  rules = {} # keyed by name.
  simple_names = {}
  mode_transitions = {}
  for match in lexer.lex(src, drop={'comment'}):
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
    name = match['sym_name']
    span = match.span('sym_name')
  return name, parse_rule_pattern(path, match=match, span=span)


_name_re = re.compile(r'\w')

def parse_rule_pattern(path, match, span):
  'Parse a pattern and return a Rule object.'
  line_info = (path, match)
  start_col, end_col = span
  parser_stack = [PatternParser(col=start_col)]
  # stack of parsers, one for each open nesting syntactic element: root, '(…)', or '[…]'.

  name_col = None # position of name currently being parsed or None.
  def flush_name(line_info, end):
    nonlocal name_col
    start = name_col + 1 # omit leading `$`.
    name = match.string[start:end]
    try: charset = unicode_charsets[name]
    except KeyError: fail_parse(line_info, name_col, f'unknown charset name: {name!r}')
    parser_stack[-1].parse_charset(line_info, name_col, charset=charset)
    name_col = None

  escape = False

  for col in range(start_col, end_col):
    c = match.string[col]
    if col < start_col: continue
    parser = parser_stack[-1]

    if escape:
      escape = False
      try: charset = escape_charsets[c]
      except KeyError: fail_parse(line_info, col, f'invalid escaped character: {c!r}')
      else: parser.parse_charset(line_info, col, charset)
      continue

    if name_col is not None:
      if _name_re.match(c):
        continue
      elif c in ' #)]?*+':
        flush_name(line_info, col) # then proceed to regular parsing below.
      elif c in '\\$([&-^':
        fail_parse(line_info, col, 'name must be terminated with a space character for readability.')
      else:
        fail_parse(line_info, col, f'invalid name character: {c!r}')

    if c == '\\':
      escape = True
    elif c == '#':
      end_col = col
      break
    elif c == ' ':
      continue
    elif c == '$':
      name_col = col
    elif not c.isprintable():
      fail_parse(line_info, col, f'invalid non-printing character: {c!r}')
    elif c == parser.terminator:
      parser_stack.pop()
      parent = parser_stack[-1]
      parent.receive(parser.finish(line_info, col))
    else:
      child = parser.parse(line_info, col, c)
      if child:
        parser_stack.append(child)

  if escape:
    fail_parse(line_info, col, 'dangling escape character')
  if name_col is not None:
    flush_name(line_info, end_col)

  parser = parser_stack.pop()
  if parser_stack:
    fail_parse(line_info, end_col, f'expected terminator: {parser.terminator!r}')
  rule = parser.finish(line_info, col)
  rule.pattern = match.string[start_col:end_col]
  return rule


def fake_tok(line_info, col): return (line_info[1], col)

def fail_parse(line_info, col, *items):
  'Print a formatted parsing failure to std err and exit.'
  (path, match) = line_info
  pos = match.start() + col
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

  def __init__(self, col, terminator=None):
    self.col = col
    self.terminator = terminator
    self.choices = []
    self.seq = []
    self.seq_col = col

  def parse(self, line_info, col, char):
    if char == '(':
      return PatternParser(col=col, terminator=')')
    elif char == '[':
      return CharsetParser(col=col)
    elif char == '|':
      self.flush_seq(line_info, col)
    elif char == '?': self.quantity(line_info, col, char, Opt)
    elif char == '*': self.quantity(line_info, col, char, Star)
    elif char == '+': self.quantity(line_info, col, char, Plus)
    else:
      self.seq.append(Charset(token=fake_tok(line_info, col), ranges=ranges_for_char(char)))

  def parse_charset(self, line_info, col, charset):
    self.seq.append(Charset(token=fake_tok(line_info, col), ranges=charset))

  def finish(self, line_info, col):
    self.flush_seq(line_info, col)
    choices = self.choices
    return choices[0] if len(choices) == 1 else Choice(token=fake_tok(line_info, self.col), subs=tuple(choices))

  def flush_seq(self, line_info, col):
    seq = self.seq
    if not seq: fail_parse(line_info, self.seq_col, 'empty sequence.')
    rule = seq[0] if len(seq) == 1 else Seq(token=fake_tok(line_info, self.seq_col), subs=tuple(seq))
    self.choices.append(rule)
    self.seq = []
    self.seq_col = col

  def quantity(self, line_info, col, char, T):
    try: el = self.seq.pop()
    except IndexError: fail_parse(line_info, col, f"'{char}' does not follow any pattern.")
    else: self.seq.append(T(token=fake_tok(line_info, col), subs=(el,)))

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

  def __init__(self, col):
    self.col = col
    self.terminator = ']'
    self.codes = set()
    self.codes_left = None  # left operand to current operator.
    self.operator = None # current operator waiting to finish parsing right side.
    self.parsed_op = False
    self.parsed_diff_op = False

  def add_code(self, line_info, col, code):
    if code in self.codes:
      fail_parse(line_info, col, f'repeated character in set: {ord(code)!r}')
    self.codes.add(code)

  def flush_left(self, line_info, col, msg_context):
    if not self.codes:
      fail_parse(line_info, col, 'empty charset preceding ', msg_context)
    op = self.operator
    if op is None: # first operator encountered.
      assert self.codes_left is None
      self.codes_left = self.codes
    elif op == '&': self.codes_left &= self.codes
    elif op == '-': self.codes_left -= self.codes
    elif op == '^': self.codes_left ^= self.codes
    else: raise ValueError(op) # internal error.
    self.codes = set()

  def push_operator(self, line_info, col, op):
    self.flush_left(line_info, col, msg_context='operator')
    is_diff_op = self.operator in ('-', '^')
    if self.parsed_diff_op or (self.parsed_op and is_diff_op):
      fail_parse(line_info, col, 'compound set expressions containing `-` or `^` operators must be grouped with `[...]`: ', op)
    self.parsed_op = True
    self.parsed_diff_op |= is_diff_op
    self.operator = op

  def parse(self, line_info, col, char):
    if char == '[':
      return CharsetParser(line_info, col)
    elif char in '&-^':
      self.push_operator(line_info, col, char)
    else:
      self.add_code(line_info, col, ord(char))

  def parse_charset(self, line_info, col, charset):
    for code in codes_for_ranges(charset):
      self.add_code(line_info, col, code)

  def parse_name(self, line_info, col, name):
    assert self.current_name_col is not None
    assert self.current_name_chars is not None
    if not self.current_name_chars:
      fail_parse(line_info, self.current_name_col, 'empty charset name.')
    name = ''.join(self.current_name_chars)
    try: named_charset = unicode_charsets[name]
    except KeyError: fail_parse(line_info, self.current_name_col, 'unknown charset name.')
    self.codes.update(codes_for_ranges(named_charset))
    self.current_name_col = None
    self.current_name_chars = None

  def finish(self, line_info, col):
    if self.operator: self.flush_left(line_info, col, msg_context='terminator')
    codes = self.codes_left or self.codes
    if not codes: fail_parse(line_info, self.col, 'empty character set.')
    return Charset(token=fake_tok(line_info, self.col), ranges=tuple(ranges_for_codes(sorted(codes))))
