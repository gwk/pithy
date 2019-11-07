# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from typing import Container, DefaultDict, Dict, FrozenSet, List, Match, NoReturn, Set, Tuple, Type, cast

from pithy.io import *
from pithy.iterable import OnHeadless, fan_by_key_fn, group_by_heads
from pithy.lex import Lexer, LexMode, LexTrans
from pithy.parse import *
from pithy.string import clip_prefix
from pithy.unicode import CodeRange, CodeRanges, codes_for_ranges
from pithy.unicode.charsets import unicode_charsets
from tolkien import Source, Token

from .defs import KindModeTransitions, ModeTransitions
from .patterns import *


@dataclass
class Grammar:
  license:str
  patterns:Dict[str,LegsPattern]
  modes:Dict[str,FrozenSet[str]]
  transitions:ModeTransitions


def parse_legs(path:str, text:str) -> Grammar:
  '''
  Parse the legs source given in `text`, returning:
  * the license string;
  * a dictionary of pattern names to LegsPattern objects;
  * a dictionary of mode names to pattern names;
  * a dictionary of mode transitions.
  '''
  source = Source(name=path, text=text)
  try: grammar:Grammar = parser.parse('grammar', source)
  except ParseError as e: e.fail()
  return grammar


common_kinds = ['newline', 'indents', 'spaces', 'comment']
sl_kinds = ['sl_license', 'sl_patterns', 'sl_modes', 'sl_transitions', 'sl_invalid']

lexer = Lexer(flags='mx',
  patterns=dict(
    newline = r'\n',
    indents = r'^\ +',
    spaces  = r'\ +',
    comment = r'//[^\n]*',

    # Section labels.
    sl_license     = r'\#\ *[Ll]icense',
    sl_patterns    = r'\#\ *[Pp]atterns',
    sl_modes       = r'\#\ *[Mm]odes',
    sl_transitions = r'\#\ *[Tt]ransitions',
    sl_invalid     = r'\#[^\n]*',

    # Top level tokens.
    colon = r':',
    sym = r'[A-Za-z_][0-9A-Za-z_]*',
    license_text = r'[^\n]+',

    # Pattern tokens.
    brack_o = r'\[',
    brack_c = r'\]',
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
    esc     = r'\\[^\n]',
    backslash = r'\\',
    char    = r'[!-~]',
  ),
  modes=[
    LexMode('main', kinds=[*common_kinds, *sl_kinds, 'colon', 'sym']),
    LexMode('license', kinds=[*sl_kinds, 'newline', 'license_text']),
    LexMode('patterns', kinds=[*common_kinds, *sl_kinds, 'bar', 'colon', 'sym']),
    LexMode('pattern', kinds=[*common_kinds,
      'brack_o', 'brack_c', 'paren_o', 'paren_c', 'bar', 'qmark', 'star', 'plus', 'ref', 'esc', 'backslash', 'char']),
    LexMode('charset', kinds=[*common_kinds, 'brack_o', 'brack_c', 'amp', 'dash', 'caret', 'ref', 'esc', 'backslash', 'char']),
  ],
  transitions=[
    LexTrans('main',      kind='sl_license',  mode='license',   pop=sl_kinds, consume=False),
    LexTrans('main',      kind='sl_patterns', mode='patterns',  pop=sl_kinds, consume=False),

    LexTrans('patterns', kind=('colon', 'indents', 'bar'), mode='pattern', pop='newline', consume=True),

    LexTrans(('pattern', 'charset'), kind='brack_o', mode='charset', pop='brack_c', consume=True),
  ]
)


def build_legs_grammar_parser() -> Parser:
  return Parser(lexer,
    dict(
      grammar=OneOrMore('section', drop='newline', transform=transform_grammar),

      section=Choice('section_license', 'section_patterns', 'section_modes', 'section_transitions'),

      # Section top-level rules.

      section_license=Struct(Atom('sl_license'), ZeroOrMore('license'),
        transform=lambda s, fields: fields[1]),

      section_patterns=Struct(Atom('sl_patterns'), 'newline', ZeroOrMore('pattern', drop='newline'),
        transform=lambda s, fields: fields[2]),

      section_modes=Struct(Atom('sl_modes'), 'newline', ZeroOrMore('mode', drop='newline'),
        transform=lambda s, fields: fields[2]),

      section_transitions=Struct(Atom('sl_transitions'), 'newline', ZeroOrMore('transition', drop='newline'),
        transform=lambda s, fields: fields[2]),

      # License.

      license=Choice(Atom('newline'), Atom('license_text'),
        transform=lambda s, label, token: s[token]),

      # Patterns.

      pattern=Struct('sym', Opt('colon_pattern_expr'),
        transform=transform_pattern),

      colon_pattern_expr=Struct('colon', 'pattern_expr', drop=('newline', 'indents'),
        transform=lambda s, fields: fields[1]),

      pattern_expr=Precedence(
        ('char', 'esc', 'ref', 'charset_p', 'paren'),
        Right(Infix('bar', transform=transform_choice)),
        Right(Adjacency(transform=transform_adj)),
        Right(
          Suffix('qmark', transform=lambda s, t, p: OptPattern(p)),
          Suffix('star',  transform=lambda s, t, p: StarPattern(p)),
          Suffix('plus',  transform=lambda s, t, p: PlusPattern(p))),
        drop=('newline', 'indents'),
      ),

      paren=Prefix('paren_o', 'pattern_expr', 'paren_c',
        transform=lambda s, t, pattern: pattern),

      # Charsets.

      charset_p=Struct('charset', # Wrapper to transform from Set[int] to CharsetPattern.
        transform=lambda s, tup: CharsetPattern.for_codes(tup[0])),

      charset=Prefix('brack_o', 'charset_expr', 'brack_c',
        transform=lambda s, t, cs: cs),

      charset_expr=Precedence(
        ('charset', 'char_cs', 'esc_cs', 'ref_cs'),
        Left(
          Infix('amp',    transform=lambda s, t, l, r: l & r),
          Infix('caret',  transform=lambda s, t, l, r: l ^ r),
          Infix('dash',   transform=lambda s, t, l, r: l - r)),
        Right(Adjacency(  transform=lambda s, t, l, r: l | r)),
        transform=lambda s, cs: cs),

      # Pattern atoms.
      amp=Atom('amp',       transform=transform_char),
      caret=Atom('caret',   transform=transform_char),
      char=Atom('char',     transform=transform_char),
      dash=Atom('dash',     transform=transform_char),
      esc=Atom('esc',       transform=transform_esc),
      ref=Atom('ref',       transform=transform_ref),

      # Charset atoms.
      char_cs=Atom('char',  transform=transform_cs_char),
      esc_cs=Atom('esc',    transform=transform_cs_esc),
      ref_cs=Atom('ref',    transform=transform_cs_ref),

      # Modes.

      mode=Struct('sym', 'colon', Quantity('sym'), 'newline',
        transform=lambda s, fields: (fields[0], fields[2])),

      # Transitions.

      transition=Struct('sym', 'colon', 'sym', 'colon', 'colon', 'sym', 'colon', 'sym', 'newline',
        transform=lambda s, fields: ((fields[0], fields[2]), (fields[5], fields[7]))),
    ),
  drop=('comment', 'spaces'))


