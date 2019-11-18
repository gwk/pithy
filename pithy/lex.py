# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Simple lexing using python regular expressions.
'''

import re
from typing import Container, Dict, FrozenSet, Iterable, Iterator, List, NamedTuple, Optional, Pattern, Tuple, Union, cast

from tolkien import Source, Token

from .string import iter_str


class LexError(Exception): pass


class LexMode:
  def __init__(self, name:str, kinds:Iterable[str], *, indents=False) -> None:
    self.name = name
    self.kinds = list(iter_str(kinds))
    self.indents = indents
    self.kind_set:FrozenSet[str] = frozenset() # Filled in by Lexer.
    self.regex:Pattern = cast(Pattern, None) # Filled in by Lexer.

  def __repr__(self) -> str:
    return f'{type(self).__name__}({self.name!r}, kinds={self.kinds}, kind_set={self.kind_set}, indents={self.indents})'


class KindPair(NamedTuple):
  'A pair of kinds that, when encountered in sequence, trigger a mode transition.'
  prev:str
  curr:str

  @staticmethod
  def mk(kind:'LexTransKind') -> 'KindPair':
    if isinstance(kind, str): return KindPair(prev='', curr=kind)
    if isinstance(kind, KindPair): return kind
    raise Lexer.DefinitionError(f'expected `str` or `KindPair`; received {kind!r}')


LexTransKind = Union[str,KindPair]
LexTransKinds = Union[LexTransKind,Iterable[LexTransKind]]
LexTransTuple = Tuple[KindPair,...]

class LexTrans:
  def __init__(self, base:Iterable[str], *, kind:LexTransKinds, mode:str, pop:LexTransKinds, consume:bool) -> None:
    self.bases = tuple(iter_str(base)) # Parent modes.
    self.kinds:LexTransTuple = _mk_pairs_tuple(kind) # Parent mode token kind or pair that causes push.
    self.mode = mode # Child mode.
    self.pops:LexTransTuple = _mk_pairs_tuple(pop)
    self.pop_dict = _mk_trans_pop_dict(self.pops) # Child mode token kinds or pairs as (curr -> prev or '') mapping.
    self.consume = consume # If false, base will consider this token for further push/pop mode transitions.

  def __repr__(self) -> str:
    return f'{type(self).__name__}({self.bases!r}, kinds={self.kinds}, mode={self.mode!r}, pops={self.pops}, consume={self.consume})'

  def should_pop(self, frame_token:Token, token:Token, prev_kind:str) -> bool:
    try: pop_prev = self.pop_dict[token.kind]
    except KeyError: return False
    return not pop_prev or prev_kind == pop_prev
    # TODO: support exact token content matching.


def _mk_pairs_tuple(pop:LexTransKinds) -> LexTransTuple:
  if isinstance(pop, (str, KindPair)): pop = (pop,)
  return tuple(KindPair.mk(el) for el in pop)


def _mk_trans_pop_dict(pops:LexTransTuple) -> Dict[str,str]:
  d:Dict[str,str] = {}
  for pair in pops:
    if pair.curr in d:
      raise Lexer.DefinitionError(f'repeated pop kind key: {pair.curr!r}')
    d[pair.curr] = pair.prev
  return d



class Lexer:
  '''
  Define a Lexer using python regular expressions.
  This class is used to prototype (and bootstrap) Legs lexers.
  Note: A zero-length match, e.g. r'^' causes an exception; otherwise the stream would never advance.
  '''

  class DefinitionError(Exception): pass

  def __init__(self, *, flags='', patterns:Dict[str,str], modes:Iterable[LexMode]=(),
   transitions:Iterable[LexTrans]=()) -> None:

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
      if n == 'invalid':
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

    # Validate and compile modes.
    if not modes:
      modes = [LexMode('main', kinds=self.patterns)]
    self.modes: Dict[str,LexMode] = {}
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
      self.modes[mode.name] = mode
      mode.kind_set = frozenset(kind_set)
      choice_sep = '\n| ' if 'x' in flags else '|'
      mode.regex = re.compile(choice_sep.join(pattern for name, pattern in self.patterns.items() if name in kind_set))
      #^ note: iterate over self.patterns.items (not pattern_names) because the dict preserves the original pattern order.

    kinds = list(self.patterns)
    if any(mode.indents for mode in modes):
      kinds.extend(['indent', 'dedent'])
    self.kinds = frozenset(kinds)

    # Validate transitions.
    assert main is not None
    self.main:str = main
    self.transitions:Dict[Tuple[str,str],Tuple[LexTrans,str]] = {}
    for trans in transitions:
      if not isinstance(trans, LexTrans): raise Lexer.DefinitionError(f'expected `LexTrans`; received {trans!r}')
      for base in trans.bases:
        if base not in self.modes: raise Lexer.DefinitionError(f'unknown parent mode: {base!r}')
      if trans.mode not in self.modes: raise Lexer.DefinitionError(f'unknown child mode: {trans.mode!r}')
      for label, pairs in [('push', trans.kinds), ('pop', trans.pops)]:
        for pair in pairs:
          for i, k in enumerate(pair):
            if i == 0 and not k: continue # Prev is allowed to be empty.
            if k and k not in self.kinds: raise Lexer.DefinitionError(f'unknown mode {label} pattern: {k!r}')
      for base in trans.bases:
        for kind_pair in trans.kinds:
          key = (base, kind_pair.curr)
          try: _, existing = self.transitions[key]
          except KeyError: # No conflict.
            self.transitions[key] = (trans, kind_pair.prev)
          else: # Conflict.
            raise Lexer.DefinitionError(f'conflicting transitions:\n  {existing}\n  {trans}')


  def _lex_inv(self, pos:int, end:int, mode:str) -> Token:
    return Token(pos=pos, end=end, mode=mode, kind='invalid')


  def _lex_one(self, regex:Pattern, source:Source[str], pos:int, end:int, mode:str) -> Token:
    m = regex.search(source.text, pos)
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


  def _lex(self, stack:List[Tuple[LexTrans,Token]], source:Source[str], pos:int, end:int, drop:Container[str], eot:bool
   ) -> Iterator[Token]:
    assert isinstance(source, Source)
    prev_kind = ''
    indent_stack:List[int] = []
    while pos < end:
      # Get the current frame and mode.
      frame_trans, frame_token = stack[-1]
      mode = self.modes[frame_trans.mode]
      # Lex one token.
      token = self._lex_one(mode.regex, source, pos=pos, end=end, mode=mode.name)
      kind = token.kind
      pos = token.end
      # Check if we should synthesize indent or dedent tokens.
      if mode.indents and prev_kind == 'newline':
        if kind == 'spaces': # Generate indent or dedent tokens.
          indent_len = len(source[token])
          while indent_stack and indent_stack[-1] > indent_len:
            yield token.pos_token(kind='dedent')
            prev_kind = 'dedent' # Hack to allow for transitions on spaces following indent/dedent.
            indent_stack.pop()
          if not indent_stack or indent_stack[-1] < indent_len:
            yield token.pos_token(kind='indent')
            prev_kind = 'indent' # Hack to allow for transitions on spaces following indent/dedent.
            indent_stack.append(indent_len)
        elif kind != 'newline': # Empty lines do not affect indent stack. All others pop the entire indent stack.
          while indent_stack:
            yield token.pos_token(kind='dedent')
            prev_kind = 'dedent' # Hack to allow for transitions on spaces following indent/dedent.
            indent_stack.pop()
      # Yield the current token.
      if kind not in drop:
        yield token
      # Perform mode transitions.
      try:
        # Check if we should pop one or more modes.
        while frame_trans.should_pop(frame_token=frame_token, token=token, prev_kind=prev_kind):
          stack.pop()
          if frame_trans.consume:
            raise _BreakFromModeSwitching # This frame "consumes" the token.
          frame_trans, frame_token = stack[-1]
        # Check if we should push a child mode.
        try: push_trans, push_prev_kind = self.transitions[(frame_trans.mode, kind)]
        except KeyError: pass
        else:
          if not push_prev_kind or prev_kind == push_prev_kind:
            stack.append((push_trans, token))
            kind = '' # Make prev_kind empty on the next iteration.
      except _BreakFromModeSwitching: pass
      prev_kind = kind
    while indent_stack:
      yield token.pos_token(kind='dedent')
      prev_kind = 'dedent' # Hack to allow for transitions on spaces following indent/dedent.
      indent_stack.pop()
    if eot:
      yield eot_token(source, mode=stack[-1][0].mode)


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
      yield (source, eot_token(source, mode=stack[-1][0].mode))


  def root_frame(self, mode:str) -> Tuple[LexTrans,Token]:
    'The root frame is degenerate; because it has an empty pops set it will never get popped; base and kind are never accessed.'
    return (LexTrans(base='', kind='', mode=mode, pop=frozenset(), consume=False), Token(0, 0, mode='', kind=''))


class _BreakFromModeSwitching(Exception): pass


def eot_token(source:Source[str], mode:str) -> Token:
  'Create a token representing the end-of-text.'
  end = len(source.text)
  return Token(pos=end, end=end, mode=mode, kind='end_of_text')


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
