# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from typing import Container, Dict, FrozenSet, List, Match, NoReturn, Set, Tuple, Type

from pithy.buffer import Buffer
from pithy.io import *
from pithy.iterable import OnHeadless, fan_by_key_fn, group_by_heads
from pithy.lex import Lexer
from pithy.unicode import CodeRange, CodeRanges, codes_for_ranges, ranges_for_codes
from pithy.unicode.charsets import unicode_charsets
from tolkien import Source, Token

from .defs import ModeTransitions
from .patterns import *


lexer = Lexer(flags='x', invalid='invalid', patterns=dict(
  newline = r'\n',
  space   = r'\ +',
  section = r'\#\ *([Pp]atterns|[Mm]odes|[Tt]ransitions)[^\n]*',
  section_invalid = r'\#[^\n]*',
  comment = r'//[^\n]*',
  sym     = r'\w+',
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

def desc_kind(kind:str) -> str: return kind_descs.get(kind, kind)


def parse_legs(path:str, text:str) -> Tuple[str,Dict[str,LegsPattern],Dict[str,FrozenSet[str]],ModeTransitions]:
  '''
  Parse the legs source given in `text`, returning:
  * the license string;
  * a dictionary of pattern names to LegsPattern objects;
  * a dictionary of mode names to pattern names;
  * a dictionary of mode transitions.
  '''
  source = Source(name=path, text=text)
  tokens_with_comments = list(lexer.lex(source, drop={'space'}))
  # If first token is a comment, assume it is the license.
  license:str
  if tokens_with_comments and tokens_with_comments[0].kind == 'comment':
    license = source[tokens_with_comments[0]].strip('/ ')
  else:
    license = 'NO LICENSE SPECIFIED.'

  tokens = [t for t in tokens_with_comments if t.kind != 'comment']
  sections = list(group_by_heads(tokens, is_head=is_section, headless=OnHeadless.keep))

  patterns:Dict[str, LegsPattern] = {} # keyed by pattern name.
  mode_pattern_kinds:Dict[str,FrozenSet[str]] = {} # keyed by mode name.
  mode_transitions:ModeTransitions = {}

  for section in sections:
    buffer = Buffer(section)
    if buffer.peek().kind == 'section':
      section_name = source[next(buffer)].strip('# ').lower()
    else:
      section_name = ''
    if not section_name or section_name.startswith('patterns'):
      parse_patterns(source, buffer, patterns)
    elif section_name.startswith('modes'):
      parse_modes(source, buffer, patterns.keys(), mode_pattern_kinds)
    elif section_name.startswith('transitions'):
      parse_transitions(source, buffer, patterns.keys(), mode_pattern_kinds.keys(), mode_transitions)
    else:
      source.fail(buffer.peek(), f'bad section name: {section_name!r}.')

  if not mode_pattern_kinds:
    mode_pattern_kinds['main'] = frozenset(patterns)
  return (license, patterns, mode_pattern_kinds, mode_transitions)


def parse_patterns(source:Source[str], buffer:Buffer[Token], patterns:Dict[str, LegsPattern]) -> None:
  for token in buffer:
    kind = token.kind
    if kind == 'newline': continue
    check_is_sym(source, token, 'pattern name symbol')
    name = source[token]
    if name in patterns:
      source.fail(token, f'duplicate pattern name: {name!r}.')
    patterns[name] = parse_pattern(source, token, buffer)


def parse_modes(source:Source[str], buffer:Buffer[Token], patterns:Container[str],
 mode_pattern_kinds:Dict[str,FrozenSet[str]]) -> None:
  for token in buffer:
    kind = token.kind
    if kind == 'newline': continue
    check_is_sym(source, token, 'mode name')
    name = source[token]
    if name in mode_pattern_kinds:
      source.fail(token, f'duplicate mode name: {name!r}.')
    consume(source, buffer, kind='colon', subj='mode declaration')
    mode_pattern_kinds[name] = parse_mode(source, buffer, patterns)


def parse_mode(source:Source[str], buffer:Buffer[Token], patterns:Container[str]) -> FrozenSet[str]:
  names:Set[str] = set()
  for token in buffer:
    kind = token.kind
    if kind == 'newline': break
    check_is_sym(source, token, 'pattern name')
    name = source[token]
    if name not in patterns: source.fail(token, f'unknown pattern name: {name!r}.')
    if name in names: source.fail(token, f'duplicate pattern name: {name!r}.')
    names.add(name)
  return frozenset(names)


def parse_transitions(source:Source[str], buffer:Buffer[Token], patterns:Container[str],
  modes:Container[str], transitions:ModeTransitions) -> None:

  def check_mode(token:Token) -> None:
    s = source[token]
    if s not in modes: source.fail(token, f'unknown mode name: {s!r}.')

  def check_pattern(token:Token) -> None:
    s = source[token]
    if s not in patterns: source.fail(token, f'unknown pattern name: {s!r}.')

  for token in buffer:
    kind = token.kind
    if kind == 'newline': continue
    check_is_sym(source, token, 'expected transition start mode')
    l_mode = token
    check_mode(l_mode)
    l_pattern = consume(source, buffer, kind='sym', subj='transition push pattern')
    check_pattern(l_pattern)
    consume(source, buffer, kind='colon', subj='transition declaration')
    r_mode = consume(source, buffer, kind='sym', subj='transition destination mode')
    check_mode(r_mode)
    r_pattern = consume(source, buffer, kind='sym', subj='transition pop pattern')
    check_pattern(r_pattern)
    consume(source, buffer, kind='newline', subj='transition')
    lm = source[l_mode]
    lp = source[l_pattern]
    r = (source[r_mode], source[r_pattern])
    if lm not in transitions: transitions[lm] = {}
    if lp in transitions[lm]: source.fail(token, f'duplicate transition entry: {lm}, {lp}.')
    transitions[lm][lp] = r


def parse_pattern(source:Source[str], sym_token:Token, buffer:Buffer[Token]) -> LegsPattern:
  assert sym_token.kind == 'sym'
  try: next_token = buffer.peek()
  except StopIteration: pass
  else:
    if next_token.kind != 'newline': # named pattern.
      consume(source, buffer, kind='colon', subj='pattern')
      return parse_pattern_pattern(source, buffer, terminator='newline')
  # literal symbol pattern.
  text = source[sym_token]
  return Seq.from_list([Charset.for_char(c) for c in text])


def parse_pattern_pattern(source:Source[str], buffer:Buffer[Token], terminator:str) -> LegsPattern:
  'Parse a pattern and return a LegsPattern object.'
  els:List[LegsPattern] = []
  def finish() -> LegsPattern: return Seq.from_list(els)
  for token in buffer:
    kind = token.kind
    def _fail(msg) -> 'NoReturn': source.fail(token, msg)
    def quantity(pattern_type:Type[QuantityPattern]) -> None:
      if not els: _fail('quantity operator must be preceded by a pattern.')
      els[-1] = pattern_type(els[-1])
    if kind == terminator: return finish()
    elif kind == 'paren_o': els.append(parse_pattern_pattern(source, buffer, terminator='paren_c'))
    elif kind == 'brckt_o': els.append(Charset(ranges=tuple(ranges_for_codes(sorted(parse_charset(source, buffer, token))))))
    elif kind == 'bar': return parse_choice(source, buffer, left=finish(), terminator=terminator)
    elif kind == 'qmark': quantity(Opt)
    elif kind == 'star': quantity(Star)
    elif kind == 'plus': quantity(Plus)
    elif kind == 'esc': els.append(Charset(ranges=ranges_for_code(parse_esc(source, token))))
    elif kind == 'ref': els.append(Charset(ranges=parse_ref(source, token)))
    elif kind == 'sym': els.extend(Charset.for_char(c) for c in source[token])
    elif kind in ('colon', 'amp', 'dash', 'caret', 'char'):
      els.append(Charset.for_char(source[token]))
    elif kind == 'invalid': _fail('invalid pattern token.')
    else: _fail(f'unexpected pattern token: {desc_kind(kind)}.')
  return finish()


def parse_choice(source:Source[str], buffer:Buffer[Token], left:LegsPattern, terminator:str) -> LegsPattern:
  return Choice(left, parse_pattern_pattern(source, buffer, terminator=terminator))


def parse_esc(source:Source[str], token:Token) -> int:
  char = source[token][1]
  try: code = escape_codes[char]
  except KeyError: source.fail(token, f'invalid escaped character: {char!r}.')
  return code


def ranges_for_code(code:int) -> CodeRanges: return ((code, code+1),)


def parse_ref(source:Source[str], token:Token) -> CodeRanges:
  try: return unicode_charsets[source[token][1:]]
  except KeyError: source.fail(token, 'unknown charset name.')


def parse_charset(source:Source[str], buffer:Buffer[Token], start_token:Token, is_right=False, is_diff=False) -> Set[int]:
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
  codes:Set[int] = set()

  def add_code(token:Token, code:int) -> None:
    if code in codes:
      source.fail(token, f'repeated character in set: {code!r}.')
    codes.add(code)

  def parse_right(token:Token, is_diff_op:bool) -> Set[int]:
    if not codes:
      source.fail(token, f'empty charset preceding operator.')
    if is_diff or (is_right and is_diff_op):
      source.fail(token, f'compound set expressions containing `-` or `^` operators must be grouped with `[...]`.')
    return parse_charset(source, buffer, token, is_right=True, is_diff=is_diff_op)

  def finish() -> Set[int]:
      if not codes: source.fail(start_token, 'empty character set.')
      return codes

  for token in buffer:
    kind = token.kind
    if kind == 'brckt_c':
      return finish()
    if kind == 'brckt_o':
      for code in parse_charset(source, buffer, token):
        add_code(token, code)
    elif kind == 'ref':
      for code in codes_for_ranges(parse_ref(source, token)):
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
      add_code(token, parse_esc(source, token))
    elif kind == 'sym':
      for char in source[token]:
        add_code(token, ord(char))
    elif kind in ('char', 'colon', 'bar', 'qmark', 'star', 'plus', 'paren_o', 'paren_c'):
      add_code(token, ord(source[token]))
    elif kind == 'invalid': source.fail(token, 'invalid pattern token.')
    else: source.fail(token, f'unexpected charset token: {desc_kind(kind)}.')
  source.fail(start_token, 'unterminated charset.')


def consume(source:Source[str], buffer:Buffer[Token], kind:str, subj:str) -> Token:
  token:Token = next(buffer)
  act = token.kind
  if act != kind: source.fail(token, f'{subj} expected {desc_kind(kind)}; found {desc_kind(act)}.')
  return token


def check_is_sym(source:Source[str], token:Token, expectation:str) -> None:
  kind = token.kind
  if kind != 'sym':
    source.fail(token, f'expected {expectation}; found {desc_kind(kind)}.')
  if source[token] in reserved_names:
    source.fail(token, f'pattern name is reserved: {source[token]!r}.')

reserved_names = { 'invalid', 'incomplete' }


def is_section(token:Token) -> bool: return token.kind == 'section'


escape_codes:Dict[str, int] = {
  'n': ord('\n'),
  's': ord(' '), # nonstandard space escape.
  't': ord('\t'),
}
escape_codes.update((c, ord(c)) for c in '\\#|$?*+()[]&-^:/')

if False:
  for k, v in sorted(escape_codes.items()):
    errL(f'{k}: {v!r}')
