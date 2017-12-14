# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Dict, Iterator, List, Match, NamedTuple, Optional, Tuple
from pithy.lex import Lexer as _Lexer


class Token(NamedTuple):
  kind: str
  pos: int
  end: int


class Source:

  def __init__(self, name: str, text: bytes) -> None:
    self.name = name
    self.text = text
    self.newline_positions: List[int] = []

  def __repr__(self): return f'{self.__class__.__name__}({self.name})'

  def get_line_index(self, pos: int) -> int:
    for (index, newline_pos) in enumerate(self.newline_positions):
      if pos <= newline_pos:
        return index
    return len(self.newline_positions)

  def get_line_start(self, pos: int) -> int:
    return self.text.rfind(b'\n', 0, pos) + 1 # rfind returns -1 for no match, happens to work perfectly.

  def get_line_end(self, pos: int) -> int:
    line_end = self.text.find(b'\n', pos)
    return len(self.text) if line_end == -1 else line_end


  def get_line_str(self, pos: int, end: int) -> str:
    line_bytes = self.text[pos:end]
    try: return line_bytes.decode('utf8')
    except UnicodeDecodeError: return repr(line_bytes) # TODO: improve messaging around decode errors.


  def diagnostic_for_token(self, token: Token, msg: str = '', show_missing_newline: bool = True) -> str:
    pos = token.pos
    end = token.end
    line_pos = self.get_line_start(pos)
    line_idx = self.text.count(b'\n', 0, pos) # number of newlines preceeding pos.
    return self.diagnostic_for_pos(pos=pos, end=end, line_pos=line_pos, line_idx=line_idx, msg=msg, show_missing_newline=show_missing_newline)


  def diagnostic_at_end(self, msg: str = '', show_missing_newline: bool = True) -> str:
    last_pos = len(self.text) - 1
    line_pos: int
    line_idx: int
    newline_pos = self.text.rfind(b'\n')
    if newline_pos >= 0: #
      if newline_pos == last_pos: # terminating newline.
        line_pos = self.get_line_start(pos=newline_pos)
        line_idx = self.text.count(b'\n', 0, newline_pos) # number of newlines preceeding newline_pos.
      else: # no terminating newline.
        line_pos = newline_pos + 1
        line_idx = len(self.newline_positions)
    else:
      line_pos = 0
      line_idx = 0
    line_str = self.get_line_str(line_pos, self.get_line_end(line_pos))
    return self._diagnostic(pos=last_pos, end=last_pos, line_pos=line_pos, line_idx=line_idx, line_str=line_str, msg=msg, show_missing_newline=show_missing_newline)


  def diagnostic_for_pos(self, pos: int, end: int, line_pos: int, line_idx: int, msg: str = '', show_missing_newline: bool = True) -> str:
    if end is None: end = pos
    line_end = self.get_line_end(pos)
    if end <= line_end: # single line.
      return self._diagnostic(pos=pos, end=end, line_pos=line_pos, line_idx=line_idx,
        line_str=self.get_line_str(line_pos, line_end), msg=msg, show_missing_newline=show_missing_newline)
    else: # multiline.
      end_line_idx = self.get_line_index(pos)
      end_line_pos = self.get_line_start(end)
      end_line_end = self.get_line_end(end)
      return (
        self._diagnostic(pos=pos, end=line_end, line_pos=line_pos, line_idx=line_idx,
          line_str=self.get_line_str(line_pos, line_end), msg=msg, show_missing_newline=show_missing_newline) +
        self._diagnostic(pos=end_line_pos, end=end, line_pos=end_line_pos, line_idx=end_line_idx,
          line_str=self.get_line_str(end_line_pos, end_line_end), msg=msg, show_missing_newline=show_missing_newline))


  def _diagnostic(self, pos: int, end: int, line_pos: int, line_idx: int, line_str: str, msg: str, show_missing_newline: bool) -> str:

    assert pos >= 0
    assert pos <= end
    assert line_pos <= pos
    assert end <= line_pos + len(line_str)

    tab = '\t'
    newline = '\n'
    space = ' '
    caret = '^'
    tilde = '~'

    line_end = line_pos + len(line_str)

    src_line: str
    if line_str[-1] == newline:
      last_idx = len(line_str) - 1
      s = line_str[:-1]
      if pos == last_idx or end == line_end:
        src_line = s + "\u23CE" # RETURN SYMBOL.
      else:
        src_line = s
    elif show_missing_newline:
      src_line = line_str + "\u23CE\u0353" # RETURN SYMBOL, COMBINING X BELOW.
    else:
      src_line = line_str

    src_bar = "| " if src_line else "|"

    under_chars = []
    for char in line_str[:(pos - line_pos)]:
      under_chars.append(tab if char == tab else space)
    if pos >= end:
      under_chars.append(caret)
    else:
      for _ in range(pos, end):
        under_chars.append(tilde)
    underline = ''.join(under_chars)

    def col_str(pos: int) -> str:
      return str((pos - line_pos) + 1)

    col = f'{col_str(pos)}-{col_str(end)}' if pos < end else col_str(pos)

    msg_space = "" if (not msg or msg.startswith('\n')) else " "
    return f'{self.name}:{line_idx+1}:{col}:{msg_space}{msg}\n{src_bar}{src_line}\n  {underline}\n'


  def bytes_for(self, token: Token, offset=0) -> bytes:
    return self.text[token.pos+offset:token.end]

  '''
  def parse_signed_number(self, token: Token) -> Int:
    negative: Bool
    base: Int
    offset: Int
    (negative, offset) = parseSign(token: token)
    (base, offset) = parseBasePrefix(token: token, offset: offset)
    return try parseSignedDigits(token: token, from: offset, base: base, negative: negative)
  }

  public func parseSign(token: Token) -> (negative: Bool, offset: Int) {
    switch text[token.pos] {
    case 0x2b: return (false, 1)  // '+'
    case 0x2d: return (true, 1)   // '-'
    default: return (false, 0)
    }
  }

  public func parseBasePrefix(token: Token, offset: Int) -> (base: Int, offset: Int):
    let pos = token.pos + offset
    if text[pos] != 0x30 { // '0'
      return (base: 10, offset: offset)
    }
    let base: Int
    switch text[pos + 1] { // byte.
    case 0x62: base = 2 // 'b'
    case 0x64: base = 10 // 'd'
    case 0x6f: base = 8 // 'o'
    case 0x71: base = 4 // 'q'
    case 0x78: base = 16 // 'x'
    default: return (base: 10, offset: offset)
    }
    return (base: base, offset: offset + 2)
  '''


  def parse_digits(self, token: Token, offset: int, base: int) -> int:
    val = 0
    for char in self.bytes_for(token, offset=offset).decode('utf8'):
      try: v = int(char, base)
      except ValueError: continue # ignore digit.
      val = val*base + v
    return val



