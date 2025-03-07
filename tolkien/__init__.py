# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Token and Source classes for implementing lexers and parsers.
'''

from typing import Any, Generic, NamedTuple, NoReturn, Optional, Protocol, TypeVar, Union


class Token(NamedTuple):
  pos:int
  end:int
  mode:str
  kind:str

  def __str__(self) -> str:
    return f'{self.pos}-{self.end}:{self.kind!r}'

  def __repr__(self) -> str:
    return f'{type(self).__qualname__}(pos={self.pos}, end={self.end}, mode={self.mode}, kind={self.kind})'

  @property
  def mode_kind(self) -> str:
    return f'{self.mode}.{self.kind}'

  @property
  def slice(self) -> slice:
    return slice(self.pos, self.end)

  def pos_token(self, kind:str|None=None) -> 'Token':
    'Create a new token with the same position as `token` but with zero length.'
    if kind is None: kind = self.kind
    return Token(pos=self.pos, end=self.pos, mode=self.mode, kind=kind)

  def end_token(self, kind:str|None=None) -> 'Token':
    'Create a new token with position and end set to `token.end`.'
    if kind is None: kind = self.kind
    return Token(pos=self.end, end=self.end, mode=self.mode, kind=kind)


class HasToken(Protocol):
  token:Token

Syntax = Union[Token,HasToken]

def get_syntax_token(syntax:Syntax) -> Token:
  return syntax if isinstance(syntax, Token) else syntax.token


SyntaxMsg = tuple[Syntax,str]

SourceText = Union[str,bytes,bytearray]
_Text = TypeVar('_Text', bound=SourceText)


class Source(Generic[_Text]):

  def __init__(self, name:str, text:_Text, *, line_idx_start:int=0, show_missing_newline:bool=True):
    assert isinstance(text, (str,bytes,bytearray))
    self.name = name
    self.text = text
    self.line_idx_start = line_idx_start
    self.show_missing_newline = show_missing_newline
    self.newline_positions:list[int] = []


  def update_line_positions(self) -> None:
    'Lazily update newline positions array. This is not quite optimal and should be optimized eventually.'
    start = self.newline_positions[-1] + 1 if self.newline_positions else 0
    n = '\n' if isinstance(self.text, str) else b'\n'
    for i in range(start, len(self.text)):
      if self.text[i] == n: self.newline_positions.append(i)


  def __repr__(self):
    return f'{self.__class__.__name__}({self.name!r}, text=<{type(self.text).__name__}[{len(self.text)}]>)'


  def get_line_index(self, pos:int) -> int:
    self.update_line_positions()
    for (index, newline_pos) in enumerate(self.newline_positions, start=self.line_idx_start):
      if pos <= newline_pos:
        return index

    newline_count = self.line_idx_start + len(self.newline_positions)
    text = self.text
    if isinstance(text, str):
      if pos == len(text) and text.endswith('\n'): return newline_count - 1
    else:
      assert isinstance(text, (bytes, bytearray))
      if pos == len(text) and text.endswith(b'\n'): return newline_count -1
    return newline_count


  def get_line_start(self, pos:int) -> int:
    'Return the character index for the start of the line containing `pos`.'
    text = self.text
    if isinstance(text, str):
      if pos == len(text) and text.endswith('\n'): pos -= 1
      return text.rfind('\n', 0, pos) + 1 # rfind returns -1 for no match, so just add one.
    else:
      assert isinstance(text, (bytes, bytearray))
      if pos == len(text) and text.endswith(b'\n'): pos -= 1
      return text.rfind(b'\n', 0, pos) + 1


  def get_line_end(self, pos:int) -> int:
    '''
    Return the character index for the end of the line containing `pos`;
    a newline is considered the final character of a line.
    '''
    text = self.text
    if isinstance(text, str):
      newline_pos = text.find('\n', pos)
    else:
      assert isinstance(text, (bytes, bytearray))
      newline_pos = text.find(b'\n', pos)
    return len(text) if newline_pos == -1 else newline_pos + 1


  def get_line_str(self, pos:int, end:int) -> str:
    assert pos <= end, (pos, end)
    line = self.text[pos:end]
    if isinstance(line, str): return line
    assert isinstance(line, (bytes, bytearray))
    return line.decode(errors='replace')

  def eot_token(self) -> Token:
    end = len(self.text)
    return Token(pos=end, end=end, mode='none', kind='eot')


  def name_line_prefix(self, pos:int) -> str:
    return f'{self.name}:{self.get_line_index(pos)+1}:'


  def diagnostic(self, *syntax_msgs:SyntaxMsg|None, prefix:str='') -> str:
    return ''.join(
      self.diagnostic_for_token(get_syntax_token(sm[0]), sm[1], prefix=prefix) for sm in syntax_msgs if sm is not None)


  def fail(self, *syntax_msgs:SyntaxMsg|None, prefix:str='') -> NoReturn:
    exit(self.diagnostic(*syntax_msgs, prefix=prefix))


  def diagnostic_for_token(self, token:Token, msg:str, *, prefix:str='') -> str:
    return self.diagnostic_for_pos(pos=token.pos, end=token.end, msg=msg, prefix=prefix)


  def diagnostic_for_pos(self, pos:int, *, end:int, prefix:str='', msg:str = '') -> str:
    line_idx = self.get_line_index(pos)
    line_pos = self.get_line_start(pos)
    line_end = self.get_line_end(pos)
    if end <= line_end: # single line.
      return self._diagnostic(pos=pos, end=end, line_pos=line_pos, line_end=line_end, line_idx=line_idx, prefix=prefix, msg=msg)
    else: # multiline.
      end_line_idx = self.get_line_index(end)
      end_line_pos = self.get_line_start(end)
      end_line_end = self.get_line_end(end)
      return (
        self._diagnostic(pos=pos, end=line_end, line_pos=line_pos, line_end=line_end,  line_idx=line_idx, prefix=prefix, msg=msg) +
        self._diagnostic(pos=end_line_pos, end=end, line_pos=end_line_pos, line_end=end_line_end, line_idx=end_line_idx,
          prefix=prefix, msg='ending here.'))


  def _diagnostic(self, pos:int, end:int, line_pos:int, line_end:int, line_idx:int, *, prefix:str, msg:str) -> str:

    assert pos >= 0
    assert pos <= end
    assert line_pos <= pos

    line_str = self.get_line_str(line_pos, line_end)
    assert end <= line_pos + len(line_str)

    tab = '\t'
    newline = '\n'
    space = ' '
    caret = '^'
    tilde = '~'

    src_line:str
    if line_str and line_str[-1] == newline:
      last_idx = len(line_str) - 1
      s = line_str[:-1]
      if pos == last_idx or end == line_end:
        src_line = s + "\u23CE" # RETURN SYMBOL.
      else:
        src_line = s
    elif self.show_missing_newline:
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

    def col_str(pos:int) -> str:
      return str((pos - line_pos) + 1)

    pre = (prefix + ': ') if prefix else ''
    col = f'{col_str(pos)}-{col_str(end)}' if pos < end else col_str(pos)

    msg_space = "" if (not msg or msg.startswith('\n')) else " "
    name_colon = (self.name + ':') if self.name else ''
    return f'{pre}{name_colon}{line_idx+1}:{col}:{msg_space}{msg}\n{src_bar}{src_line}\n  {underline}\n'


  def bytes_for(self, token:Token, offset=0) -> bytes:
    text = self.text
    if isinstance(text, str):
      return text[token.pos+offset:token.end].encode()
    else:
      assert isinstance(text, (bytes, bytearray))
      return text[token.pos+offset:token.end]


  def str_for(self, token:Token, offset=0) -> str:
    text = self.text
    if isinstance(text, str):
      return text[token.pos+offset:token.end]
    else:
      assert isinstance(text, (bytes, bytearray))
      return text[token.pos+offset:token.end].decode(errors='replace')


  def __getitem__(self, token:Token) -> str:
    text = self.text
    if isinstance(text, str):
      return text[token.pos:token.end]
    else:
      assert isinstance(text, (bytes, bytearray))
      return text[token.pos:token.end].decode(errors='replace')


  '''
  def parse_signed_number(self, token:Token) -> Int:
    negative:Bool
    base:Int
    offset:Int
    (negative, offset) = parseSign(token:token)
    (base, offset) = parseBasePrefix(token:token, offset:offset)
    return try parseSignedDigits(token:token, from:offset, base:base, negative:negative)
  }

  public func parseSign(token:Token) -> (negative:Bool, offset:Int) {
    switch text[token.pos] {
    case 0x2b: return (false, 1)  // '+'
    case 0x2d: return (true, 1)   // '-'
    default: return (false, 0)
    }
  }

  public func parseBasePrefix(token:Token, offset:Int) -> (base:Int, offset:Int):
    let pos = token.pos + offset
    if text[pos] != 0x30 { // '0'
      return (base: 10, offset: offset)
    }
    let base:Int
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


  def parse_digits(self, token:Token, offset:int, base:int) -> int:
    val = 0
    for char in self.str_for(token, offset=offset):
      try: v = int(char, base)
      except ValueError: continue # ignore digit.
      val = val*base + v
    return val
