# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Token and Source classes for implementing lexers and parsers.
'''

__version__ = '0.0.3'


from bisect import bisect_left
from dataclasses import dataclass
from typing import Callable, Container, Generic, Iterator, NoReturn, Protocol, runtime_checkable, TypeVar
from unicodedata import category, east_asian_width


@runtime_checkable
class HasSlc(Protocol):
  @property
  def slc(self) -> slice: ...


Syntax = slice|HasSlc


def get_syntax_slc(syntax:Syntax) -> slice:
  return syntax if isinstance(syntax, slice) else syntax.slc


def slc_str(slc:slice) -> str: return f'{slc.start}…{slc.stop}'


class SyntaxError(Exception):

  syntax:Syntax
  msg:str

  def __init__(self, syntax:Syntax, msg:str):
    self.syntax = syntax
    self.msg = msg
    super().__init__(msg)


_setattr = object.__setattr__


@dataclass(frozen=True)
class Token:
  '''
  The `Token` class references a slice of a source text, labeling it with `mode` and `kind` strings.
  Therefore to retreive the text content of a token, one must also have a reference to the source text.
  '''

  slc:slice
  mode:str
  kind:str

  def __init__(self, pos:int, end:int, mode:str='main', kind:str='?'):
    _setattr(self, 'slc', slice(pos, end))
    _setattr(self, 'mode', mode)
    _setattr(self, 'kind', kind)

  def __str__(self) -> str:
    return f'{slc_str(self.slc)}:{self.short_mode_kind}'

  def __repr__(self) -> str:
    mode_str = '' if self.mode == 'main' else f', mode={self.mode!r}'
    kind_str = '' if self.kind == '?' else f', kind={self.kind!r}'
    return f'{type(self).__qualname__}({self.slc.start}, {self.slc.stop}{mode_str}{kind_str})'

  @property
  def mode_kind(self) -> str:
    return f'{self.mode}.{self.kind}'

  @property
  def short_mode_kind(self) -> str:
    return self.kind if self.mode == 'main' else self.mode_kind

  @property
  def pos(self) -> int: return int(self.slc.start)

  @property
  def end(self) -> int: return int(self.slc.stop)

  def pos_token(self, kind:str|None=None) -> 'Token':
    'Create a new token with the same position as `token` but with zero length.'
    if kind is None: kind = self.kind
    return Token(pos=self.pos, end=self.pos, mode=self.mode, kind=kind)

  def end_token(self, kind:str|None=None) -> 'Token':
    'Create a new token with position and end set to `token.end`.'
    if kind is None: kind = self.kind
    return Token(pos=self.end, end=self.end, mode=self.mode, kind=kind)


SyntaxMsg = tuple[Syntax,str]

_Text = TypeVar('_Text', str, bytes, bytearray)


class Source(Generic[_Text]):

  name:str
  text:_Text
  line_idx_start:int
  show_missing_newline:bool
  newline_positions:list[int]

  def __init__(self, name:str, text:_Text, *, line_idx_start:int=0, show_missing_newline:bool=True):
    assert isinstance(text, (str,bytes,bytearray))
    self.name = name
    self.text = text
    self.line_idx_start = line_idx_start
    self.show_missing_newline = show_missing_newline
    self.newline_positions:list[int] = []


  @staticmethod
  def from_path(path:str) -> Source[str]:
    with open(path) as f:
      return Source(name=path, text=f.read())


  def update_newline_positions(self, pos:int|None=None) -> None:
    'Lazily update the newline positions array up to `pos`. `pos` must be less than or equal to the text length.'
    if pos is None: pos = len(self.text)
    start = self.newline_positions[-1] + 1 if self.newline_positions else 0
    newline_char = '\n' if isinstance(self.text, str) else 0xa
    for i in range(start, pos):
      if self.text[i] == newline_char: self.newline_positions.append(i)


  def __repr__(self) -> str:
    return f'{self.__class__.__name__}({self.name!r}, text=<{type(self.text).__name__}[{len(self.text)}]>)'


  def get_line_index(self, pos:int) -> int:
    text = self.text
    length = len(text)
    if not (0 <= pos <= length): raise IndexError(pos)
    self.update_newline_positions(pos)
    if pos == length:
      newline_count = self.line_idx_start + len(self.newline_positions)
      ends_with_newline = text.endswith('\n') if isinstance(text, str) else text.endswith(b'\n')
      #^ Do not compare the last element: indexing bytes yields an int.
      return (newline_count - 1) if ends_with_newline else newline_count
      #^ Special case so that the EOF position does not get a line index beyond the last line.
    return self.line_idx_start + bisect_left(self.newline_positions, pos)
    #^ Count the newlines strictly before `pos`; a newline belongs to the line that it ends.


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


  def line_slices(self) -> Iterator[slice]:
    self.update_newline_positions()
    prev_newline_pos = -1
    for newline_pos in self.newline_positions:
      yield slice(prev_newline_pos+1, newline_pos+1)
      prev_newline_pos = newline_pos
    if prev_newline_pos < len(self.text) - 1:
      yield slice(prev_newline_pos+1, len(self.text))


  def line_texts(self) -> Iterator[_Text]:
    text:_Text = self.text
    for slc in self.line_slices():
      yield text[slc]


  def eot_token(self) -> Token:
    end = len(self.text)
    return Token(pos=end, end=end, mode='none', kind='eot')


  def name_line_prefix(self, pos:int) -> str:
    return f'{self.name}:{self.get_line_index(pos)+1}:'


  def diagnostic(self, *syntax_msgs:SyntaxMsg|None, prefix:str='', text_width:TextWidth|None=None) -> str:
    '''
    Return the plain text diagnostic for each syntax and message pair.
    See `Diagnostic.render` for `text_width`.
    '''
    return ''.join(d.render(text_width=text_width) for d in self.diagnostics(*syntax_msgs, prefix=prefix))


  def fail(self, *syntax_msgs:SyntaxMsg|None, prefix:str='', text_width:TextWidth|None=None) -> NoReturn:
    exit(self.diagnostic(*syntax_msgs, prefix=prefix, text_width=text_width))


  def diagnostics(self, *syntax_msgs:SyntaxMsg|None, prefix:str='') -> list[Diagnostic]:
    '''
    Return the diagnostics for each syntax and message pair, as structured pieces that the caller can render in any format.
    A syntax that spans several lines produces two diagnostics, for its first and last lines.
    '''
    diagnostics:list[Diagnostic] = []
    for sm in syntax_msgs:
      if sm is None: continue
      slc = get_syntax_slc(sm[0])
      diagnostics.extend(self.diagnostics_for_pos(pos=slc.start, end=slc.stop, msg=sm[1], prefix=prefix))
    return diagnostics


  def diagnostic_for_syntax(self, syntax:Syntax, msg:str, *, prefix:str='') -> str:
    return self.diagnostic((syntax, msg), prefix=prefix)


  def diagnostic_for_pos(self, pos:int, *, end:int, prefix:str='', msg:str = '') -> str:
    return ''.join(d.render() for d in self.diagnostics_for_pos(pos, end=end, prefix=prefix, msg=msg))


  def diagnostics_for_pos(self, pos:int, *, end:int, prefix:str='', msg:str = '') -> list[Diagnostic]:
    length = len(self.text)
    orig_pos, orig_end = pos, end
    pos = min(max(pos, 0), length)
    end = min(max(end, pos), length)
    if pos != orig_pos or end != orig_end:
      # The caller passed an invalid position. Raising would lose the message, so report the nearest valid position with a note.
      note = f'(invalid position {orig_pos}:{orig_end}; text length is {length})'
      msg = f'{msg} {note}' if msg else note
    line_idx = self.get_line_index(pos)
    line_pos = self.get_line_start(pos)
    line_end = self.get_line_end(pos)
    if end <= line_end: # single line.
      return [self._diagnostic(pos=pos, end=end, line_pos=line_pos, line_end=line_end, line_idx=line_idx, prefix=prefix, msg=msg)]
    else: # multiline.
      end_line_idx = self.get_line_index(end)
      end_line_pos = self.get_line_start(end)
      end_line_end = self.get_line_end(end)
      return [
        self._diagnostic(pos=pos, end=line_end, line_pos=line_pos, line_end=line_end,  line_idx=line_idx, prefix=prefix, msg=msg),
        self._diagnostic(pos=end_line_pos, end=end, line_pos=end_line_pos, line_end=end_line_end, line_idx=end_line_idx,
          prefix=prefix, msg='ending here.')]


  def _diagnostic(self, pos:int, end:int, line_pos:int, line_end:int, line_idx:int, *, prefix:str, msg:str) -> Diagnostic:

    text = self.text
    if not isinstance(text, str):
      # A position inside a multibyte character is widened to the whole character, so that the line decodes intact.
      is_empty = (pos == end)
      pos = _utf8_char_bounds(text, pos)[0]
      end = pos if is_empty else _utf8_char_bounds(text, end)[1]

    assert pos >= 0
    assert pos <= end
    assert line_pos <= pos
    assert end <= line_end

    # Positions index the text, which may be bytes, whereas the diagnostic is laid out in characters.
    # Decode the parts separately so that each part is measured in characters.
    before = self.get_line_str(line_pos, pos)
    within = self.get_line_str(pos, end)
    after = self.get_line_str(end, line_end)

    # The newline is removed from the parts and represented by a symbol, which is shown only when the syntax touches it.
    newline_symbol = ''
    is_newline_within = False
    if before.endswith('\n'): # The end of text, following a final newline.
      before = before[:-1] + '\u23ce' # The position is past the newline, so the symbol is part of the preceding text.
    elif within.endswith('\n'):
      within = within[:-1]
      is_newline_within = True
      newline_symbol = '\u23ce' # RETURN SYMBOL.
    elif after.endswith('\n'):
      after = after[:-1]
      if not (within or after): newline_symbol = '\u23ce' # The position is that of the newline.
    elif self.show_missing_newline:
      newline_symbol = '\u23ce\u0353' # RETURN SYMBOL, COMBINING X BELOW.

    return Diagnostic(prefix=prefix, name=self.name, line_idx=line_idx, msg=msg, before=before, within=within, after=after,
      newline_symbol=newline_symbol, is_newline_within=is_newline_within)


  def bytes_for(self, token:Token, offset:int=0) -> bytes:
    text = self.text
    if isinstance(text, str):
      return text[token.pos+offset:token.end].encode()
    else:
      assert isinstance(text, (bytes, bytearray))
      return bytes(text[token.pos+offset:token.end])


  def str_for(self, token:Token, offset:int=0) -> str:
    text = self.text
    if isinstance(text, str):
      return text[token.pos+offset:token.end]
    else:
      assert isinstance(text, (bytes, bytearray))
      return text[token.pos+offset:token.end].decode(errors='replace')


  def __getitem__(self, idx:int|Syntax) -> str:
    text = self.text
    slc = slice(idx,idx+1) if isinstance(idx, int) else get_syntax_slc(idx)
    if isinstance(text, str):
      return text[slc]
    else:
      assert isinstance(text, (bytes, bytearray))
      return text[slc].decode(errors='replace')


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



def _utf8_char_bounds(text:bytes|bytearray, idx:int) -> tuple[int,int]:
  '''
  Return the bounds of the UTF-8 character that the byte position `idx` falls inside of, or `(idx, idx)` if it is on a boundary.
  This never raises for malformed text: a position that does not follow a lead byte reaching past it is treated as a boundary,
  and a truncated character ends at its last continuation byte.
  '''
  length = len(text)
  if not (0 < idx < length and _is_utf8_continuation(text[idx])): return (idx, idx)
  start = idx - 1
  while start > 0 and idx - start < 3 and _is_utf8_continuation(text[start]): start -= 1
  lead = text[start]
  if lead >= 0xf0: char_len = 4
  elif lead >= 0xe0: char_len = 3
  elif lead >= 0xc0: char_len = 2
  else: return (idx, idx) # Not a lead byte.
  if start + char_len <= idx: return (idx, idx) # The preceding character is complete; this is a stray continuation byte.
  end = idx
  while end < min(start + char_len, length) and _is_utf8_continuation(text[end]): end += 1
  return (start, end)


def _is_utf8_continuation(byte:int) -> bool: return 0x80 <= byte < 0xc0


type TextWidth = Callable[[str],int]
'''
A function that returns the number of terminal columns that a string occupies.
It takes a whole string rather than a character so that it can account for sequences such as emoji joined by zero width joiners.
The string never contains a tab or a newline.
'''


@dataclass(frozen=True)
class Diagnostic:
  '''
  The pieces of a diagnostic for one source line, which can be rendered in any format.
  The line is split into the text before, within and after the reported syntax; none of these contain the newline.
  A point diagnostic has no text within: it reports a position between characters.
  At the end of text following a final newline, the position is past the newline, so `before` ends with the newline symbol.
  All text is `str`, regardless of the source text type.
  '''

  prefix:str # Optional prefix of the location, e.g. 'error'.
  name:str # The source name.
  line_idx:int # Zero-based line index, including the source `line_idx_start`.
  msg:str
  before:str
  within:str
  after:str
  newline_symbol:str # The symbol to show at the end of the line, or empty; distinguishes a present newline from a missing one.
  is_newline_within:bool # The syntax includes the newline.


  @property
  def is_point(self) -> bool: return not (self.within or self.is_newline_within)

  @property
  def col(self) -> int:
    'The zero-based column of the syntax, in characters.'
    return len(self.before)

  @property
  def col_end(self) -> int: return self.col + len(self.within) + self.is_newline_within

  @property
  def location(self) -> str:
    'The location label, with one-based line and columns, e.g. `error: name:1:2-4:`.'
    pre = (self.prefix + ': ') if self.prefix else ''
    name_colon = (self.name + ':') if self.name else ''
    col_desc = str(self.col+1) if self.is_point else f'{self.col+1}-{self.col_end+1}'
    return f'{pre}{name_colon}{self.line_idx+1}:{col_desc}:'


  def render(self, text_width:TextWidth|None=None) -> str:
    '''
    Render the diagnostic as plain text: the location and message, the source line, and a line that marks the syntax.
    A point is marked with a caret, other syntax with tildes.

    The marks are aligned by terminal column, using `text_width` to measure the text; it defaults to `stdlib_text_width`.
    This is a best effort: terminals disagree about the widths of some characters, and ambiguous width characters are counted as one.
    The text within the syntax is measured as a continuation of the text before it, so that a sequence spanning the two is intact.
    Tabs are copied into the marks line so that alignment does not depend on the tab width.
    '''
    if text_width is None: text_width = stdlib_text_width
    msg = self.msg
    msg_space = '' if (not msg or msg.startswith('\n')) else ' '
    src_line = self.before + self.within + self.after + self.newline_symbol
    src_bar = '| ' if src_line else '|'
    indent = _marks(self.before, ' ', text_width)
    if self.is_point:
      marks = '^'
    else:
      marks = _marks(self.before + self.within, '~', text_width)[len(indent):] + ('~' if self.is_newline_within else '')
      if not marks: marks = '~' # The syntax consists of zero-width characters.
    return f'{self.location}{msg_space}{msg}\n{src_bar}{src_line}\n  {indent}{marks}\n'



def stdlib_text_width(text:str) -> int:
  '''
  The default `TextWidth` function, which uses the Unicode data of the Python standard library.
  Each character is measured by `stdlib_char_width`, with rules for the emoji sequences that most modern terminals render as one glyph:
  * A character joined to a wide character by a zero width joiner occupies no further columns.
  * Variation selector 16 requests emoji presentation, which widens a narrow character to two columns.
  * An emoji skin tone modifier occupies no columns.
  * A pair of regional indicator symbols forms a flag of two columns.
  Older terminals and those that do not segment text into grapheme clusters render some of these sequences as separate glyphs.
  '''
  width = 0
  base_width = 0 # The width of the most recent character that occupied any columns.
  is_joined = False # The preceding character is a zero width joiner.
  is_flag_open = False # The preceding character is an unpaired regional indicator.
  for char in text:
    if is_joined:
      is_joined = False
      if base_width == 2: continue # The joined character is part of the preceding glyph.
    if char == '\u200d': # ZERO WIDTH JOINER.
      is_joined = True
      continue
    if char == '\ufe0f': # VARIATION SELECTOR-16.
      if base_width == 1:
        width += 1
        base_width = 2
      continue
    if '\U0001f3fb' <= char <= '\U0001f3ff': continue # Emoji modifiers (skin tones).
    if '\U0001f1e6' <= char <= '\U0001f1ff': # Regional indicator symbols.
      if is_flag_open:
        is_flag_open = False
        continue
      is_flag_open = True
      width += 2
      base_width = 2
      continue
    is_flag_open = False
    char_width = stdlib_char_width(char)
    width += char_width
    if char_width: base_width = char_width
  return width


def stdlib_char_width(char:str) -> int:
  '''
  The number of terminal columns that a single character occupies, according to the Unicode data of the Python standard library.
  Combining marks and format characters occupy no columns; East Asian wide and fullwidth characters occupy two.
  '''
  if char < '\x7f': return 1
  if category(char) in ('Mn', 'Me', 'Cf'): return 0
  return 2 if east_asian_width(char) in ('W', 'F') else 1


def _marks(text:str, mark:str, text_width:TextWidth) -> str:
  'Return a string of `mark` characters that occupies the same terminal columns as `text`. Tabs are preserved.'
  return '\t'.join(mark * text_width(segment) for segment in text.split('\t'))



class LexerProtocol(Protocol):
  '''
  The interface that a lexer provides to a parser.
  Both lexer instances and lexer classes with class-level implementations can conform.
  '''

  @property
  def kinds(self) -> Container[str]:
    'The token kinds that the lexer can produce, excluding `end_of_text` and the kinds for invalid text.'

  def lex(self, source:Source, slc:slice|None=None, *, mode:str|None=None, drop:Container[str]=(), eot:bool=False
   ) -> Iterator[Token]:
    '''
    Lex `source`, yielding tokens.
    If `slc` is provided then only that range of the text is lexed; no token extends past its end.
    `mode` is the mode in which lexing starts; if it is None then the lexer uses its default mode.
    Tokens whose kinds are in `drop` are omitted.
    If `eot` is true then a final `end_of_text` token is yielded, positioned at the end of the range.
    '''
