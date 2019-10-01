# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Simple lexing using python regular expressions.
'''

import re
from typing import Container, Dict, FrozenSet, Iterable, Iterator, List, NoReturn, Optional, Pattern, Tuple, cast

from tolkien import Source, Token


class LexError(Exception): pass


class LexTrans:
  def __init__(self, base:str, kind:str, mode:str, pops:Iterable[str], consume:bool) -> None:
    self.base = base # Parent mode.
    self.kind = kind # Base token kind.
    self.mode = mode # Child mode.
    self.pops = frozenset([pops] if isinstance(pops, str) else pops) # Child token kinds.
    self.consume = consume # If false, base will consider this token for further push/pop mode transitions.

  def __repr__(self) -> str: return f'{type(self).__name__}({self.base!r}, {self.kind!r}, {self.mode!r}, {self.pops!r}, {self.consume!r})'


class Lexer:
  '''
  Note: A zero-length match, e.g. r'^' causes an exception; otherwise the stream would never advance.
  '''
  # One way to support zero-length tokens, e.g. r'^\s*' for Python indent tokens,
  # would be to swap out the main regex for one with the pattern in question omitted,
  # for the next iteration only.

  class DefinitionError(Exception): pass

  def __init__(self, *, flags='', invalid=None, patterns:Dict[str,str], modes:Dict[str,Iterable[str]]={},
   transitions:Iterable[LexTrans]=()) -> None:
    self.invalid = invalid

    # Validate flags.
    for flag in flags:
      if flag not in 'aiLmsux':
        raise Lexer.DefinitionError(f'invalid global regex flag: {flag}')
    flags_pattern = f'(?{flags})' if flags else ''
    is_extended = 'x' in flags

    # Validate patterns.
    if not patterns: raise Lexer.DefinitionError('Lexer instance must define at least one pattern')
    self.patterns: Dict[str,str] = {}
    for n, v in patterns.items():
      validate_name(n)
      if n == invalid:
        raise Lexer.DefinitionError(f'{n!r} pattern name collides with the invalid token name')
      if not isinstance(v, str): # TODO: also support bytes.
        raise Lexer.DefinitionError(f'{n!r} pattern value must be a string; found {v!r}')
      pattern = f'{flags_pattern}(?P<{n}>{v})'
      try: r = re.compile(pattern) # compile each expression by itself to improve error clarity.
      except Exception as e:
        lines = [f'{n!r} pattern is invalid: {pattern}']
        if flags: lines.append(f'global flags: {flags!r}')
        if is_extended and re.search('(?<!\\)#)', v): lines.append('unescaped verbose mode comments break lexer')
        msg = '\n  note: '.join(lines)
        raise Lexer.DefinitionError(msg) from e
      for group_name in r.groupindex:
        if group_name in patterns and group_name != n:
          raise Lexer.DefinitionError(f'{n!r} pattern contains a conflicting capture group name: {group_name!r}')
      self.patterns[n] = pattern

    # Validate modes.
    self.modes: Dict[str,FrozenSet[str]] = {}
    main = None
    if modes:
      for mode, names in modes.items():
        if not main: main = mode
        if mode in patterns:
          raise Lexer.DefinitionError(f'mode name conflicts with pattern name: {mode!r}')
        expanded = set()
        if isinstance(names, str):
          raise Lexer.DefinitionError(f'mode {mode!r} value should be a iterable of names, not a str: {names!r}')
        for name in names:
          if re.fullmatch(r'\w+', name):
            if name in patterns: expanded.add(name)
            else: raise Lexer.DefinitionError(f'mode {mode!r} includes nonexistant pattern: {name!r}')
          else:
            try:
              matching = {p for p in self.patterns if re.fullmatch(name, p)}
            except Exception:
              raise Lexer.DefinitionError(f'mode {mode!r} includes invalid wildcard pattern regex: {name}')
            if not matching:
              raise Lexer.DefinitionError(f'mode {mode!r} wildcard pattern regex does not match any patterns: {name}')
            expanded.update(matching)
        self.modes[mode] = frozenset(expanded)
    else:
      self.modes = { 'main' : frozenset(self.patterns) }
      main = 'main'

    # Validate transitions.
    assert main is not None
    self.main:str = main
    self.transitions:Dict[Tuple[str,str],LexTrans] = {}
    for trans in transitions:
      if not isinstance(trans, LexTrans): raise TypeError(trans)
      if trans.base not in modes: raise Lexer.DefinitionError(f'unknown parent mode: {trans.base!r}')
      if trans.mode not in modes: raise Lexer.DefinitionError(f'unknown child mode: {trans.mode!r}')
      if trans.kind not in patterns: raise Lexer.DefinitionError(f'unknown mode push pattern: {trans.kind!r}')
      for kind in trans.pops:
        if kind not in patterns: raise Lexer.DefinitionError(f'unknown mode pop pattern: {kind!r}')
      self.transitions[(trans.base, trans.kind)] = trans

    choice_sep = '\n| ' if 'x' in flags else '|'
    def compile_mode(mode:str, pattern_names:FrozenSet[str]) -> Pattern:
      return re.compile(choice_sep.join(pattern for name, pattern in self.patterns.items() if name in pattern_names))
      #^ note: iterate over self.patterns.items (not pattern_names) because the dict preserves the original pattern order.

    self.regexes = { mode : compile_mode(mode, pattern_names) for mode, pattern_names in self.modes.items() }


  def _lex_inv(self, pos:int, end:int) -> Token:
    inv = Token(pos=pos, end=end, kind=(self.invalid or 'invalid'))
    if self.invalid: return inv
    raise LexError(inv)


  def _lex_one(self, regex:Pattern, source:Source[str], pos:int, end:int) -> Token:
    m = regex.search(source.text, pos)
    if not m:
      return self._lex_inv(pos=pos, end=end)
    p, e = m.span()
    if pos < p:
      return self._lex_inv(pos=pos, end=p)
    if p == e:
      raise Lexer.DefinitionError(f'Zero-length patterns are disallowed.\n  kind: {m.lastgroup}; match: {m}')
    kind = m.lastgroup
    assert isinstance(kind, str)
    return Token(pos=p, end=e, kind=kind)


  def _lex(self, stack:List[Tuple[LexTrans,Token]], source:Source[str], pos:int, end:int, drop:Container[str], eot:bool
   ) -> Iterator[Token]:
    assert isinstance(source, Source)
    while pos < end:
      frame_trans, frame_token = stack[-1]
      mode = frame_trans.mode
      regex = self.regexes[mode]
      token = self._lex_one(regex, source, pos=pos, end=end)
      kind = token.kind
      pos = token.end
      if kind not in drop:
        yield token
      # Check if we should pop one or more modes.
      try:
        while kind in frame_trans.pops: # Check if we should pop the current mode.
          stack.pop()
          if frame_trans.consume:
            raise _BreakFromModeSwitching # This frame "consumes" the token.
          frame_trans, frame_token = stack[-1]
          mode = frame_trans.mode
        # Check if we should push a child mode.
        try: push_trans = self.transitions[(mode, kind)]
        except KeyError: pass
        else:
          stack.append((push_trans, token))
      except _BreakFromModeSwitching: pass
    if eot:
      yield eot_token(source)


  def lex(self, source:Source[str], pos:int=0, end:Optional[int]=None, drop:Container[str]=(), eot=False) -> Iterator[Token]:
    if not isinstance(source, Source): raise TypeError(source)
    text = source.text
    if pos < 0:
      pos = len(text) + pos
    if end is None:
      end = len(text)
    elif end < 0:
      end = len(text) + end
    _e:int = end # typing hack.
    return self._lex(stack=[self.root_frame(mode=self.main)], source=source, pos=pos, end=_e, drop=drop, eot=eot)


  def lex_stream(self, *, name:str, stream:Iterable[str], drop:Container[str]=(), eot=False) -> Iterator[Tuple[Source, Token]]:
    '''
    Note: the yielded Token objects have positions relative to input string that each was lexed from.
    TODO: fix the line numbers.
    '''
    stack = [self.root_frame(mode=self.main)]
    source = Source(name=name, text='')
    for text in stream:
      if text:
        source = Source(name=name, text=text)
        for token in self._lex(stack=stack, source=source, pos=0, end=len(source.text), drop=drop, eot=False):
          yield (source, token)
    if eot:
      yield (source, eot_token(source))


  def root_frame(self, mode:str) -> Tuple[LexTrans,Token]:
    'The root frame is degenerate; because it has an empty pops set it will never get popped; base and kind are never accessed.'
    return (LexTrans(base='', kind='', mode=mode, pops=frozenset(), consume=False), Token(0, 0, ''))


class _BreakFromModeSwitching(Exception): pass


def eot_token(source:Source[str]) -> Token:
  'Create a token representing the end-of-text.'
  end = len(source.text)
  return Token(pos=end, end=end, kind='end_of_text')


def validate_name(name:str) -> str:
  if not valid_name_re.fullmatch(name):
    raise Lexer.DefinitionError(f'invalid name: {name!r}')
  if name in reserved_names:
    raise Lexer.DefinitionError(f'name is reserved: {name!r}')
  return name


valid_name_re = re.compile(r'[A-Za-z_]\w*')

reserved_names = frozenset({'end_of_text'})


whitespace_patterns = dict(
  indents   = r'(?m:^\ +)',
  spaces    = r'\ +',
  ind_tabs  = r'(?m:^\ +)',
  tabs      = r'\t+',
  newline   = r'\n',
)


c_like_punctuation_patterns = dict(

  paren_o     = r'\(',
  paren_c     = r'\)',
  brack_o     = r'\[',
  brack_c     = r'\]',
  brace_o     = r'{',
  brace_c     = r'}',

  comma       = r',',
  semi        = r';',

  # Order-dependent patterns.
  dot3        = r'\.\.\.',
  dot2        = r'\.\.',
  dot         = r'\.',

  eq3         = r'===',
  eq2         = r'==',
  eq          = r'=',

  exclaim2_eq = r'!==',
  exclaim_eq  = r'!=',
  exclaim     = r'!',

  arrow_r     = r'->',
  dash_eq     = r'-=',
  dash        = r'-',

  plus_eq     = r'\+=',
  plus        = r'\+',

  amp_eq      = r'&=',
  amp2        = r'&&',
  amp         = r'&',

  pipe2       = r'\|\|',
  pipe_eq     = r'\|=',
  pipe        = r'\|',

  at_eq       = r'@=',
  at          = r'@',

  caret_eq    = r'\^=',
  caret       = r'\^',

  colon_eq    = r':=',
  colon       = r':',

  slash2_eq   = r'//=',
  slash2      = r'//',

  slash_eq    = r'/=',
  slash       = r'/',

  star2_eq    = r'\*\*=',
  star2       = r'\*\*',
  star_eq     = r'\*=',
  star        = r'\*',

  qmark2      = r'\?\?',
  qmark       = r'\?',

  shift_l_eq  = r'<<=',
  shift_l     = r'<<',
  le          = r'<=',
  arrow_l     = r'<-',
  lt          = r'<',

  shift_r_eq  = r'>>=',
  shift_r     = r'>>',
  ge          = r'>=',
  gt          = r'>',

  percent_eq  = r'%=',
  percent     = r'%',

  tilde_eq    = r'~=',
  tilde       = r'~',

  backslash   = r'\\',
)
