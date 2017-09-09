# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from typing import *
from pithy.iterable import fan_by_key_fn, group_by_heads, OnHeadless
from pithy.buffer import Buffer
from pithy.lex import *
from pithy.io import *

from unico import CodeRange, CodeRanges, codes_for_ranges, ranges_for_codes
from unico.charsets import unicode_charsets

from .rules import *
from .defs import ModeTransitions


Token = Match[str]


lexer = Lexer(flags='x', invalid='invalid', patterns=dict(
  newline = r'\n',
  space   = r'\ +',
  section = r'\#\ *([Pp]atterns|[Mm]odes|[Tt]ransitions)[^\n]*',
  section_invalid = r'\#[^\n]*',
  comment = r'//[^\n]*',
  sym     = r'\w+(?:\w+)?',
  colon   = r':',
  brckt_o = r'\[',
  brckt_c = r'\]',
  #brace_o = r'\{',
  #brace_c = r'\}',
  paren_o = r'\(',
  paren_c = r'\)',
  bar     = r'\|',
  qmark   = r'\?',
  star    = r'\*',
  plus    = r'\+',
  amp     = '&',
  dash    = '-',
  caret   = r'\^',
  ref     = r'\$\w*',
  esc     = r'\\[^\n]', # TODO: list escapable characters.
  char    = r'[^\\\n]',
))

kind_descs = {
  'section_invalid' : 'invalid section',
  'sym'     : 'symbol',
  'colon'   : '`:`',
}

def desc_kind(kind: str) -> str: return kind_descs.get(kind, kind)


def parse_legs(path: str, src: str) -> Tuple[str, Dict[str, Rule], Dict[str, List[str]], ModeTransitions]:
  '''
  Parse the legs source given in `src`,
  returning a dictionary of mode names to rule objects, and a dictionary of mode transitions.
  '''

  tokens_with_comments = list(lexer.lex(src, drop={'space'}))
  # If first token is a comment, assume it is the license.
  license: str
  if tokens_with_comments and tokens_with_comments[0].lastgroup == 'comment':
    license = tokens_with_comments[0].group().strip('# ')
  else:
    license = 'NO LICENSE SPECIFIED.'

  tokens = [t for t in tokens_with_comments if t.lastgroup != 'comment']
  sections = list(group_by_heads(tokens, is_head=is_section, headless=OnHeadless.keep))

  patterns: Dict[str, Rule] = {} # keyed by rule name.
  modes: Dict[str, List[str]] = {} # keyed by mode name.
  transitions: ModeTransitions = {}

  for section in sections:
    buffer = Buffer(section)
    if buffer.peek().lastgroup == 'section':
      section_name = next(buffer)[0].strip('# ').lower()
    else:
      section_name = ''
    if section_name.startswith('modes'):
      parse_modes(path, buffer, patterns.keys(), modes)
    if section_name.startswith('transitions'):
      parse_transitions(path, buffer, patterns.keys(), modes.keys(), transitions)
    else:
      parse_patterns(path, buffer, patterns)

  if not modes:
    modes['main'] = list(patterns)
  return (license, patterns, modes, transitions)


def parse_patterns(path: str, buffer: Buffer[Token], patterns: Dict[str, Rule]) -> None:
  for token in buffer:
    kind = token.lastgroup
    if kind == 'newline': continue
    check_is_sym(path, token, 'rule name symbol')
    name = token[0]
    if name in patterns:
      fail_parse(path, token, f'duplicate rule name: {name!r}.')
    patterns[name] = parse_rule(path, token, buffer)


def parse_modes(path: str, buffer: Buffer[Token], patterns: Container[str], modes: Dict[str, List[str]]) -> None:
  for token in buffer:
    kind = token.lastgroup
    if kind == 'newline': continue
    check_is_sym(path, token, 'mode name')
    name = token[0]
    if name in modes:
      fail_parse(path, token, f'duplicate mode name: {name!r}.')
    consume(path, buffer, kind='colon', subj='mode declaration')
    modes[name] = parse_mode(path, buffer, patterns)


