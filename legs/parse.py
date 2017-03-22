# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from pithy.iterable import fan_by_key_fn, group_by_heads, OnHeadless
from pithy.buffer import Buffer
from pithy.lex import *
from pithy.io import *

from unico import codes_for_ranges, ranges_for_codes
from unico.charsets import unicode_charsets

from legs.rules import *


lexer = Lexer('x',
  patterns=dict(
    line    = r'\n',
    space   = r'\ +',
    comment = r'\# [^\n]*',
    sym     = r'\w+(?:\.\w+)?',
    colon   = r':',
    percent = r'%',
    pat     = r'[^\n]*',
  ),
  modes=dict(
    main={
      'line',
      'space',
      'comment',
      'sym',
      'colon',
      'percent'
    },
    pattern={
      'line',
      'pat',
    }
  ),
  transitions={
    ('main', 'colon') : ('pattern', 'line')
  }
)

kind_descs = {
  'line'    : 'terminating newline',
  'space'   : 'space',
  'comment' : 'comment',
  'sym'     : 'symbol',
  'colon'   : '`:`',
  'percent' : '`%`',
  'pat'     : 'pattern',
}


def parse_legs(path, src):
  '''
  Parse the legs source given in `src`,
  returning a dictionary of mode names to rule objects, and a dictionary of mode transitions.
  '''
  rules = {} # keyed by name.
  simple_names = {}
  mode_transitions = {}
  buffer = Buffer(lexer.lex(src, drop={'space', 'comment'}))
  for token in buffer:
    line_info = (path, token)
    kind = token.lastgroup
    if kind == 'line':
      continue
    if kind == 'percent':
      (src_pair, dst_pair) = parse_mode_transition(path, buffer)
      if src_pair in mode_transitions:
        fail_parse(line_info, f'duplicate transition parent name: {src_pair[1]!r}')
      mode_transitions[src_pair] = dst_pair
    elif kind == 'sym':
      name = token[0]
      rule = parse_rule(path, token, buffer)
      if name in ('invalid', 'incomplete'):
        fail_parse(line_info, f'rule name is reserved: {name!r}')
      if name in rules:
        fail_parse(line_info, f'duplicate rule name: {name!r}')
      rules[name] = rule
      for simple in simplified_names(name):
        if simple in simple_names:
          fail_parse(line_info, f'rule name collides when simplified: {simple_names[simple]!r}')
        simple_names[simple] = name
    else:
      fail_parse(path, token, f'expected transition or rule.')
  mode_named_rules = fan_by_key_fn(rules.items(), key=lambda item: mode_for_name(item[0]))
  mode_named_rules.setdefault('main', [])
  return (mode_named_rules, mode_transitions)



def consume(path, buffer, kind, subj):
  token = next(buffer)
  act = token.lastgroup
  if act != kind: fail_parse((path, token), f'{subj} expected {kind_descs[kind]}; received {kind_descs[act]}.')
  return token


def parse_mode_transition(path, buffer):
  l = mode_and_name(consume(path, buffer, 'sym', 'transition entry'))
  r = mode_and_name(consume(path, buffer, 'sym', 'transition exit'))
  consume(path, buffer, 'line', 'transition')
  return (l, r)


def mode_and_name(token):
  name = token[0]
  return mode_for_name(name), name


def mode_for_name(name):
  mode, _, _ = name.rpartition('.')
  return (mode or 'main')


def simplified_names(name):
  n = name.lower()
  return { n.replace('.', '_'), n.replace('.', '') }


def parse_rule(path, sym_token, buffer):
  assert sym_token.lastgroup == 'sym'
  if buffer.peek().lastgroup == 'colon': # named rule.
    next(buffer)
    pattern_token = consume(path, buffer, 'pat', 'rule')
  else:
    pattern_token = sym_token
  consume(path, buffer, 'line', 'rule')
  return parse_rule_pattern(path, token=pattern_token)


_name_re = re.compile(r'\w')

