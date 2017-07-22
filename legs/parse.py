# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from typing import *
from pithy.iterable import fan_by_key_fn
from pithy.buffer import Buffer
from pithy.lex import *
from pithy.io import *

from unico import CodeRange, CodeRanges, codes_for_ranges, ranges_for_codes
from unico.charsets import unicode_charsets

from .rules import *
from .defs import ModeTransitions


Token = Match[str]


lexer = Lexer(flags='x', invalid='inv',
  patterns=dict(
    line    = r'\n',
    space   = r'\ +',
    comment = r'\# [^\n]*',
    sym     = r'\w+(?:\.\w+)?',
    colon   = r':',
    percent = r'%',

    pat_brckt_o = r'\[',
    pat_brckt_c = r'\]',
    #pat_brace_o = r'\{',
    #pat_brace_c = r'\}',
    pat_paren_o = r'\(',
    pat_paren_c = r'\)',
    pat_bar     = r'\|',
    pat_opt     = r'\?',
    pat_star    = r'\*',
    pat_plus    = r'\+',
    pat_amp     = '&',
    pat_dash    = '-',
    pat_caret   = r'\^',
    pat_ref     = r'\$\w*',
    pat_esc     = r'\\.',
    pat_char    = r'[^\\\n]',
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
      'space',
      'pat_.*',
    }
  ),
  transitions={
    ('main', 'colon') : ('pattern', 'line')
  }
)

kind_descs = {
  'inv'     : 'invalid',
  'line'    : 'terminating newline',
  'sym'     : 'symbol',
  'colon'   : '`:`',
  'percent' : '`%`',
  'pat'     : 'pattern',
}

def desc_kind(kind: str) -> str: return kind_descs.get(kind, kind)


def parse_legs(path: str, src: str) -> Tuple[str, Dict[str, List[Tuple[str, Rule]]], ModeTransitions]:
  '''
  Parse the legs source given in `src`,
  returning a dictionary of mode names to rule objects, and a dictionary of mode transitions.
  '''
  rules: Dict[str, Rule] = {} # keyed by name.
  simple_names: Dict[str, str] = {}
  mode_transitions: ModeTransitions = {}
  tokens = list(lexer.lex(src, drop={'space'}))
  # If first token (first line) is a comment, assume it is the license.
  license: str
  if tokens and tokens[0].lastgroup == 'comment':
    license = tokens[0].group().strip('# ')
  else:
    license = 'NO LICENSE SPECIFIED.'
  buffer = Buffer([t for t in tokens if t.lastgroup != 'comment'])
  for token in buffer:
    kind = token.lastgroup
    if kind == 'line':
      continue
    if kind == 'percent':
      (src_pair, dst_pair) = parse_mode_transition(path, buffer)
      if src_pair in mode_transitions:
        fail_parse(path, token, f'duplicate transition parent name: {src_pair[1]!r}')
      mode_transitions[src_pair] = dst_pair
    elif kind == 'sym':
      name = token[0]
      rule = parse_rule(path, token, buffer)
      if name in ('invalid', 'incomplete'):
        fail_parse(path, token, f'rule name is reserved: {name!r}')
      if name in rules:
        fail_parse(path, token, f'duplicate rule name: {name!r}')
      rules[name] = rule
      for simple in simplified_names(name):
        if simple in simple_names:
          fail_parse(path, token, f'rule name collides when simplified; previous rule: {simple_names[simple]!r}')
        simple_names[simple] = name
    else:
      fail_parse(path, token, f'expected transition or rule.')
  mode_named_rules = fan_by_key_fn(rules.items(), key=lambda item: mode_for_name(item[0])) # type: ignore # mypy bug?
  mode_named_rules.setdefault('main', [])
  return (license, mode_named_rules, mode_transitions)



def consume(path: str, buffer: Buffer[Token], kind: str, subj: str) -> Token:
  token: Token = next(buffer)
  act = token.lastgroup
  if act != kind: fail_parse(path, token, f'{subj} expected {desc_kind(kind)}; received {desc_kind(act)}.')
  return token


def parse_mode_transition(path: str, buffer: Buffer[Token]) -> Tuple[Tuple[str, str], Tuple[str, str]]:
  l = mode_and_name(consume(path, buffer, kind='sym', subj='transition entry'))
  r = mode_and_name(consume(path, buffer, kind='sym', subj='transition exit'))
  consume(path, buffer, kind='line', subj='transition')
  return (l, r)


def mode_and_name(token: Token) -> Tuple[str, str]:
  name = token[0]
  return (mode_for_name(name), name)


def mode_for_name(name: str) -> str:
  mode, _, _ = name.rpartition('.')
  return (mode or 'main')


def simplified_names(name: str) -> Set[str]:
  n = name.lower()
  return {n.replace('.', '_'), n.replace('.', '')}


