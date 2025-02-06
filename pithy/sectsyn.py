# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


'''
SectIndices (Section Syntax).

SS is a simple syntax using header lines to define nested sections.
It is similar to Markdown but concerned only with nested section structure, and defaults to using '$' as the header symbol.
The idea is to return the section text ranges so that different parsers can be called for each section.
In this way, a single file can contain multiple types of syntax, each with its own parser.

There is always a root section at level 0.
Any text preceding the first header is considered part of the root section.
The root section always has an empty title.

The syntax for a section is a line starting with some number of the specified header symbol character.
The number of header symbols indicates the nesting level of the section.
'''

from dataclasses import dataclass
from typing import Iterator, Literal, overload

from tolkien import _Text, Source, SyntaxError


@dataclass
class SectIndices:
  level:int
  idx:int
  parent_idx:int
  title:slice
  body:slice


@overload
def parse_sections(source:Source[_Text], *, symbol:str|bytes, numbered:bool, raises:Literal[False]) -> Iterator[SectIndices|SyntaxError]: ...

@overload
def parse_sections(source:Source[_Text], *, symbol:str|bytes, numbered:bool, raises:Literal[True]) -> Iterator[SectIndices]: ...


def parse_sections(source:Source, *, symbol:str|bytes, numbered:bool, raises=False) -> Iterator[SectIndices|SyntaxError]:
  '''
  Given a text source, yield SectIndices elements.
  `symbol` is the section header symbol, which may be a multi-character string or a bytes sequence.
  If `numbered` is True, the section symbol is followed by a number, which is the section depth.
  If `numbered` is False, the number of repeated `symbol` characters indicates the section depth.
  If `raises` is True, SyntaxError exceptions are raised for syntax errors.
  If `raises` is False, SyntaxError exceptions are yielded, interleaved with SectIndices elements.
  '''
  text = source.text

  if isinstance(text, (bytes, bytearray)) and isinstance(symbol, str):
    symbol = symbol.encode()

  text_type = type(text[0:0])
  if type(symbol) != text_type:
    raise ValueError(f'Symbol type {type(symbol)} does not match text type {text_type}.')

  source.update_newline_positions() # Calculate all line positions.

  parent_stack:list[tuple[int,int]] = [(-1, -1)] # (level, index). The stack of parent sections. There is always base element.

  # Pending section attributes.
  section_idx = 0 # Counter that determines the index of each section.
  level = 0
  title_pos = 0
  title_end = 0
  body_pos = 0
  newline_char = ('\n' if isinstance(text, str) else b'\n')

  def emit_section(body_end:int) -> SectIndices:
    nonlocal body_pos
    # Trim whitespace from the body.
    while body_end > body_pos and text[body_end-1:body_end].isspace():
      body_end -= 1
    while body_pos < body_end and text[body_pos:body_pos+1] == newline_char:
      body_pos += 1
    if body_end and text[body_end:body_end+1] == newline_char:
      body_end += 1 # Keep a single terminating newline at the end of the body.

    parent_level, parent_idx = parent_stack[-1]
    assert parent_level == level - 1, (parent_level, level)
    return SectIndices(level, section_idx, parent_idx, slice(title_pos, title_end), slice(body_pos, body_end))

  for line_slc in source.line_slices():
    if numbered:
      next_level, section_header_level_end = numbered_section_header_level(text, line_slc, symbol)
    else:
      next_level, section_header_level_end = repeated_section_header_level(text, line_slc, symbol)

    if not next_level: continue # Body text.

    section = emit_section(line_slc.start - 1) # Emit the previous section, closed by the current section title line.
    yield section
    section_idx += 1

    if next_level > section.level + 1:
      header_slc = slice(line_slc.start, section_header_level_end)
      err = SyntaxError(syntax=header_slc, msg=f'Header level {next_level} does not match parent level {section.level}.')
      if raises: raise err
      else: yield err

    # Adjust the parent stack to match the emitted/current section.
    target_level = min(section.level, next_level)
    while parent_stack[-1][0] >= target_level: parent_stack.pop()
    if next_level > target_level:
      parent_stack.append((section.level, section.idx))

    assert parent_stack and parent_stack[-1][0] == next_level - 1
    level = next_level
    title_pos = section_header_level_end
    title_end = line_slc.stop

    # Trim whitespace from the title.
    while title_end > title_pos and text[title_end-1:title_end].isspace():
      title_end -= 1
    while title_pos < title_end and text[title_pos:title_pos+1].isspace():
      title_pos += 1

    body_pos = line_slc.stop

  yield emit_section(len(text)) # Emit the final section.


def repeated_section_header_level(text:str|bytes|bytearray, line_slc:slice, symbol:str|bytes) -> tuple[int,int]:
  '''
  Count the number of leading section symbols in a line.
  '''
  sym_len = len(symbol)
  level = 0
  pos = line_slc.start
  for pos in range(line_slc.start, line_slc.stop, sym_len):
    if text.find(symbol, pos, pos+sym_len) == -1: break # type: ignore[arg-type]
    level += 1
  return (level, pos)


def numbered_section_header_level(text:str|bytes|bytearray, line_slc:slice, symbol:str|bytes) -> tuple[int,int]:
  '''
  Parse a section header line in the form 'symbol number title'.
  '''
  sym_len = len(symbol)
  start_pos = line_slc.start
  pos = start_pos
  if text.find(symbol, pos, pos+sym_len) == -1: return (0, start_pos) # type: ignore[arg-type]
  pos += sym_len

  # Parse the number.
  num_pos = pos
  while pos < line_slc.stop and text[pos:pos+1].isdigit():
    pos += 1

  if num_pos < pos:
    level = int(text[num_pos:pos])
    return (level, pos)
  else:
    return (0, pos)
