# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Simple lexing using python regular expressions.
'''

import re
from typing import cast, Container, Iterable, Iterator, Pattern

from tolkien import Source, Token

from .strings import iter_str


_context_keywords_ = ['dedent', 'indentation', 'lexer', 'lexical analysis', 'mode transitions', 're.compile',
  'regular expressions', 'scanner', 'tokenization', 'tokens']


class LexMode:
  def __init__(self, name:str, kinds:Iterable[str], *, indents:bool=False):
    self.name = name
    self.kinds = list(iter_str(kinds))
    self.indents = indents
    self.kind_set:frozenset[str] = frozenset() # Filled in by Lexer.
    self.regex:Pattern = cast(Pattern, None) # Filled in by Lexer.

  def __repr__(self) -> str:
    return f'{type(self).__name__}({self.name!r}, kinds={self.kinds}, kind_set={self.kind_set}, indents={self.indents})'


class LexTrans:
  '''
  A mode transition. When the lexer is in one of the `base` modes and produces a token of one of the `kind` kinds, it pushes `mode`.
  When it then produces a token of one of the `pop` kinds, it pops back to the base mode.
  The popping token is produced by the child mode. If `consume` is false, then the base frame also acts on that token:
  it can pop in turn, or push another mode.
  '''

  def __init__(self, base:Iterable[str], *, kind:Iterable[str], mode:str, pop:Iterable[str], consume:bool):
    self.bases = tuple(iter_str(base)) # Parent modes.
    self.kinds = tuple(iter_str(kind)) # Parent mode token kinds that cause push.
    self.mode = mode # Child mode.
    self.pops = frozenset(iter_str(pop)) # Child mode token kinds that cause pop.
    self.consume = consume # If false, base will consider this token for further push/pop mode transitions.

  def __repr__(self) -> str:
    return (f'{type(self).__name__}({self.bases!r}, kind={self.kinds!r}, mode={self.mode!r}, pop={sorted(self.pops)!r}, '
      f'consume={self.consume})')



class Lexer:
  '''
  Define a Lexer using python regular expressions.
  This class is used to prototype (and bootstrap) Legs lexers.
  Note: A zero-length match, e.g. r'^' causes an exception; otherwise the stream would never advance.
  '''

  class DefinitionError(Exception): pass

  def __init__(self, *, flags:str='', patterns:dict[str,str], modes:Iterable[LexMode]=(),
   transitions:Iterable[LexTrans]=()) -> None:

    # Validate flags.
    for flag in flags:
      if flag not in 'aiLmsux':
        raise Lexer.DefinitionError(f'invalid global regex flag: {flag}')
    flags_pattern = f'(?{flags})' if flags else ''
    is_verbose = 'x' in flags

    # Validate patterns.
    if not patterns: raise Lexer.DefinitionError('Lexer instance must define at least one pattern')
    self.patterns: dict[str,str] = {}
    for n, v in patterns.items():
      validate_name(n)
      if n == 'invalid':
        raise Lexer.DefinitionError(f'{n!r} pattern name collides with the invalid token name')
      if not isinstance(v, str): # TODO: also support bytes.
        raise Lexer.DefinitionError(f'{n!r} pattern value must be a string; found {v!r}')
      pattern = f'(?P<{n}>{v})'
      flagged_pattern = flags_pattern + pattern
      try: r = re.compile(flagged_pattern) # Compile each expression by itself to improve error clarity.
      except Exception as e:
        lines = [f'{n!r} pattern is invalid: {flagged_pattern}']
        if flags: lines.append(f'global flags: {flags!r}')
        if is_verbose and re.search(r'(?<!\\)#', v): lines.append('unescaped verbose mode comments break lexer')
        msg = '\n  note: '.join(lines)
        raise Lexer.DefinitionError(msg) from e
      for group_name in r.groupindex:
        if group_name in patterns and group_name != n:
          raise Lexer.DefinitionError(f'{n!r} pattern contains a conflicting capture group name: {group_name!r}')
      self.patterns[n] = pattern

    # Validate and compile modes.
    modes = list(modes) # The modes are traversed more than once.
    if not modes:
      modes = [LexMode('main', kinds=self.patterns)]
    self.modes: dict[str,LexMode] = {}
    main = None
    for mode in modes:
      if not isinstance(mode, LexMode): raise Lexer.DefinitionError(f'expected LexMode; received: {mode!r}')
      if not main: main = mode.name
      if mode.name in self.modes:
        raise Lexer.DefinitionError(f'duplicate mode name: {mode.name!r}')
      if mode.name in patterns:
        raise Lexer.DefinitionError(f'mode name conflicts with pattern name: {mode.name!r}')
      kind_set = set()
      for kind in iter_str(mode.kinds):
        if re.fullmatch(r'\w+', kind): # Single name.
          if kind in patterns: kind_set.add(kind)
          else: raise Lexer.DefinitionError(f'mode {mode.name!r} includes nonexistent pattern: {kind!r}')
        else: # Pattern.
          try:
            matching = {p for p in self.patterns if re.fullmatch(kind, p)}
          except Exception:
            raise Lexer.DefinitionError(f'mode {mode.name!r} includes invalid pattern regex: {kind}')
          if not matching:
            raise Lexer.DefinitionError(f'mode {mode.name!r} wildcard pattern regex does not match any patterns: {kind}')
          kind_set.update(matching)
      if not kind_set: raise Lexer.DefinitionError(f'mode {mode.name!r} has no patterns')
      if mode.indents:
        for kind in ('newline', 'spaces'):
          if kind not in kind_set: raise Lexer.DefinitionError(f'mode {mode.name!r} has indents but lacks the {kind!r} pattern')
        for kind in ('indent', 'dedent'):
          if kind in patterns: raise Lexer.DefinitionError(f'{kind!r} pattern name collides with the {kind} token name')
      self.modes[mode.name] = mode
      mode.kind_set = frozenset(kind_set)
      choice_sep = '\n| ' if is_verbose else '|'

      pattern = flags_pattern + choice_sep.join(pat for name, pat in self.patterns.items() if name in kind_set)
      try: mode.regex = re.compile(pattern)
      except re.error as e:
        raise Lexer.DefinitionError(f'mode {mode.name!r} assembled pattern is invalid: {pattern}') from e
      #^ note: iterate over self.patterns.items (not pattern_names) because the dict preserves the original pattern order.

    kinds = list(self.patterns)
    if any(mode.indents for mode in modes):
      kinds.extend(['indent', 'dedent'])
    self.kinds = frozenset(kinds)

    # Validate transitions.
    assert main is not None
    self.main:str = main
    self.transitions:dict[tuple[str,str],LexTrans] = {} # (base mode, kind) -> transition.
    for trans in transitions:
      if not isinstance(trans, LexTrans): raise Lexer.DefinitionError(f'expected `LexTrans`; received {trans!r}')
      for base in trans.bases:
        if base not in self.modes: raise Lexer.DefinitionError(f'unknown parent mode: {base!r}')
      if trans.mode not in self.modes: raise Lexer.DefinitionError(f'unknown child mode: {trans.mode!r}')
      for label, trans_kinds in [('push', trans.kinds), ('pop', sorted(trans.pops))]:
        for kind in trans_kinds:
          # The synthesized `indent` and `dedent` tokens do not take part in transitions.
          if kind not in self.patterns: raise Lexer.DefinitionError(f'unknown mode {label} pattern: {kind!r}')
      for base in trans.bases:
        for kind in trans.kinds:
          key = (base, kind)
          try: existing = self.transitions[key]
          except KeyError: self.transitions[key] = trans
          else: raise Lexer.DefinitionError(f'conflicting transitions:\n  {existing}\n  {trans}')


  def _lex_inv(self, pos:int, end:int, mode:str) -> Token:
    return Token(pos=pos, end=end, mode=mode, kind='invalid')


  def _lex_one(self, regex:Pattern, source:Source[str], pos:int, end:int, mode:str) -> Token:
    m = regex.search(source.text, pos, end)
    if not m:
      return self._lex_inv(pos=pos, end=end, mode=mode)
    p, e = m.span()
    if pos < p:
      return self._lex_inv(pos=pos, end=p, mode=mode)
    if p == e:
      raise Lexer.DefinitionError(f'Zero-length patterns are disallowed.\n  kind: {m.lastgroup}; match: {m}')
    kind = m.lastgroup
    assert isinstance(kind, str)
    return Token(pos=p, end=e, mode=mode, kind=kind)


  def _lex(self, source:Source[str], pos:int, end:int, mode:str, drop:Container[str], eot:bool) -> Iterator[Token]:
    # The root frame is never popped because its transition has no pop kinds.
    stack = [LexTrans(base=(), kind=(), mode=mode, pop=(), consume=False)]
    is_line_start = True
    indent_stack:list[int] = []
    while pos < end:
      # Get the current frame and mode.
      frame = stack[-1]
      lex_mode = self.modes[frame.mode]
      # Lex one token.
      token = self._lex_one(lex_mode.regex, source, pos=pos, end=end, mode=lex_mode.name)
      kind = token.kind
      pos = token.end
      # Check if we should synthesize indent or dedent tokens.
      if lex_mode.indents and is_line_start and kind != 'newline': # Empty lines do not affect the indent stack.
        indent_len = len(source[token]) if kind == 'spaces' else 0
        is_blank = (kind == 'spaces' and (pos == end or self._lex_one(lex_mode.regex, source, pos, end, '').kind == 'newline'))
        if not is_blank: # Lines of only spaces do not affect the indent stack either.
          while indent_stack and indent_stack[-1] > indent_len:
            yield token.pos_token(kind='dedent')
            indent_stack.pop()
          if indent_len and (not indent_stack or indent_stack[-1] < indent_len):
            yield token.pos_token(kind='indent')
            indent_stack.append(indent_len)
      # Yield the current token.
      if kind not in drop:
        yield token
      # Perform mode transitions. First pop each frame that this token closes, until one consumes the token.
      consumed = False
      while kind in frame.pops and not consumed:
        stack.pop()
        consumed = frame.consume
        frame = stack[-1]
      if not consumed: # Check if we should push a child mode.
        try: stack.append(self.transitions[(frame.mode, kind)])
        except KeyError: pass
      is_line_start = (kind == 'newline')
    top_mode = stack[-1].mode
    for _ in indent_stack:
      yield Token(pos=end, end=end, mode=top_mode, kind='dedent')
    if eot:
      yield eot_token(end, mode=top_mode)


  def lex(self, source:Source[str], slc:slice|None=None, drop:Container[str]=(), eot:bool=False, *, mode:str|None=None
   ) -> Iterator[Token]:
    '''
    Lex `source`, yielding tokens.
    If `slc` is provided then only that range of the text is lexed; no token extends past its end.
    The `end_of_text` token is positioned at the end of the range.
    `mode` is the mode in which lexing starts; it defaults to the main mode.
    '''
    if not isinstance(source, Source): raise TypeError(source)
    if not isinstance(source.text, str):
      raise TypeError(f'pithy.lex.Lexer requires a source with `str` text; received {type(source.text).__name__}: {source!r}')
    if mode is None: mode = self.main
    elif mode not in self.modes: raise ValueError(f'unknown mode: {mode!r}')
    pos, end = _range_for_slc(source, slc)
    return self._lex(source=source, pos=pos, end=end, mode=mode, drop=drop, eot=eot)


def eot_token(end:int, mode:str) -> Token:
  'Create a token representing the end-of-text at position `end`.'
  return Token(pos=end, end=end, mode=mode, kind='end_of_text')


def _range_for_slc(source:Source[str], slc:slice|None) -> tuple[int,int]:
  'Return the (pos, end) range for `slc`, or the whole text if `slc` is None.'
  length = len(source.text)
  if slc is None: return (0, length)
  if slc.step not in (None, 1): raise ValueError(f'slice step is not supported: {slc!r}')
  pos, end, _ = slc.indices(length)
  return (pos, max(pos, end))


def validate_name(name:str) -> str:
  if not valid_name_re.fullmatch(name):
    raise Lexer.DefinitionError(f'invalid name: {name!r}')
  if name in reserved_names:
    raise Lexer.DefinitionError(f'name is reserved: {name!r}')
  return name


valid_name_re = re.compile(r'[A-Za-z_]\w*')

reserved_names = frozenset({'end_of_text'})


whitespace_patterns = dict(
  spaces    = r'\ +',
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
