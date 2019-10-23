# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Dict, Iterator, List, Match, Optional, Pattern, Tuple

from tolkien import Source, Token


StateTransitions = Dict[int,Dict[int,int]] # state -> byte -> dst_state.
MatchStateKinds = Dict[int,str] # state -> token kind.
ModeData = Tuple[int,StateTransitions,MatchStateKinds] # start_node, state_transitions, match_state_kinds.

KindModeTransitions = Dict[str,Tuple[str,str]]
ModeTransitions = Dict[str,KindModeTransitions]


class LexerBase(Iterator[Token]):

  mode_transitions:ModeTransitions
  pattern_descs:Dict[str,str]

  def __init__(self, source:Source[bytes]) -> None:
    self.source = source
    self.pos = 0

  def __iter__(self) -> Iterator[Token]: return self

  def __next__(self) -> Token: raise NotImplementedError


class DictLexerBase(LexerBase):

  mode_data:Dict[str,ModeData]

  def __init__(self, source:Source[bytes]) -> None:
    self.stack:List[Tuple[str,Optional[str]]] = [('main', None)] # [(mode, pop_kind)].
    super().__init__(source=source)

  def __next__(self) -> Token:
    text = self.source.text
    assert isinstance(text, bytes)
    len_text = len(text)
    pos = self.pos
    if pos == len_text: raise StopIteration
    mode, pop_kind = self.stack[-1]
    assert mode in self.mode_data, (mode, list(self.mode_data))
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

  mode_patterns:Dict[str,Pattern]

  def __init__(self, source:Source) -> None:
    self.stack:List[Tuple[str,Optional[str]]] = [('main', None)] # [(mode, pop_kind)].
    super().__init__(source=source)

  def __next__(self) -> Token:
    text = self.source.text
    len_text = len(text)
    pos = self.pos
    if pos == len_text: raise StopIteration
    mode, pop_kind = self.stack[-1]
    pattern = self.mode_patterns[mode]
    # Currently we use search as a hack to determine incomplete tokens.
    # This is not totally accurate because incompletes are supposed to be greedy,
    # whereas this approach emits the shortest possible incomplete token.
    # It is also inefficient.
    m = pattern.search(text, pos)
    assert m is not None
    if not m: # Emit an incomplete token to end.
      self.pos = len_text
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


def ploy_repr(string: str) -> str:
  r = ["'"]
  for char in string:
    if char == '\\': r.append('\\\\')
    elif char == "'": r.append("\\'")
    elif 0x20 <= ord(char) <= 0x7E: r.append(char)
    elif char == '\0': r.append('\\0')
    elif char == '\t': r.append('\\t')
    elif char == '\n': r.append('\\n')
    elif char == '\r': r.append('\\r')
    else: r.append(f'\\{hex(ord(char))};')
  r.append("'")
  return ''.join(r)


# Legs testing.


def test_main(LexerClass) -> None:
  from sys import argv
  for index, arg in enumerate(argv):
    if index == 0: continue
    name = f'arg{index}'
    print(f'\n{name}: {ploy_repr(arg)}')
    source = Source(name=name, text=arg.encode('utf8'))
    for token in LexerClass(source=source):
      kind_desc = LexerClass.pattern_descs[token.kind]
      msg = test_desc(source=source, token=token, kind_desc=kind_desc)
      print(source.diagnostic(token, msg, show_missing_newline=False), end='')


def test_desc(source:Source, token:Token, kind_desc:str) -> str:
  off = 2 # "0_" prefix is the common case.
  base:Optional[int]
  if token.kind == 'num':     base = 10; off = 0
  elif token.kind == 'bin':   base = 2
  elif token.kind == 'quat':  base = 4
  elif token.kind == 'oct':   base = 8
  elif token.kind == 'dec':   base = 10
  elif token.kind == 'hex':   base = 16
  else: base = None

  if base is None: return kind_desc
  val = source.parse_digits(token=token, offset=off, base=base)
  return f'{kind_desc}: {val}'
