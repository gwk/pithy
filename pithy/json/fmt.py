# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from io import BytesIO, Reader, Writer
from typing import Generator


# Iterating over chunks of bytes ints instead of individual BytesIO bytes objects yields ~2x speedup.
_chunk_size = 16 * 1024
_b_newline = ord('\n')
_b_space = ord(' ')
_b_dquote = ord('"')
_b_backslash = ord('\\')
_b_comma = ord(',')
_b_colon = ord(':')
_b_ws = frozenset(b' \n\t\r')
_b_open = frozenset(b'{[')
_b_close = frozenset(b'}]')
_byte_table = [bytes([i]) for i in range(256)]  # Avoid per-byte allocation when yielding; ~15% speedup.
_b_indent = b'  '


def fmt_json_bytes(bytes_or_file:bytes|Reader[bytes]) -> Generator[bytes,None,int]:
  '''
  Format JSON bytes. The JSON input does not have to be well-formed.
  This is useful for pretty-printing JSON, including input that is malformed.
  The output identical to the input, with the following changes:
  * space, '\n', '\r', '\t' are replaced with formatted whitespace (spaces and newlines only).
  The output style is lispy, with closing braces/brackets on the same line as the last item.
  Returns the indent level; use `GenRes` to obtain the indent level and output together.
  '''
  file:Reader[bytes] = BytesIO(bytes_or_file) if isinstance(bytes_or_file, bytes) else bytes_or_file

  s_start, s_open_inline, s_open_break, s_close, s_comma, s_colon, s_mid, s_str, s_str_esc = range(9)
  # States:
  # s_start: before any tokens have been seen.
  # s_open_inline: an open token (`{` or `[`) whose first child will be on the same line.
  # s_open_break: an open token (`{` or `[`) whose first child will be on the next line.
  # s_close: a close token (`}` or `]`).
  # s_comma: a comma token (`,`).
  # s_colon: a colon token (`:`).
  # s_mid: any other token.
  # s_str: inside a string.
  # s_str_esc: a backslash token inside of a string.

  indent = 0
  state = s_start
  while chunk := file.read(_chunk_size):
    output = bytearray() # ~15% speedup over yielding individual bytes when building the output.
    for b in chunk:
      prev_state = state

      if state == s_str_esc:
        state = s_str
      elif state == s_str:
        if b == _b_dquote:
          state = s_mid
        elif b == _b_backslash:
          state = s_str_esc

      elif b in _b_ws:
        continue
      elif b == _b_dquote:
        state = s_str
      elif b in _b_open:
        # Open brackets preceded by a newline or the document start inline their first child.
        # s_open_inline propagates: consecutive inline opens all inline their first child.
        # s_open_break precedes a newline, so the following open is inlined.
        # s_comma and s_close both trigger a newline before the next token, so the following item can is inlined.
        # All other predecessors (s_colon, s_mid, s_str) are mid-line, requiring s_open_break.
        if prev_state in (s_start, s_open_inline, s_open_break, s_comma, s_close):
          state = s_open_inline
        else:
          state = s_open_break
      elif b in _b_close:
        state = s_close
      elif b == _b_comma:
        state = s_comma
      elif b == _b_colon:
        state = s_colon
      else:
        state = s_mid

      if (
       prev_state == s_colon or
       prev_state == s_open_inline or
       (prev_state not in (s_open_inline, s_open_break, s_close) and state == s_close)):
        output.append(_b_space)
      elif prev_state in (s_open_break, s_comma, s_close) and state not in (s_comma, s_close):
        output.append(_b_newline)
        output.extend(_b_indent * indent)

      output.append(b)

      if state in (s_open_inline, s_open_break):
        indent += 1
      elif state == s_close:
        indent -= 1

    yield bytes(output)

  # Final newline for non-empty output.
  if state != s_start:
    yield b'\n'

  return indent



def write_formatted_json_bytes(file:Writer[bytes], bytes_or_file:bytes|Reader[bytes]) -> None:
  for b in fmt_json_bytes(bytes_or_file):
    file.write(b)
