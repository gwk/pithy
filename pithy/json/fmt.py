# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from io import BytesIO, Reader, Writer
from typing import Iterator
from warnings import warn


def fmt_json_bytes(bytes_or_file:bytes|Reader[bytes]) -> Iterator[bytes]:
  '''
  Format JSON bytes. The JSON input does not have to be well-formed.
  The output is the input, with alterations only to whitespace.
  This is useful for pretty-printing JSON that is malformed.
  The output style is lispy, with closing braces/brackets on the same line as the last item.
  '''
  file:Reader[bytes] = BytesIO(bytes_or_file) if isinstance(bytes_or_file, bytes) else bytes_or_file

  s_start, s_open, s_close, s_comma, s_colon, s_mid, s_str, s_str_esc = range(8)
  # States:
  # s_start: before any tokens have been seen.
  # s_open: an open token (`{` or `[`).
  # s_close: a close token (`}` or `]`).
  # s_comma: a comma token (`,`).
  # s_colon: a colon token (`:`).
  # s_mid: any other token.
  # s_str: inside a string.
  # s_str_esc: a backslash token inside of a string.

  indent = 0
  state = s_start
  is_next_inline = True
  while byte := file.read(1):
    prev_state = state

    if state == s_str_esc:
      state = s_str
    elif state == s_str:
      if byte == b'"':
        state = s_mid
      elif byte == b'\\':
        state = s_str_esc

    elif byte in b' \n\t\r':
      continue
    elif byte == b'"':
      state = s_str
    elif byte in b'{[':
      state = s_open
    elif byte in b'}]':
      state = s_close
    elif byte == b',':
      state = s_comma
    elif byte == b':':
      state = s_colon
    else:
      state = s_mid

    if (
     prev_state == s_colon or
     (prev_state == s_open and is_next_inline) or
     (prev_state not in (s_open, s_close) and state == s_close)):
      yield b' '
    elif prev_state == s_open and state != s_close:
      yield b'\n'
      yield b'  ' * indent
      is_next_inline = True

    if prev_state in (s_comma, s_close) and state not in (s_comma, s_close): # Done closing; emit newline/indent.
      yield b'\n'
      yield b'  ' * indent
      is_next_inline = True

    yield byte

    if state == s_open:
      indent += 1
    elif state == s_close:
      indent -= 1

    if state != s_open:
      is_next_inline = False

  # Final newline for non-empty output.
  if state != s_start:
    yield b'\n'

  if indent != 0:
    warn(f'Unbalanced JSON levels: {indent}')


def write_formatted_json_bytes(file:Writer[bytes], bytes_or_file:bytes|Reader[bytes]) -> None:
  for b in fmt_json_bytes(bytes_or_file):
    file.write(b)