def parse_rule(path: str, sym_token: Token, buffer: Buffer[Token]) -> Rule:
  assert sym_token.lastgroup == 'sym'
  if buffer.peek().lastgroup == 'colon': # named rule.
    next(buffer)
    return parse_rule_pattern(path, buffer, terminator='line')
  else:
    consume(path, buffer, kind='line', subj='unnamed rule')
    text = sym_token[0]
    return Seq.for_subs(Charset.for_char(c) for c in text)


def parse_rule_pattern(path: str, buffer: Buffer[Token], terminator: str) -> Rule:
  # 'Parse a pattern and return a Rule object.'
  els: List[Rule] = []
  def finish() -> Rule: return Seq.for_subs(els)
  for token in buffer:
    kind = token.lastgroup
    def _fail(msg) -> 'NoReturn': fail_parse(path, token, msg)
    def quantity(rule_type: Type[Rule]) -> None:
      if not els: _fail('quantity operator must be preceded by a pattern')
      els[-1] = rule_type(subs=(els[-1],))
    if kind == terminator: return finish()
    elif kind == 'pat_paren_o': els.append(parse_rule_pattern(path, buffer, terminator='pat_paren_c'))
    elif kind == 'pat_brckt_o': els.append(Charset(ranges=tuple(ranges_for_codes(sorted(parse_charset(path, buffer, token))))))
    elif kind == 'pat_bar': return parse_choice(path, buffer, left=finish(), terminator=terminator)
    elif kind == 'pat_opt':   quantity(Opt)
    elif kind == 'pat_star':  quantity(Star)
    elif kind == 'pat_plus':  quantity(Plus)
    elif kind == 'pat_esc': els.append(Charset(ranges=ranges_for_code(parse_esc(path, token))))
    elif kind == 'pat_ref': els.append(Charset(ranges=parse_ref(path, token)))
    elif kind in ('pat_amp', 'pat_dash', 'pat_caret', 'pat_char'):
      els.append(Charset.for_char(token[0]))
    elif kind == 'inv': _fail(f'invalid pattern token')
    else: _fail(f'unexpected pattern token: {desc_kind(kind)}')
  return finish()


def parse_choice(path: str, buffer: Buffer[Token], left: Rule, terminator: str) -> Rule:
  return Choice(subs=(left, parse_rule_pattern(path, buffer, terminator=terminator)))


def parse_esc(path: str, token: Token) -> int:
  char = token[0][1]
  try: code = escape_codes[char]
  except KeyError: fail_parse(path, token, f'invalid escaped character: {char!r}')
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
      fail_parse(path, token, f'repeated character in set: {code!r}')
    codes.add(code)

  def parse_right(token: Token, is_diff_op: bool) -> Set[int]:
    if not codes:
      fail_parse(path, token, f'empty charset preceding operator')
    if is_diff or (is_right and is_diff_op):
      fail_parse(path, token, f'compound set expressions containing `-` or `^` operators must be grouped with `[...]`')
    return parse_charset(path, buffer, token, is_right=True, is_diff=is_diff_op)

  def finish() -> Set[int]:
      if not codes: fail_parse(path, start_token, 'empty character set.')
      return codes

  for token in buffer:
    kind = token.lastgroup
    if kind == 'pat_brckt_c':
      return finish()
    if kind == 'pat_brckt_o':
      for code in parse_charset(path, buffer, token):
        add_code(token, code)
    elif kind == 'pat_ref':
      for code in codes_for_ranges(parse_ref(path, token)):
        add_code(token, code)
    elif kind == 'pat_amp':
      codes.intersection_update(parse_right(token, is_diff_op=False))
      return finish()
    elif kind == 'pat_dash':
      codes.difference_update(parse_right(token, is_diff_op=True))
      return finish()
    elif kind == 'pat_caret':
      codes.symmetric_difference_update(parse_right(token, is_diff_op=True))
      return finish()
    elif kind == 'pat_esc':
      add_code(token, parse_esc(path, token))
    elif kind in ('pat_char', 'pat_bar', 'pat_opt', 'pat_star', 'pat_plus', 'pat_paren_o', 'pat_paren_c'):
      add_code(token, ord(token[0]))
    elif kind == 'inv': fail_parse(path, token, 'invalid pattern token')
    else: fail_parse(path, token, f'unexpected charset token: {desc_kind(kind)}')
  fail_parse(path, start_token, 'unterminated charset.')



def fail_parse(path: str, token: Token, msg: str) -> 'NoReturn':
  'Print a formatted parsing failure to std err and exit.'
  exit(msg_for_match(token, prefix=path, msg=msg))


escape_codes: Dict[str, int] = {
  'n': ord('\n'),
  's': ord(' '), # nonstandard space escape.
  't': ord('\t'),
}
escape_codes.update((c, ord(c)) for c in '\\#|$?*+()[]&-^')

if False:
  for k, v in sorted(escape_codes.items()):
    errL(f'{k}: {v!r}')