def parse_mode(path: str, buffer: Buffer[Token], patterns: Container[str]) -> List[str]:
  mode: List[str] = []
  for token in buffer:
    kind = token.lastgroup
    if kind == 'newline': return mode
    check_is_sym(path, token, 'rule name')
    name = token[0]
    if name not in patterns: fail_parse(path, token, f'unknown pattern name: {name!r}.')
    mode.append(name)
  return mode


def parse_transitions(path: str, buffer: Buffer[Token], patterns: Container[str],
  modes: Container[str], transitions: ModeTransitions) -> None:

  def check_mode(token: Token) -> None:
    if token[0] not in modes: fail_parse(path, token, f'unknown mode name: {token[0]!r}.')

  def check_pattern(token: Token) -> None:
    if token[0] not in patterns: fail_parse(path, token, f'unknown pattern name: {token[0]!r}.')

  for token in buffer:
    kind = token.lastgroup
    if kind == 'newline': continue
    check_is_sym(path, token, 'expected transition start mode')
    l_mode = token
    check_mode(l_mode)
    l_rule = consume(path, buffer, kind='sym', subj='transition push rule')
    check_pattern(l_rule)
    consume(path, buffer, kind='colon', subj='transition declaration')
    r_mode = consume(path, buffer, kind='sym', subj='transition destination mode')
    check_mode(r_mode)
    r_rule = consume(path, buffer, kind='sym', subj='transition pop rule')
    check_pattern(r_rule)
    consume(path, buffer, kind='newline', subj='transition')
    l = (l_mode[0], l_rule[0])
    r = (r_mode[0], r_rule[0])
    if l in transitions: fail_parse(path, token, f'duplicate transition entry: {l}.')
    transitions[l] = r


def parse_rule(path: str, sym_token: Token, buffer: Buffer[Token]) -> Rule:
  assert sym_token.lastgroup == 'sym'
  if buffer.peek().lastgroup == 'colon': # named rule.
    next(buffer)
    return parse_rule_pattern(path, buffer, terminator='newline')
  else:
    consume(path, buffer, kind='newline', subj='literal symbol rule')
    text = sym_token[0]
    return Seq.of_iter(Charset.for_char(c) for c in text)


def parse_rule_pattern(path: str, buffer: Buffer[Token], terminator: str) -> Rule:
  'Parse a pattern and return a Rule object.'
  els: List[Rule] = []
  def finish() -> Rule: return Seq.of_iter(els)
  for token in buffer:
    kind = token.lastgroup
    def _fail(msg) -> 'NoReturn': fail_parse(path, token, msg)
    def quantity(rule_type: Type[Rule]) -> None:
      if not els: _fail('quantity operator must be preceded by a pattern.')
      els[-1] = rule_type(els[-1])
    if kind == terminator: return finish()
    elif kind == 'paren_o': els.append(parse_rule_pattern(path, buffer, terminator='paren_c'))
    elif kind == 'brckt_o': els.append(Charset(ranges=tuple(ranges_for_codes(sorted(parse_charset(path, buffer, token))))))
    elif kind == 'bar': return parse_choice(path, buffer, left=finish(), terminator=terminator)
    elif kind == 'qmark':   quantity(Opt)
    elif kind == 'star':  quantity(Star)
    elif kind == 'plus':  quantity(Plus)
    elif kind == 'esc': els.append(Charset(ranges=ranges_for_code(parse_esc(path, token))))
    elif kind == 'ref': els.append(Charset(ranges=parse_ref(path, token)))
    elif kind == 'sym': els.extend(Charset.for_char(c) for c in token[0])
    elif kind in ('colon', 'amp', 'dash', 'caret', 'char'):
      els.append(Charset.for_char(token[0]))
    elif kind == 'invalid': _fail('invalid pattern token.')
    else: _fail(f'unexpected pattern token: {desc_kind(kind)}.')
  return finish()


def parse_choice(path: str, buffer: Buffer[Token], left: Rule, terminator: str) -> Rule:
  return Choice(left, parse_rule_pattern(path, buffer, terminator=terminator))


