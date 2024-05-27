# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


'''
Hash Section Syntax.

HSS is a simple syntax using markdown style text headers to define nested sections.
The idea is to return the section text ranges so that different parsers can be called for each section.
In this way, a single file can contain multiple types of syntax, each with its own parser.

There is always a root section at level 0.
Any text preceding the first header is considered part of the root section.
The root section always has an empty title.
'''

from dataclasses import dataclass
from typing import Iterator

from tolkien import Source, SyntaxError


@dataclass
class HssSection:
  level:int
  idx:int
  parent_idx:int
  title:slice
  body:slice


def parse_sections(source:Source) -> Iterator[HssSection]:
  '''
  Given a text source, yield HssSection elements.
  '''
  text = source.text
  source.update_newline_positions(len(text)) # Calculate all line positions.

  parent_stack:list[tuple[int,int]] = [(-1, -1)] # (level, index). The stack of parent sections. There is always base element.

  # Pending section attributes.
  section_idx = 0 # Counter that determines the index of each section.
  level = 0
  title_pos = 0
  title_end = 0
  body_pos = 0
  newline_char = ('\n' if isinstance(text, str) else b'\n')

  def emit_section(body_end:int) -> HssSection:
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
    return HssSection(level, section_idx, parent_idx, slice(title_pos, title_end), slice(body_pos, body_end))

  for slc in source.line_slices():
    line = text[slc]
    next_level = count_hash_chars(line)
    if not next_level: continue # Body text.

    section = emit_section(slc.start - 1) # Emit the previous section, closed by the current title.
    yield section
    section_idx += 1

    if next_level > section.level + 1:
      hashes_slc = slice(slc.start, slc.start + next_level)
      raise SyntaxError(syntax=hashes_slc, msg=f'Header level {next_level} does not match parent level {section.level}.')

    # Adjust the parent stack to match the emitted/current section.
    target_level = min(section.level, next_level)
    while parent_stack[-1][0] >= target_level: parent_stack.pop()
    if next_level > target_level:
      parent_stack.append((section.level, section.idx))

    assert parent_stack and parent_stack[-1][0] == next_level - 1
    level = next_level
    title_pos = slc.start + next_level
    title_end = slc.stop

    # Trim whitespace from the title.
    while title_end > title_pos and text[title_end-1].isspace():
      title_end -= 1
    while title_pos < title_end and text[title_pos].isspace():
      title_pos += 1

    body_pos = slc.stop

  yield emit_section(len(text)) # Emit the final section.


def count_hash_chars(line:str) -> int:
  '''
  Count the number of leading hash characters in a line.
  '''
  count = 0
  for c in line:
    if c == '#':
      count += 1
    else:
      break
  return count
