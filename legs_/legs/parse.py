# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Parser for legs grammar files.

A grammar file is framed by line shape before any tokenization, in two layers:
* `pithy.sectsyn.parse_sections` splits the file into sections at `# Name` header lines.
* `pithy.sectsyn.parse_entries` splits each section into entries.
  A line beginning at column 0 begins an entry; an indented line or one beginning with `|` continues it.

Each entry is then lexed and parsed independently, within its own range.
Therefore no pattern can alter the section or entry structure, and a syntax error is confined to its entry.
All errors are reported together.

The sections are `License`, `Patterns`, `Modes` and `Transitions`. They can appear in any order and can be repeated.
Text preceding the first header is treated as patterns, so a simple grammar needs no headers.
A header requires a space after the `#`. A pattern line cannot begin with `# ` at column 0; indent it or write `\\#`.
'''

import re
from dataclasses import dataclass
from typing import Iterable

from pithy.lex import Lexer, LexMode, LexTrans
from pithy.parse import Adjacency, Atom, Infix, Left, ParseError, Parser, Precedence, Right, Struct, Suffix, uni_val, ZeroOrMore
from pithy.sectsyn import parse_entries, parse_sections, SectIndices
from pithy.unicode import CodeRanges, codes_for_ranges
from pithy.unicode.charsets import unicode_charsets
from tolkien import get_syntax_slc, Source, Syntax, SyntaxError, SyntaxMsg, Token

from . import KindModeTransitions, ModeTransitions
from .patterns import CharsetPattern, ChoicePattern, LegsPattern, OptPattern, PlusPattern, SeqPattern, StarPattern


@dataclass
class Grammar:
  license:str
  patterns:dict[str,LegsPattern]
  modes:dict[str,frozenset[str]]
  transitions:ModeTransitions


def parse_legs(path:str, text:str) -> Grammar:
  '''
  Parse the legs source given in `text`, returning a Grammar containing:
  * the license string;
  * a dictionary of pattern names to LegsPattern objects;
  * a dictionary of mode names to pattern names;
  * a dictionary of mode transitions.
  If the source contains errors then all of them are reported in source order and the process exits.
  '''
  source = Source(name=path, text=text)
  builder = GrammarBuilder(source)
  for sect in parse_sections(source, symbol='#', numbered=False, title_sep=':'):
    if isinstance(sect, SyntaxError): continue # A level skip; the deeper section is reported by `parse_section`.
    builder.parse_section(sect)
  grammar = builder.build()
  if builder.errors: exit(''.join(diagnostic for _, diagnostic in sorted(builder.errors, key=lambda e: e[0])))
  return grammar



class GrammarBuilder:
  'Accumulates the contents of the sections and the error diagnostics.'

  def __init__(self, source:Source[str]):
    self.source = source
    self.errors:list[tuple[int,str]] = [] # (position, diagnostic).
    self.licenses:list[str] = []
    self.patterns:dict[str,LegsPattern] = {}
    self.modes:dict[str,list[Token]] = {} # Mode name to pattern name tokens.
    self.transitions:list[tuple[Token,Token,Token,Token]] = [] # (from_mode, open_kind, push_mode, close_kind).


  def error(self, syntax:Syntax, msg:str, notes:Iterable[SyntaxMsg]=()) -> None:
    self.errors.append((get_syntax_slc(syntax).start, self.source.diagnostic(*notes, (syntax, msg))))


  def parse_error(self, e:ParseError) -> None:
    self.error(e.syntax, f'parse error: {e.msg}', notes=reversed(e.notes))


  def parse_section(self, sect:SectIndices) -> None:
    source = self.source
    if sect.level == 0: # The root section; text preceding the first header is treated as patterns.
      self.parse_patterns(sect.raw_body)
      return
    if sect.level > 1:
      self.error(sect.marker, 'error: nested sections are not supported.')
      return

    name_text, comment_sep, _ = source[sect.name].partition('//')
    name = name_text.strip().lower()
    if name == 'license':
      self.licenses.extend((source[sect.inline], source[sect.body]))
      return
    if sect.inline.start < sect.inline.stop and not comment_sep and not source[sect.inline].startswith('//'):
      self.error(sect.inline, 'error: unexpected text after section name.')
    match name:
      case 'patterns': self.parse_patterns(sect.raw_body)
      case 'modes': self.parse_modes(sect.raw_body)
      case 'transitions': self.parse_transitions(sect.raw_body)
      case _: self.error(sect.title, 'error: unknown section; expected `License`, `Patterns`, `Modes` or `Transitions`.')


  def parse_patterns(self, body:slice) -> None:
    source = self.source
    for entry in self.entries(body, continuations=['|']):
      m = pattern_head_re.match(source.text, entry.start, entry.stop)
      if not m:
        line = slice(entry.start, min(entry.stop, source.get_line_end(entry.start)))
        hint = '; a section header requires a space after `#`' if source.text.startswith('#', entry.start) else ''
        self.error(line, f'error: expected pattern name{hint}.')
        continue
      name_slc = slice(*m.span('name'))
      name = source[name_slc]
      rest = slice(m.end(), entry.stop)
      pattern:LegsPattern
      if m['colon']:
        try: pattern = pattern_parser.parse('pattern_expr', source, slc=rest)
        except ParseError as e:
          self.parse_error(e)
          continue
      else: # A bare name is a literal pattern.
        excess = next(pattern_lexer.lex(source, rest, drop=dropped_kinds), None)
        if excess is not None:
          self.error(excess, 'error: expected `:` following pattern name.')
          continue
        pattern = SeqPattern.from_list([CharsetPattern.for_code(ord(c)) for c in name])
      if name in self.patterns:
        self.error(name_slc, f'error: pattern already defined: {name}')
        continue
      self.patterns[name] = pattern


  def parse_modes(self, body:slice) -> None:
    source = self.source
    for entry in self.entries(body):
      try: mode = decl_parser.parse('mode', source, slc=entry)
      except ParseError as e:
        self.parse_error(e)
        continue
      name = source[mode.sym]
      if name in self.modes:
        self.error(mode.sym, f'error: mode already defined: {name}')
        continue
      self.modes[name] = mode.mode_pattern_syms


  def parse_transitions(self, body:slice) -> None:
    for entry in self.entries(body):
      try: transition = decl_parser.parse('transition', self.source, slc=entry)
      except ParseError as e: self.parse_error(e)
      else: self.transitions.append(tuple(transition[1:])) # Omit the leading `slc` field.


  def entries(self, body:slice, continuations:Iterable[str]=()) -> Iterable[slice]:
    'Yield the entry ranges of a section body, reporting any orphaned continuation lines.'
    for entry in parse_entries(self.source, body, continuations=continuations, comments=['//']):
      if isinstance(entry, SyntaxError): self.error(entry.syntax, 'error: continuation line has no preceding entry.')
      else: yield entry


  def build(self) -> Grammar:
    '''
    Validate the references between sections and return the grammar.
    This is done after all sections are parsed so that the order of the sections does not matter.
    '''
    source = self.source
    patterns = self.patterns
    license = '\n'.join(self.licenses).strip()

    modes:dict[str,frozenset[str]] = {}
    for name, pattern_syms in self.modes.items():
      for sym in pattern_syms:
        if source[sym] not in patterns: self.error(sym, f'error: undefined pattern name: {source[sym]}')
      modes[name] = frozenset(source[sym] for sym in pattern_syms)
    if not modes:
      modes['main'] = frozenset(patterns)

    transitions:dict[str,KindModeTransitions] = {}
    for from_mode_tok, open_kind_tok, push_mode_tok, close_kind_tok in self.transitions:
      from_mode = source[from_mode_tok]
      open_kind = source[open_kind_tok]
      push_mode = source[push_mode_tok]
      close_kind = source[close_kind_tok]
      is_ok = True
      for mode_tok, mode, kind_tok, kind in [
       (from_mode_tok, from_mode, open_kind_tok, open_kind), (push_mode_tok, push_mode, close_kind_tok, close_kind)]:
        if mode not in modes:
          self.error(mode_tok, f'error: undefined mode name: {mode}')
          is_ok = False
        elif kind not in modes[mode]:
          self.error(kind_tok, f'error: pattern is not a member of mode `{mode}`: {kind}')
          is_ok = False
      if not is_ok: continue
      kind_transitions = transitions.setdefault(from_mode, {})
      if open_kind in kind_transitions:
        self.error(open_kind_tok, f'error: transition already defined for mode `{from_mode}`: {open_kind}')
        continue
      kind_transitions[open_kind] = (push_mode, close_kind)

    return Grammar(license=license, patterns=patterns, modes=modes, transitions=transitions)



pattern_head_re = re.compile(r'(?P<name>[A-Za-z_][0-9A-Za-z_]*)[ \t]*(?P<colon>:)?')

dropped_kinds = ('comment', 'newline', 'spaces')


# Pattern expressions.

pattern_lexer = Lexer(flags='mx',
  patterns=dict(
    newline = r'\n',
    spaces  = r'\ +',
    comment = r'//[^\n]*',
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
    LexMode('pattern', kinds=[*dropped_kinds,
      'brack_o', 'brack_c', 'paren_o', 'paren_c', 'bar', 'qmark', 'star', 'plus', 'ref', 'esc', 'backslash', 'char']),
    LexMode('charset', kinds=[*dropped_kinds, 'brack_o', 'brack_c', 'amp', 'dash', 'caret', 'ref', 'esc', 'backslash', 'char']),
  ],
  transitions=[
    LexTrans(('pattern', 'charset'), kind='brack_o', mode='charset', pop='brack_c', consume=True),
  ]
)


def build_pattern_parser() -> Parser:
  return Parser(pattern_lexer,
    drop=dropped_kinds,
    literals=('brack_o', 'brack_c', 'paren_o', 'paren_c'),
    rules=dict(
      pattern_expr=Precedence(
        ('char', 'esc', 'ref', 'charset_p', 'paren'),
        Right(Infix('bar', transform=transform_choice)),
        Right(Adjacency(transform=transform_adj)),
        Right(
          Suffix('qmark', transform=lambda s, slc, t, v: OptPattern(v)),
          Suffix('star',  transform=lambda s, slc, t, v: StarPattern(v)),
          Suffix('plus',  transform=lambda s, slc, t, v: PlusPattern(v))),
      ),

      paren=Struct('paren_o', 'pattern_expr', 'paren_c'),

      # Charsets.

      charset_p=Struct('charset', # Wrapper to transform from set[int] to CharsetPattern.
        transform=lambda s, t, fields: CharsetPattern.for_codes(fields[0])),

      charset=Struct('brack_o', 'charset_expr', 'brack_c'),

      charset_expr=Precedence(
        ('charset', 'char_cs', 'esc_cs', 'ref_cs'),
        Left(
          Infix('amp',    transform=lambda s, slc, t, l, r: l & r),
          Infix('caret',  transform=lambda s, slc, t, l, r: l ^ r),
          Infix('dash',   transform=lambda s, slc, t, l, r: l - r)),
        Right(Adjacency(  transform=lambda s, slc, t, l, r: l | r)),
        transform=uni_val),

      # Pattern atoms.
      char=Atom('char',     transform=transform_char),
      esc=Atom('esc',       transform=transform_esc),
      ref=Atom('ref',       transform=transform_ref),

      # Charset atoms.
      char_cs=Atom('char',  transform=transform_cs_char),
      esc_cs=Atom('esc',    transform=transform_cs_esc),
      ref_cs=Atom('ref',    transform=transform_cs_ref),
    ),
  )


# Mode and transition declarations.

decl_lexer = Lexer(flags='mx',
  patterns=dict(
    newline = r'\n',
    spaces  = r'\ +',
    comment = r'//[^\n]*',
    colon   = r':',
    sym     = r'[A-Za-z_][0-9A-Za-z_]*',
  ))


decl_parser = Parser(decl_lexer,
  drop=dropped_kinds,
  literals=('colon',),
  rules=dict(
    mode=Struct('sym', 'colon', ZeroOrMore('sym', field='mode_pattern_syms')),
    transition=Struct('sym', 'colon', 'sym', 'colon', 'colon', 'sym', 'colon', 'sym'),
  ),
)


# Parser transformers.

def transform_choice(source:Source, slc:slice, token:Token, l:LegsPattern, r:LegsPattern) -> ChoicePattern:
  return ChoicePattern(l, r)

def transform_adj(source:Source, slc:slice, token:Token, l:LegsPattern, r:LegsPattern) -> SeqPattern:
  return SeqPattern(l, r)


# Parser atom transformers.

def transform_char(source:Source, token:Token) -> CharsetPattern:
  return CharsetPattern.for_code(ord(source[token]))

def transform_esc(source:Source, token:Token) -> CharsetPattern:
  return CharsetPattern.for_code(code_for_esc(source, token))

def transform_ref(source:Source, token:Token) -> CharsetPattern:
  return CharsetPattern(ranges=ranges_for_ref(source, token))


# Charset atom transformers.

def transform_cs_char(source:Source, token:Token) -> set[int]:
  return set((ord(source[token]),))

def transform_cs_esc(source:Source, token:Token) -> set[int]:
  return set((code_for_esc(source, token),))

def transform_cs_ref(source:Source, token:Token) -> set[int]:
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


escape_codes:dict[str, int] = {
  'n': ord('\n'),
  's': ord(' '), # nonstandard space escape.
  't': ord('\t'),
}
escape_codes.update((c, ord(c)) for c in '\\#|$?*+()[]&-^:/')


pattern_parser = build_pattern_parser()