def parse_rule_pattern(path, token):
  'Parse a pattern and return a Rule object.'
  line_info = (path, token)
  start_pos, end_pos = token.span()
  parser_stack = [PatternParser(pos=start_pos)]
  # stack of parsers, one for each open nesting syntactic element: root, '(…)', or '[…]'.

  name_pos = None # position of name currently being parsed or None.
  def flush_name(line_info, end):
    nonlocal name_pos
    start = name_pos + 1 # omit leading `$`.
    name = token.string[start:end]
    try: charset = unicode_charsets[name]
    except KeyError: fail_parse(line_info, f'unknown charset name: {name!r}', pos=name_pos)
    parser_stack[-1].parse_charset(line_info, name_pos, charset=charset)
    name_pos = None

  escape = False

  for pos in range(start_pos, end_pos):
    c = token.string[pos]
    if pos < start_pos: continue
    parser = parser_stack[-1]

    def _fail(msg): fail_parse(line_info, msg, pos=pos)

    if escape:
      escape = False
      try: charset = escape_charsets[c]
      except KeyError: _fail(f'invalid escaped character: {c!r}')
      else: parser.parse_charset(line_info, pos, charset)
      continue

    if name_pos is not None:
      if _name_re.match(c):
        continue
      elif c in ' #)]?*+':
        flush_name(line_info, pos) # then proceed to regular parsing below.
      elif c in '\\$([&-^':
        _fail('name must be terminated with a space character for readability.')
      else:
        _fail(f'invalid name character: {c!r}')

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
      _fail(f'invalid non-printing character: {c!r}')
    elif c == parser.terminator:
      parser_stack.pop()
      parent = parser_stack[-1]
      parent.receive(parser.finish(line_info, pos))
    else:
      child = parser.parse(line_info, pos, c)
      if child:
        parser_stack.append(child)

  if escape:
    fail_parse(line_info, 'dangling escape character', pos=pos)
  if name_pos is not None:
    flush_name(line_info, end_pos)

  parser = parser_stack.pop()
  if parser_stack:
    fail_parse(line_info, f'expected terminator: {parser.terminator!r}', pos=end_pos)
  rule = parser.finish(line_info, pos)
  rule.pattern = token[0]
  return rule


def fake_tok(line_info, pos): return (line_info[1], pos)

def fail_parse(line_info, *items, pos=None):
  'Print a formatted parsing failure to std err and exit.'
  (path, token) = line_info
  exit(msg_for_match(token, prefix=path, msg=''.join(items), pos=pos, end=pos))


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
    if not seq: fail_parse(line_info, 'empty sequence.', pos=self.seq_pos)
    rule = seq[0] if len(seq) == 1 else Seq(token=fake_tok(line_info, self.seq_pos), subs=tuple(seq))
    self.choices.append(rule)
    self.seq = []
    self.seq_pos = pos

  def quantity(self, line_info, pos, char, T):
    try: el = self.seq.pop()
    except IndexError: fail_parse(line_info, f"'{char}' does not follow any pattern.", pos=pos)
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
      fail_parse(line_info, f'repeated character in set: {ord(code)!r}', pos=pos)
    self.codes.add(code)

  def flush_left(self, line_info, pos, msg_context):
    if not self.codes:
      fail_parse(line_info, 'empty charset preceding ', msg_context, pos=pos)
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
      fail_parse(line_info, 'compound set expressions containing `-` or `^` operators must be grouped with `[...]`: ', op, pos=pos)
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
      fail_parse(line_info, 'empty charset name.', pos=self.current_name_pos)
    name = ''.join(self.current_name_chars)
    try: named_charset = unicode_charsets[name]
    except KeyError: fail_parse(line_info, 'unknown charset name.', pos=pos)
    self.codes.update(codes_for_ranges(named_charset))
    self.current_name_pos = None
    self.current_name_chars = None

  def finish(self, line_info, pos):
    if self.operator: self.flush_left(line_info, pos, msg_context='terminator')
    codes = self.codes_left or self.codes
    if not codes: fail_parse(line_info, 'empty character set.', pos=self.pos)
    return Charset(token=fake_tok(line_info, self.pos), ranges=tuple(ranges_for_codes(sorted(codes))))
