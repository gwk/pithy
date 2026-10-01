# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


'''
Sectsyn (Section Syntax).

Sectsyn is a simple syntax using header lines to define nested sections.
It is similar to Markdown section syntax but can use an arbitrary symbol.
The idea is to return the section text ranges so that different parsers can be called for each section.
In this way, a single file can contain multiple types of syntax, each with its own parser.
Sections are split by line shape alone, before any tokenization, so no section body can alter the section structure.

There is always a root section at level 0.
Any text preceding the first header is considered part of the root section.
The root section always has an empty marker and title.

# Headers

A header is a line that begins at column 0 with a marker, followed by whitespace or the end of the line.
* In repeated mode the marker is one or more repetitions of the symbol; the count is the level.
* In numbered mode the marker is the symbol followed by decimal digits; the number is the level.

The remainder of the header line is the title, with surrounding whitespace trimmed.
If `title_sep` is provided then the title is split at the first separator into a name and inline content.

A header may be at most one level deeper than its parent. A deeper header is a syntax error.
In non-raising mode such a section is still yielded with its declared level, as a child of the nearest shallower section.
In numbered mode, level 0 is reserved for the root; a level 0 header is a syntax error and the line is left as body text.

# Collisions

Any other line is body text, including lines that begin with the symbol but do not have the header shape.
For example with the symbol `#`, the lines `#!shebang` and `#comment` are body text.
A body line cannot have the header shape at column 0.
An indented line is never a header, so indentation is the universal escape.
It is up to each section's syntax to tolerate the leading whitespace.
In numbered mode, choose a symbol that is not followed by digits in body text.

# Bodies

Each section provides two body ranges:
* `raw_body` is the complete lines between the header line and the next header, for whitespace-sensitive syntaxes.
* `body` omits leading blank lines and trailing whitespace, but keeps the indentation of the first line and a final newline.
'''

from dataclasses import dataclass
from typing import Iterator, Literal, overload

from tolkien import _Text, Source, SyntaxError


_context_keywords_ = ['header', 'heading', 'markdown', 'multiple syntaxes', 'nested sections', 'section']
_context_status_ = 'experimental'


type _AnyText = str|bytes|bytearray


@dataclass
class SectIndices:
  level:int
  idx:int
  parent_idx:int
  marker:slice # The header symbols and level number; empty for the root.
  title:slice # The complete trimmed title.
  name:slice # The title up to `title_sep`; the same as `title` if there is no separator.
  inline:slice # The title content following `title_sep`; empty if there is no separator.
  body:slice # The trimmed body.
  raw_body:slice # The untrimmed body lines.

  @property
  def slc(self) -> slice: # HasSlc conformance.
    return slice(self.marker.start, self.raw_body.stop)


@overload
def parse_sections(source:Source[_Text], *, symbol:str|bytes, numbered:bool, title_sep:str|bytes|None=None,
 raises:Literal[False]=False) -> Iterator[SectIndices|SyntaxError]: ...

@overload
def parse_sections(source:Source[_Text], *, symbol:str|bytes, numbered:bool, title_sep:str|bytes|None=None,
 raises:Literal[True]) -> Iterator[SectIndices]: ...


def parse_sections(source:Source, *, symbol:str|bytes, numbered:bool, title_sep:str|bytes|None=None, raises:bool=False
 ) -> Iterator[SectIndices|SyntaxError]:
  '''
  Given a text source, yield SectIndices elements.
  `symbol` is the section header symbol, which may be a multi-character string or a bytes sequence.
  If `numbered` is True, the section symbol is followed by a number, which is the section depth.
  If `numbered` is False, the number of repeated `symbol` characters indicates the section depth.
  If `title_sep` is provided, each title is split at the first occurrence into `name` and `inline` ranges.
  If `raises` is True, SyntaxError exceptions are raised for syntax errors.
  If `raises` is False, SyntaxError exceptions are yielded, interleaved with SectIndices elements.
  '''
  text = source.text
  symbol = _coerce_to_text(text, symbol, 'symbol')
  if title_sep is not None: title_sep = _coerce_to_text(text, title_sep, 'title_sep')

  open_sections:list[tuple[int,int]] = [(0, 0)] # (level, idx). The stack of open sections; the root is never popped.

  # Pending section attributes.
  level = 0
  idx = 0
  parent_idx = -1
  marker = title = name = inline = slice(0, 0)
  body_pos = 0

  def pending_section(body_end:int) -> SectIndices:
    return SectIndices(level, idx, parent_idx, marker, title, name, inline,
      body=_trim_body(text, body_pos, body_end), raw_body=slice(body_pos, body_end))

  for line_slc in source.line_slices():
    header = header_level(text, line_slc, symbol, numbered=numbered)
    if header is None: continue # Body text.
    next_level, marker_end = header
    next_marker = slice(line_slc.start, marker_end)

    if next_level == 0:
      err = SyntaxError(syntax=next_marker, msg='Header level 0 is reserved for the root section.')
      if raises: raise err
      yield err
      continue # The line remains body text.

    yield pending_section(line_slc.start) # The previous section is closed by the current header line.

    while open_sections[-1][0] >= next_level: open_sections.pop()
    parent_level, parent_idx = open_sections[-1]
    if next_level > parent_level + 1:
      msg = f'Header level {next_level} is more than one deeper than parent level {parent_level}.'
      err = SyntaxError(syntax=next_marker, msg=msg)
      if raises: raise err
      yield err

    level = next_level
    idx += 1
    open_sections.append((level, idx))
    marker = next_marker
    title = _trim(text, marker_end, line_slc.stop)
    name, inline = _split_title(text, title, title_sep)
    body_pos = line_slc.stop

  yield pending_section(len(text))