def parse_esc(path: str, token: Token) -> int:
  char = token[0][1]
  try: code = escape_codes[char]
  except KeyError: fail_parse(path, token, f'invalid escaped character: {char!r}.')
  return code


def ranges_for_code(code: int) -> CodeRanges: return ((code, code+1),)


def parse_ref(path: str, token: Token) -> CodeRanges:
  try: return unicode_charsets[token[0][1:]]
  except KeyError: fail_parse(path, token, 'unknown charset name.')


def parse_charset(path: str, buffer: Buffer[Token], start_token: Token, is_right=False, is_diff=False) -> Set[int]:
  '''
  The Legs character set syntax is different from traditional regular expressions.
  * `[...]` introduces a nested character set.
  * `&` binary operator: set intersection.
  * `-` binary operator: set difference.
  * `^` binary operator: set symmetric difference.
  Multiple intersection operators can be chained together,
  but if a difference or symmetric difference operator is used,
  it must be the only operator to appear within the character set;
  more complex expressions must be explicitly grouped.
  Thus, the set expression syntax has no operator precedence or associativity.
  '''
  codes: Set[int] = set()

  def add_code(token: Token, code: int) -> None:
    if code in codes:
      fail_parse(path, token, f'repeated character in set: {code!r}.')
    codes.add(code)

  def parse_right(token: Token, is_diff_op: bool) -> Set[int]:
    if not codes:
      fail_parse(path, token, f'empty charset preceding operator.')
    if is_diff or (is_right and is_diff_op):
      fail_parse(path, token, f'compound set expressions containing `-` or `^` operators must be grouped with `[...]`.')
    return parse_charset(path, buffer, token, is_right=True, is_diff=is_diff_op)

  def finish() -> Set[int]:
      if not codes: fail_parse(path, start_token, 'empty character set.')
      return codes

  for token in buffer:
    kind = token.lastgroup
    if kind == 'brckt_c':
      return finish()
    if kind == 'brckt_o':
      for code in parse_charset(path, buffer, token):
        add_code(token, code)
    elif kind == 'ref':
      for code in codes_for_ranges(parse_ref(path, token)):
        add_code(token, code)
    elif kind == 'amp':
      codes.intersection_update(parse_right(token, is_diff_op=False))
      return finish()
    elif kind == 'dash':
      codes.difference_update(parse_right(token, is_diff_op=True))
      return finish()
    elif kind == 'caret':
      codes.symmetric_difference_update(parse_right(token, is_diff_op=True))
      return finish()
    elif kind == 'esc':
      add_code(token, parse_esc(path, token))
    elif kind == 'sym':
      for char in token[0]:
        add_code(token, ord(char))
    elif kind in ('char', 'colon', 'bar', 'qmark', 'star', 'plus', 'paren_o', 'paren_c'):
      add_code(token, ord(token[0]))
    elif kind == 'invalid': fail_parse(path, token, 'invalid pattern token.')
    else: fail_parse(path, token, f'unexpected charset token: {desc_kind(kind)}.')
  fail_parse(path, start_token, 'unterminated charset.')


def consume(path: str, buffer: Buffer[Token], kind: str, subj: str) -> Token:
  token: Token = next(buffer)
  act = token.lastgroup
  if act != kind: fail_parse(path, token, f'{subj} expected {desc_kind(kind)}; found {desc_kind(act)}.')
  return token


def check_is_sym(path: str, token: Token, expectation: str) -> None:
  kind = token.lastgroup
  if kind != 'sym':
    fail_parse(path, token, f'expected {expectation}; found {desc_kind(kind)}.')
  if token[0] in reserved_names:
    fail_parse(path, token, f'rule name is reserved: {token[0]!r}.')

reserved_names = { 'invalid', 'incomplete' }


def is_section(token: Token) -> bool: return token.lastgroup == 'section'


escape_codes: Dict[str, int] = {
  'n': ord('\n'),
  's': ord(' '), # nonstandard space escape.
  't': ord('\t'),
}
escape_codes.update((c, ord(c)) for c in '\\#|$?*+()[]&-^:/')

if False:
  for k, v in sorted(escape_codes.items()):
    errL(f'{k}: {v!r}')