class Lexer(Iterator[Token]):

  def __init__(self, source: Source) -> None:
    self.source = source
    self.stack: List[Tuple[int, Optional[str]]] = [(0, None)] # [(mode_start, pop_kind)].
    self.pos = 0

  transitions: Dict[int, Dict[int, int]] = {}
  match_node_kinds: Dict[int, str] = {}
  mode_transitions: Dict[int, Dict[str, Tuple[int, str]]] = {} # parent_start->(parent_kind->child_start_kind_pair).
  rule_descs: Dict[str, str] = {}

  def __iter__(self) -> Iterator[Token]: return self

  def __next__(self) -> Token:
    text = self.source.text
    len_text = len(text)
    mode_start, pop_kind = self.stack[-1]
    pos = self.pos
    state = mode_start
    end = None
    kind = 'incomplete'
    while pos < len_text:
      byte = text[pos]
      try: state = self.transitions[state][byte]
      except KeyError: break
      else: # advance.
        pos += 1
        try: kind = self.match_node_kinds[state]
        except KeyError: pass
        else: end = pos
    # matching stopped or reached end of text.
    if pos == self.pos: # no more tokens; done.
      assert pos == len_text
      raise StopIteration
    if end is None:
      assert kind == 'incomplete'
      end = pos
    assert self.pos < end
    token_pos = self.pos
    self.pos = end
    if kind == pop_kind:
      self.stack.pop()
    else:
      try: child_pair = self.mode_transitions[mode_start][kind]
      except KeyError: pass
      else: self.stack.append(child_pair)
    return Token(pos=token_pos, end=end, kind=kind)


def ployRepr(string: str) -> str:
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
    print(f'\n{name}: {ployRepr(arg)}')
    source = Source(name=name, text=arg.encode('utf8'))
    for token in LexerClass(source=source):
      kind_desc = LexerClass.rule_descs[token.kind]
      msg = test_desc(source=source, token=token, kind_desc=kind_desc)
      print(source.diagnostic_for_token(token, msg=msg, show_missing_newline=False), end='')


def test_desc(source: Source, token: Token, kind_desc: str) -> str:
  off = 2 # "0_" prefix is the common case.
  base: Optional[int]
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