def header_level(text:_AnyText, line_slc:slice, symbol:str|bytes, *, numbered:bool) -> tuple[int,int]|None:
  '''
  Return the header level and marker end position for a line, or None if the line is not a header.
  In numbered mode the level can be zero, which the caller should treat as an error.
  '''
  sym_len = len(symbol)
  pos = line_slc.start
  end = line_slc.stop
  level = 0
  if numbered:
    if not text.startswith(symbol, pos, end): return None # type: ignore[arg-type]
    pos += sym_len
    num_pos = pos
    while pos < end and text[pos:pos+1] in _digits: pos += 1
    if num_pos == pos: return None
    level = int(text[num_pos:pos])
  else:
    while text.startswith(symbol, pos, end): # type: ignore[arg-type]
      pos += sym_len
      level += 1
    if not level: return None
  if pos < end and not text[pos:pos+1].isspace(): return None
  return (level, pos)


_digits = frozenset('0123456789') | frozenset(bytes([d]) for d in b'0123456789')
#^ Explicit ASCII digits; `str.isdigit` accepts characters like superscripts that `int` rejects.


def _coerce_to_text(text:_AnyText, pattern:str|bytes, label:str) -> str|bytes:
  'Convert `pattern` to match the type of `text` and validate it.'
  if isinstance(text, str):
    if not isinstance(pattern, str): raise ValueError(f'{label} type {type(pattern)} does not match text type {type(text)}.')
  elif isinstance(pattern, str):
    pattern = pattern.encode()
  if not pattern: raise ValueError(f'{label} is empty.')
  if any(pattern[i:i+1].isspace() for i in range(len(pattern))): raise ValueError(f'{label} contains whitespace: {pattern!r}.')
  return pattern


def _trim(text:_AnyText, pos:int, end:int) -> slice:
  'Trim whitespace from both ends of the range. An all-whitespace range trims to an empty slice at `pos`.'
  while end > pos and text[end-1:end].isspace(): end -= 1
  while pos < end and text[pos:pos+1].isspace(): pos += 1
  return slice(pos, end)


def _split_title(text:_AnyText, title:slice, title_sep:str|bytes|None) -> tuple[slice,slice]:
  'Split the title into name and inline content ranges.'
  sep_pos = -1 if title_sep is None else text.find(title_sep, title.start, title.stop) # type: ignore[arg-type]
  if sep_pos == -1: return (title, slice(title.stop, title.stop))
  assert title_sep is not None
  return (_trim(text, title.start, sep_pos), _trim(text, sep_pos + len(title_sep), title.stop))


def _trim_body(text:_AnyText, pos:int, end:int) -> slice:
  'Omit leading blank lines and trailing whitespace, keeping the first line indentation and a single final newline.'
  newline = '\n' if isinstance(text, str) else b'\n'
  content_end = end
  while content_end > pos and text[content_end-1:content_end].isspace(): content_end -= 1
  if content_end == pos: return slice(pos, pos)
  for i in range(pos, content_end): # Advance `pos` past each blank line.
    char = text[i:i+1]
    if not char.isspace(): break
    if char == newline: pos = i + 1
  if text[content_end:content_end+1] == newline: content_end += 1
  return slice(pos, content_end)