# Parser transformers.

def transform_grammar(source:Source, sections:List) -> Grammar:
  licenses:List[str] = []
  patterns:Dict[str,LegsPattern] = {}
  modes:Dict[str,FrozenSet[str]] = {}
  transitions = DefaultDict[str,KindModeTransitions](dict)
  for label, section in sections:
    sk = clip_prefix(label.lower(), 'section_')
    if sk == 'license':
      licenses.extend(section)
    elif sk == 'patterns':
      for sym, pattern in section:
        name = source[sym]
        if name in patterns: source.fail((sym, f'error: pattern already defined: {name}'))
        patterns[name] = pattern
    elif sk == 'modes':
      for sym, mode_pattern_syms in section:
        name = source[sym]
        if name in modes:  source.fail((sym, f'error: mode already defined: {name}'))
        for sym in mode_pattern_syms:
          pattern_name = source[sym]
          if pattern_name not in patterns:
            source.fail((sym, f'error: undefined pattern name: {name}'))
        modes[name] = frozenset(source[sym] for sym in mode_pattern_syms)
    elif sk == 'transitions':
      for (from_mode_tok, open_kind_tok), (push_mode_tok, close_kind_tok) in section:
        from_mode = source[from_mode_tok]
        open_kind = source[open_kind_tok]
        push_mode = source[push_mode_tok]
        close_kind = source[close_kind_tok]
        transitions[from_mode][open_kind] = (push_mode, close_kind)
  license = ''.join(licenses).strip()
  for pattern in patterns.values():
    assert isinstance(pattern, LegsPattern), pattern
  if not modes:
    modes['main'] = frozenset(patterns)

  return Grammar(license=license, patterns=patterns, modes=modes, transitions=dict(transitions))


def transform_pattern(source:Source, fields:List) -> Tuple[Token,LegsPattern]:
  sym, pattern = fields
  if pattern is None:
    pattern = SeqPattern.from_list([CharsetPattern.for_code(ord(c)) for c in source[sym]])
  return (sym, pattern)


def transform_choice(source:Source, token:Token, l:LegsPattern, r:LegsPattern) -> ChoicePattern:
  return ChoicePattern(l, r)

def transform_adj(source:Source, token:Token, l:LegsPattern, r:LegsPattern) -> SeqPattern:
  return SeqPattern(l, r)


# Parser atom transformers.

def transform_char(source:Source, token:Token) -> CharsetPattern:
  return CharsetPattern.for_code(ord(source[token]))

def transform_esc(source:Source, token:Token) -> CharsetPattern:
  return CharsetPattern.for_code(code_for_esc(source, token))

def transform_ref(source:Source, token:Token) -> CharsetPattern:
  return CharsetPattern(ranges=ranges_for_ref(source, token))


# Charset atom transformers.

def transform_cs_char(source:Source, token:Token) -> Set[int]:
  return set((ord(source[token]),))

def transform_cs_esc(source:Source, token:Token) -> Set[int]:
  return set((code_for_esc(source, token),))

def transform_cs_ref(source:Source, token:Token) -> Set[int]:
  return set(codes_for_ranges(ranges_for_ref(source, token)))


# Utilities.

def code_for_esc(source:Source, token:Token) -> int:
  char = source[token][1]
  try: return escape_codes[char]
  except KeyError: source.fail((token, f'error: invalid escaped character: {char!r}.'))

def ranges_for_ref(source:Source[str], token:Token) -> CodeRanges:
  name = source[token][1:]
  try: return unicode_charsets[name]
  except KeyError: source.fail((token, f'error: unknown charset name: {name!r}.'))


kind_descs = { # TODO: Change pithy.parse.expect to use these.
  'section_invalid' : 'invalid section',
  'sym'     : 'symbol',
  'colon'   : '`:`',
}


escape_codes:Dict[str, int] = {
  'n': ord('\n'),
  's': ord(' '), # nonstandard space escape.
  't': ord('\t'),
}
escape_codes.update((c, ord(c)) for c in '\\#|$?*+()[]&-^:/')

if False:
  for k, v in sorted(escape_codes.items()): # type: ignore
    errL(f'{k}: {v!r}')


parser = build_legs_grammar_parser()
