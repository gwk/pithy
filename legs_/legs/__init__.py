# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

__version__ = '0.0.5'

from typing import Any, ClassVar, Collection, Container, Iterator, Pattern

from tolkien import Source, Token


StateTransitions = dict[int,dict[int,int]] # state -> byte -> dst_state.
MatchStateKinds = dict[int,str] # state -> token kind.
ModeData = tuple[int,StateTransitions,MatchStateKinds] # start_node, state_transitions, match_state_kinds.

KindModeTransitions = dict[str,tuple[str,str]]
ModeTransitions = dict[str,KindModeTransitions]


class LexerBase(Iterator[Token]):
  '''
  The base class of generated Python lexers.
  An instance is an iterator of the tokens of a source.
  A lexer class conforms to `tolkien.LexerProtocol` by means of `kinds` and `lex`, so it can be passed to `pithy.parse.Parser`.
  '''

  mode_transitions:ModeTransitions
  pattern_descs:dict[str,str]
  kinds:ClassVar[frozenset[str]] = frozenset() # The pattern kinds, excluding `invalid` and `incomplete`.


  def __init_subclass__(cls, **kwargs:Any) -> None:
    super().__init_subclass__(**kwargs)
    pattern_descs = cls.__dict__.get('pattern_descs')
    if pattern_descs is not None: cls.kinds = frozenset(pattern_descs) - {'invalid', 'incomplete'}


  @classmethod
  def lex(cls, source:Source[bytes], slc:slice|None=None, *, mode:str|None=None, drop:Container[str]=(), eot:bool=False
   ) -> Iterator[Token]:
    '''
    Lex `source`, yielding tokens. See `tolkien.LexerProtocol`.
    `mode` defaults to `main`.
    '''
    lexer = cls(source, slc, mode=(mode or 'main'))
    for token in lexer:
      if token.kind not in drop: yield token
    if eot: yield Token(pos=lexer.end, end=lexer.end, mode=lexer.stack[-1][0], kind='end_of_text')


  def __init__(self, source:Source[bytes], slc:slice|None=None, mode:str='main'):
    '''
    Create a lexer for `source`.
    If `slc` is provided then only that range of the text is lexed; no token extends past its end.
    `mode` is the mode in which lexing starts.
    Together these allow a parser that frames the text by other means to lex each framed range with the appropriate mode.
    '''
    pos, end, step = (slc or slice(None)).indices(len(source.text))
    if step != 1: raise ValueError(f'slice step is not supported: {slc!r}')
    if mode not in self.mode_names(): raise ValueError(f'unknown mode: {mode!r}; modes: {sorted(self.mode_names())}')
    self.source = source
    self.pos = pos
    self.end = max(pos, end)
    self.stack:list[tuple[str,str|None]] = [(mode, None)] # [(mode, pop_kind)].

  @classmethod
  def mode_names(cls) -> Collection[str]:
    'The names of the modes of the lexer.'
    raise NotImplementedError

  def __iter__(self) -> Iterator[Token]: return self

  def __next__(self) -> Token: raise NotImplementedError


class DictLexerBase(LexerBase):

  mode_data:dict[str,ModeData]

  @classmethod
  def mode_names(cls) -> dict[str,ModeData]: return cls.mode_data

  def __next__(self) -> Token:
    text = self.source.text
    assert isinstance(text, bytes)
    len_text = self.end
    pos = self.pos
    if pos == len_text: raise StopIteration
    mode, pop_kind = self.stack[-1]
    mode_start, transitions, match_node_kinds = self.mode_data[mode]

    state = mode_start
    end = None
    kind = 'incomplete'
    while pos < len_text:
      byte = text[pos]
      try: state = transitions[state][byte]
      except KeyError: break
      else: # advance.
        pos += 1
        try: kind = match_node_kinds[state]
        except KeyError: pass
        else: end = pos
    # Matching stopped or reached end of text.
    token_pos = self.pos
    if end is None: # Never reached a match state.
      assert kind == 'incomplete'
      end = pos
    assert token_pos < end # Token cannot be zero length. TODO: support zero-length tokens?
    self.pos = end # Advance lexer state.
    # Check for mode transition.
    if kind == pop_kind:
      self.stack.pop()
    else:
      try: child_frame = self.mode_transitions[mode][kind]
      except KeyError: pass
      else: self.stack.append(child_frame)
    return Token(pos=token_pos, end=end, mode=mode, kind=kind)


class RegexLexerBase(LexerBase):

  mode_patterns:dict[str,Pattern]

  @classmethod
  def mode_names(cls) -> dict[str,Pattern]: return cls.mode_patterns

  def __next__(self) -> Token:
    text = self.source.text
    len_text = self.end
    pos = self.pos
    if pos == len_text: raise StopIteration
    mode, pop_kind = self.stack[-1]
    pattern = self.mode_patterns[mode]
    # Currently we use search as a hack to determine incomplete tokens.
    # This is not totally accurate because incompletes are supposed to be greedy,
    # whereas this approach emits the shortest possible incomplete token.
    # It is also inefficient.
    m = pattern.search(text, pos, len_text)
    assert m is not None
    if not m: # Emit an incomplete token to end.
      self.pos = len_text # type: ignore[unreachable] # Due to assert above.
      return Token(pos=pos, end=len_text, mode=mode, kind='incomplete')
    start = m.start()
    if start > pos: # Emit an incomplete token up to the match; the next search will find the same match (inefficient).
      self.pos = start
      return Token(pos=pos, end=start, mode=mode, kind='incomplete')
    end = m.end()
    kind = m.lastgroup
    assert isinstance(kind, str)
    assert pos < end, (kind, m)
    self.pos = end # Advance lexer state.
    # Check for mode transition.
    if kind == pop_kind:
      self.stack.pop()
    else:
      try: child_frame = self.mode_transitions[mode][kind]
      except KeyError: pass
      else: self.stack.append(child_frame)
    return Token(pos=pos, end=end, mode=mode, kind=kind)
