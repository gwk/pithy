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
def parse_sections(source:Source[_Text], *, symbol:str|bytes|None=None, raises:Literal[False]) -> Iterator[SectIndices|SyntaxError]: ...

@overload
def parse_sections(source:Source[_Text], *, symbol:str|bytes|None=None, raises:Literal[True]) -> Iterator[SectIndices]: ...


def parse_sections(source:Source, *, symbol:str|bytes|None=None, raises=False) -> Iterator[SectIndices|SyntaxError]:
  '''
  Given a text source, yield SectIndices elements.
  If raises is True, SyntaxError exceptions are raised for syntax errors.
  If raises is False, SyntaxError exceptions are yielded, interleaved with SectIndices elements.
  '''
  text = source.text
  if symbol is None:
    symbol = '$' if isinstance(source.text, str) else b'$'
  if len(symbol) != 1: raise ValueError(f'Header symbol must be a single character; received: {symbol!r}.')
  assert type(symbol) == type(text)

  raw_symbol:str|int = symbol if isinstance(symbol, str) else symbol[0]

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
    while body_end > body_pos and text[body_end-1].isspace():
      body_end -= 1
    while body_pos < body_end and text[body_pos] == newline_char:
      body_pos += 1
    if body_end and text[body_end] == newline_char:
      body_end += 1 # Keep a single terminating newline at the end of the body.

    parent_level, parent_idx = parent_stack[-1]
    assert parent_level == level - 1, (parent_level, level)
    return SectIndices(level, section_idx, parent_idx, slice(title_pos, title_end), slice(body_pos, body_end))

  for line_slc in source.line_slices():
    next_level, section_header_level_end = section_header_level(text, line_slc=line_slc, symbol=raw_symbol)

    if not next_level: continue # Body text.

    section = emit_section(line_slc.start - 1) # Emit the previous section, closed by the current title.
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
    while title_end > title_pos and text[title_end-1].isspace():
      title_end -= 1
    while title_pos < title_end and text[title_pos].isspace():
      title_pos += 1

    body_pos = line_slc.stop

  yield emit_section(len(text)) # Emit the final section.


def section_header_level(text:str|bytes|bytearray, line_slc:slice, symbol:str|int) -> tuple[int,int]:
  '''
  Count the number of leading hash characters in a line, plus the numerical value following the symbol.
  '''
  count = 0
  pos = line_slc.start
  for pos in range(line_slc.start, line_slc.stop):
    c = text[pos]
    if c == symbol:
      count += 1
    else:
      break
  return count, pos
