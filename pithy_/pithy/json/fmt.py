# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
JSON formatting.

# Development

See `perf/pithy/json/fmt/perf-test-json-fmt.py` for a simple perf test.
'''

from io import BytesIO, Reader, Writer
from typing import Generator


# Iterating over bytes chunks and their ints instead of individual BytesIO bytes objects yields ~2x speedup.
_chunk_size = 16 * 1024
_b_newline = ord('\n')
_b_space = ord(' ')
_b_dquote = ord('"')
_b_backslash = ord('\\')
_b_comma = ord(',')
_b_colon = ord(':')
_b_slash = ord('/')
_b_star = ord('*')
_b_ws = frozenset(b' \n\t\r')
_b_open = frozenset(b'{[')
_b_close = frozenset(b'}]')
_b_specials = frozenset(b' \n\t\r{}[],:"/')
#^ Bytes that terminate an s_mid run. Must exactly mirror the structural dispatch chain below.
_byte_table = [bytes([i]) for i in range(256)]  # Avoid per-byte allocation when yielding; ~15% speedup.
_b_indent = b'  '


def fmt_json_bytes(bytes_or_file:bytes|Reader[bytes], *, fix:bool, allow_trailing_commas:bool=False,
 allow_comments:bool=False) -> Generator[bytes,None,int]:
  '''
  Format JSON bytes. The JSON input does not have to be syntactically well-formed.
  This is useful for pretty-printing JSON, including input that is malformed.

  If `fix` is `True` then the output is modified to try to make it well-formed JSON:
  * Missing commas are added where appropriate.
  * Multiple consecutive commas are reduced to a single comma.
  * A final comma before a closing brace/bracket is removed unless `allow_trailing_commas` is `True`.

  `allow_trailing_commas` has no effect if `fix` is `False`.

  JavaScript-style comments (`//` line and `/* */` block) are recognized.
  When `fix` is `True`, comments are stripped unless `allow_comments` is `True`.
  When `fix` is `False`, comments are always preserved.

  The output identical to the input, with the following changes:
  * JSON whitespace (only space, '\n', '\r', '\t') is altered; the output whitespace is spaces and newlines only.
  * Trailing commas are omitted unless `allow_trailing_commas` is `True`.
  * Comments are stripped when `fix` is `True` and `allow_comments` is `False`.
  The output style is lispy, with closing braces/brackets on the same line as the last item.
  Returns the indent level; use `GenRes` to obtain the indent level and output together.
  '''
  file:Reader[bytes] = BytesIO(bytes_or_file) if isinstance(bytes_or_file, bytes) else bytes_or_file

  s_start, s_open_inline, s_open_break, s_close, s_comma, s_colon, s_mid, s_str, s_str_esc = range(9)
  # States are specified as local ints. This is faster than looking up global vars.
  # It is also much faster than using a global Enum object.
  # Enums would allow us to use the `match` statement, but that also appears to be slower in practice.
  # s_start: before any tokens have been seen.
  # s_open_inline: an open token (`{` or `[`) whose first child will be on the same line.
  # s_open_break: an open token (`{` or `[`) whose first child will be on the next line.
  # s_close: a close token (`}` or `]`).
  # s_comma: a comma token (`,`).
  # s_colon: a colon token (`:`).
  # s_mid: any other token.
  # s_str: inside a string.
  # s_str_esc: a backslash token inside of a string.

  # The machine is structured as super-states guarded at the top of the inner loop:
  # comments, strings, and finally the structural dispatch, which handles one token-initial byte per pass.
  # String content and comment bodies are scanned with `bytes.find` and copied as slices at C speed;
  # whitespace runs and s_mid runs (which have no single-byte find target) step through tight per-byte loops.
  # All of these skip the classification and separator-emission logic entirely.
  # Each super-state is resumable: when the chunk runs out mid-token, the persisted state re-enters the same block.
  #
  # Emission invariant: every token's FINAL byte stays deferred in `prev_byte`, so that fix-mode can drop a
  # trailing comma and the comment/EOF paths can flush or re-queue it. Token INTERIORS (string content,
  # s_mid run interiors, comment bodies) are emitted eagerly, because no whitespace/comment/drop logic can
  # intervene mid-token.

  inline_states = frozenset((s_start, s_open_inline, s_open_break, s_comma, s_close))

  c_none, c_pending, c_line, c_block, c_block_star = range(5)
  comment = c_none
  strip_comments = fix and not allow_comments
  unterminated_block_buffer = bytearray()
  #^ In strip mode, captures the current block comment so it can be re-emitted on EOF if unterminated.

  prev2_state = s_start
  prev_state = s_start
  prev_byte = -1
  prev_had_ws = False
  post_line_comment_nl = False
  #^ True when a preserved `//` comment just emitted its terminating newline; suppresses the next transition's leading newline.
  indent = 0

  while chunk := file.read(_chunk_size):
    n = len(chunk)
    output = bytearray() # ~15% speedup over yielding individual bytes when building the output.
    i = 0
    while i < n:

      # Comment super-state.
      if comment is not c_none:
        if comment is c_pending:
          byte = chunk[i]
          if byte == _b_slash:
            comment = c_line
            if not strip_comments:
              if prev_byte != -1:
                output.append(prev_byte)
                output.append(_b_space)
                prev_byte = -1
              output.extend(b'//')
            prev_had_ws = True
            i += 1
            continue
          if byte == _b_star:
            comment = c_block
            if not strip_comments:
              if prev_byte != -1:
                output.append(prev_byte)
                output.append(_b_space)
                prev_byte = -1
              output.extend(b'/*')
            else:
              unterminated_block_buffer.extend(b'/*')
            prev_had_ws = True
            i += 1
            continue
          # Not a comment start. Emit the orphan `/` as a literal s_mid byte so it is preserved.
          # Run the prev_state -> s_mid transition for the slash, then queue it as prev_byte.
          comment = c_none
          if prev_byte != -1:
            output.append(prev_byte)
          if prev_state is s_open_inline:
            output.append(_b_space)
          elif prev_state is s_open_break:
            if not post_line_comment_nl:
              output.append(_b_newline)
            output.extend(_b_indent * indent)
          elif prev_state is s_close:
            if fix:
              output.append(_b_comma)
            if not post_line_comment_nl:
              output.append(_b_newline)
            output.extend(_b_indent * indent)
          elif prev_state is s_comma:
            if not post_line_comment_nl:
              output.append(_b_newline)
            output.extend(_b_indent * indent)
          elif prev_state is s_colon:
            output.append(_b_space)
          elif (prev_state is s_mid or prev_state is s_str) and prev_had_ws:
            if fix:
              output.append(_b_comma)
            if not post_line_comment_nl:
              output.append(_b_newline)
            output.extend(_b_indent * indent)
          prev2_state = prev_state
          prev_state = s_mid
          prev_byte = _b_slash
          prev_had_ws = False
          post_line_comment_nl = False
          continue # Do not consume: the loop top re-dispatches chunk[i], which always makes progress.
        elif comment is c_line:
          j = chunk.find(_b_newline, i)
          if j < 0: # The comment runs to the end of the chunk; c_line persists into the next chunk.
            if not strip_comments:
              output += chunk[i:]
            i = n
          else:
            comment = c_none
            if not strip_comments:
              output += chunk[i:j+1] # The body plus the terminating newline.
              post_line_comment_nl = True
            i = j + 1
          continue
        elif comment is c_block:
          j = chunk.find(_b_star, i)
          e = n if j < 0 else j + 1 # Copy through the star, if found; otherwise c_block persists into the next chunk.
          if strip_comments:
            unterminated_block_buffer += chunk[i:e]
          else:
            output += chunk[i:e]
          if j >= 0:
            comment = c_block_star
          i = e
          continue
        else: # c_block_star: a single byte; handles `*/`, `**`, and the chunk-boundary split.
          byte = chunk[i]
          i += 1
          if byte == _b_slash:
            comment = c_none
            if not strip_comments:
              output.append(byte)
            else:
              unterminated_block_buffer.clear() # Comment closed; discard the safety buffer.
            prev_had_ws = True
            continue
          comment = c_block_star if byte == _b_star else c_block
          if not strip_comments:
            output.append(byte)
          else:
            unterminated_block_buffer.append(byte)
          prev_had_ws = True
          continue

      # String super-state.
      if prev_state is s_str or prev_state is s_str_esc:
        if prev_byte != -1: # Flush the deferred opening quote.
          output.append(prev_byte)
          prev_byte = -1
        if prev_state is s_str_esc: # A backslash ended the previous chunk; emit the escaped byte raw.
          output.append(chunk[i])
          i += 1
          prev_state = s_str
        while i < n:
          q = chunk.find(_b_dquote, i) # Candidate closing quote.
          e = chunk.find(_b_backslash, i, q if q >= 0 else n) # An escape before the candidate quote?
          if e >= 0:
            output += chunk[i:e+1] # Content plus the backslash, emitted eagerly.
            i = e + 1
            if i < n:
              output.append(chunk[i]) # The escaped byte cannot close the string; emit it raw.
              i += 1
              continue
            prev_state = s_str_esc # The chunk ended immediately after the backslash.
            break
          if q < 0: # The rest of the chunk is string content; s_str persists into the next chunk.
            output += chunk[i:]
            i = n
            break
          output += chunk[i:q] # Content, emitted eagerly.
          i = q + 1
          prev_byte = _b_dquote # The closing quote is deferred, like every token-final byte.
          prev2_state = s_str
          prev_state = s_mid
          break
        continue

      # Structural dispatch: one token-initial byte per pass.
      byte = chunk[i]
      i += 1

      if byte in _b_ws:
        prev_had_ws = True
        while i < n and chunk[i] in _b_ws:
          i += 1
        continue
      if byte == _b_slash:
        comment = c_pending
        continue
      if byte == _b_dquote:
        state = s_str
      elif byte in _b_open:
        # Open brackets on a new line are followed by an inlined first child.
        # s_open_inline propagates: consecutive inline opens are allowed.
        # s_open_break precedes a newline, so a following open is inlined.
        # s_comma and s_close both trigger a newline before the next token, so the following item is inlined.
        # All other predecessors (s_colon, s_mid, s_str) are mid-line, requiring s_open_break.
        if prev_state in inline_states:
          state = s_open_inline
        else:
          state = s_open_break
      elif byte in _b_close:
        state = s_close
      elif byte == _b_comma:
        state = s_comma
      elif byte == _b_colon:
        state = s_colon
      else:
        state = s_mid

      if fix and prev_state is s_comma:
        if state is s_comma: # Multiple consecutive commas; omit all but the first, leaving prev_state alone.
          continue # The comma byte was already consumed above.
        if state is s_close and not allow_trailing_commas: # Omit the comma; state will transition to s_close.
          prev_state = prev2_state
          prev_byte = -1

      if prev_byte != -1:
        output.append(prev_byte)

      if prev_state is s_open_inline:
        if state != s_close:
          output.append(_b_space)
      elif prev_state is s_open_break:
        if state != s_close:
          if not post_line_comment_nl:
            output.append(_b_newline)
          output.extend(_b_indent * indent)
      elif prev_state is s_close:
        if state is not s_comma and state is not s_close:
          if fix:
            output.append(_b_comma)
          if not post_line_comment_nl:
            output.append(_b_newline)
          output.extend(_b_indent * indent)
      elif prev_state is s_comma:
        if state is s_comma: # When not in fix mode, do not add newline/indent to consecutive commas.
          assert not fix # In `fix` mode, multiple consecutive commas should have been handled above.
        elif state is not s_close:
          if not post_line_comment_nl:
            output.append(_b_newline)
          output.extend(_b_indent * indent)
      elif prev_state is s_colon:
        output.append(_b_space)
      elif prev_state is s_mid or prev_state is s_str:
        if state is s_close:
          output.append(_b_space)
        elif (state is s_mid or state is s_str) and prev_had_ws: # Two tokens with intervening whitespace; missing comma.
          if fix:
            output.append(_b_comma)
          if not post_line_comment_nl:
            output.append(_b_newline)
          output.extend(_b_indent * indent)

      prev_byte = byte
      prev2_state = prev_state
      prev_state = state
      prev_had_ws = False
      post_line_comment_nl = False

      if state is s_open_inline or state is s_open_break:
        indent += 1
      elif state is s_close:
        indent -= 1

      if state is s_mid: # Tight run loop for constants and other non-delimiter bytes; maintains last-byte deferral.
        # prev2_state is not updated per byte: it is only read when prev_state is s_comma,
        # and every comma's dispatch tail rewrites it before that read.
        while i < n:
          b = chunk[i]
          if b in _b_specials:
            break
          output.append(prev_byte)
          prev_byte = b
          i += 1

    yield bytes(output)

  if comment is c_pending: # Reached EOF just after a bare `/`; emit the orphan slash rather than dropping it.
    if prev_byte != -1:
      yield _byte_table[prev_byte]
      if prev_had_ws:
        yield b' '
      prev_byte = -1
    yield b'/'
    prev_state = s_mid # Ensure the final newline is emitted even if the slash was the only token.
    post_line_comment_nl = False

  if prev_byte != -1: # If the final byte is a comma then the output is invalid so we emit it regardless.
    yield _byte_table[prev_byte]
  if unterminated_block_buffer: # Reached EOF inside an unterminated block comment; preserve it rather than swallowing input.
    yield bytes(unterminated_block_buffer)
  if prev_state != s_start and not post_line_comment_nl:
    # Final newline for non-empty output, unless a preserved line comment already ended with one.
    yield b'\n'

  return indent



def write_formatted_json_bytes(file:Writer[bytes], bytes_or_file:bytes|Reader[bytes], fix:bool,\
 allow_trailing_commas:bool=False, allow_comments:bool=False) -> None:

  for b in fmt_json_bytes(bytes_or_file, fix=fix, allow_trailing_commas=allow_trailing_commas, allow_comments=allow_comments):
    file.write(b)
