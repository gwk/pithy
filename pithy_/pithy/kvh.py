# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
KVH: a text key/value header for binary file formats.

A KVH record is a text header, followed by an application-defined binary body.
This documentation is the specification of the format. It is written in terms of bytes, independent of any programming language.

```
KVH<NUL><SP>format-name<SP>v1<LF>
BODY_SIZE<SP>1024<LF>
key<SP>value<LF>
key<SP>first line of a multiline value<LF>
<TAB>second line<LF>
<NUL> ... NUL padding to a 64 byte boundary, or to the declared header size ...
body
... NUL padding to a 64 byte boundary ...
```

# Notation

* NUL is the byte 0x00, TAB is 0x09, LF is 0x0A, CR is 0x0D and SP is 0x20.
* A printable byte is any byte from 0x21 to 0x7E. This excludes SP.
* A digit is any byte from 0x30 to 0x39. A decimal integer is either the single digit `0`, or a digit other than `0`
  followed by zero or more digits. It has no sign and no leading zeros.
* The maximum integer is 9007199254740991, which is 2^53 - 1.
  Every implementation language can represent integers up to this value exactly, including JavaScript.
* All offsets and sizes are in bytes. Offsets are relative to the first byte of the header.
* The alignment is 64.

# Magic line

The header begins with the five bytes 0x4B 0x56 0x48 0x00 0x20, which are `KVH`, NUL and SP.
The format identifier follows, and is terminated by the first LF.
The NUL makes tools such as git and grep classify the file as binary regardless of the header length.

* The identifier is a format name, then SP, then the byte `v` (0x76), then the format version.
* The name is one or more words separated by single SP bytes. A word is one or more printable bytes.
* The version is a decimal integer no greater than the maximum integer.
  It is the last word of the identifier, so `a v1 v2` has the name `a v1` and the version 2.
* The identifier is at most 255 bytes long.
* If the identifier ends with CR, a reader should report that the file was damaged by newline conversion.

The application defines the name and the meaning of the version.
An application reader should reject a version that it does not support.

# Lines

The rest of the header is a sequence of lines. Each line is terminated by LF.
No other byte or character terminates a line; in particular CR, U+0085, U+2028 and U+2029 do not.
The first byte of each line determines its kind:

* NUL: the header text ends. See the section on termination. This is not a line, and no LF is required after it.
* TAB: a continuation line.
* Anything else: an item line. This includes an empty line, which is an item line with an empty key and is therefore invalid.

# Items

An item is a key and a value. An item line begins a new item.

* The key is the bytes of the line up to the first SP, or the whole line if it contains no SP.
* If the line contains SP then the first line of the value is the bytes after the first SP, taken verbatim.
  These bytes may include further SP bytes. There must be at least one byte after the first SP.
* If the line contains no SP then the first line of the value is empty.

A continuation line adds a line to the value of the current item. The added line is the bytes after the TAB, taken verbatim.
A continuation line that precedes the first item is invalid.
The value is its lines joined by LF. A value never ends with an implicit LF:
the value `a` is written as `key<SP>a<LF>`, and the value `a<LF>` is written as `key<SP>a<LF><TAB><LF>`.
Every value therefore has exactly one encoding.

# Keys

* A key is an optional `?` (0x3F), followed by a printable byte other than `?`, followed by zero or more printable bytes.
* A key is at most 255 bytes long, including the `?`.
* Keys are compared as exact byte sequences. `k`, `K` and `?k` are three distinct keys.
* Each key may appear at most once in a header.
* The order of items has no meaning to KVH. Readers and writers should preserve it.

# Values

* The lines of a value must be valid UTF-8. Overlong encodings, surrogates (U+D800 to U+DFFF) and code points above U+10FFFF
  are invalid.
* A value must not contain the control characters U+0000 to U+0008, U+000B, U+000C, U+000E to U+001F, or U+007F to U+009F.
* TAB and CR may appear anywhere in a value. LF appears only as the separator between the lines of a value.
* No other character is treated specially. Values are not normalized, and U+FEFF is an ordinary character.

# Reserved and advisory keys

A key is reserved for KVH if it contains at least one byte from `A` to `Z` (0x41 to 0x5A)
and no byte from `a` to `z` (0x61 to 0x7A). Examples: `SIZE`, `X_1`, `?SUM`.
All other keys belong to the application. Examples: `name`, `Size`, `?note`, `1`.

A key that begins with `?` is advisory: a reader that does not recognize the key can ignore it and still read the file.
A reader must reject a header that contains a key that it does not recognize and that does not begin with `?`.
This lets a format add advisory keys without making new files unreadable by old readers.

* A KVH reader applies this rule to reserved keys. `HEADER_SIZE` and `BODY_SIZE` are the reserved keys defined so far.
* Applications can use the same convention for their own keys, and are responsible for applying it.
* A writer that modifies a file should drop the advisory keys that it does not recognize, because they may no longer hold.
* Application code cannot write reserved keys as ordinary items.

# Termination and header padding

The header text ends at the first line that begins with NUL. That byte is the terminator.
The header size is the offset at which the body begins. It is always a multiple of the alignment.
Every byte from the terminator up to the header size must be NUL. These bytes are the header padding.

The reserved key `HEADER_SIZE` is optional and may appear at any position among the items.
Its value is the header size, as a decimal integer on a single line, no greater than the maximum integer.

* Without `HEADER_SIZE` the header size is the smallest multiple of the alignment that is greater than the offset of the
  terminator. The padding is then less than one alignment block.
* With `HEADER_SIZE` the header size is the declared value.
  It must be a multiple of the alignment and greater than the offset of the terminator. It need not be the smallest such value.

A reader must verify that the padding bytes are present and are all NUL.
A header that ends before its padding is complete is truncated and invalid.

`HEADER_SIZE` lets a writer reserve space, so that it can later rewrite the header in place without moving the body.
For example, a writer that streams a body of unknown size can reserve space, write the body and its padding,
and then rewrite the header with `BODY_SIZE` added and the same `HEADER_SIZE`.

# Body

The reserved key `BODY_SIZE` is optional and may appear at any position among the items.
Its value is the exact size of the body, as a decimal integer on a single line, no greater than the maximum integer.

* Without `BODY_SIZE` the body extends to the end of the file, so nothing can follow it.
* With `BODY_SIZE` the body must be followed by the fewest NUL bytes that make its padded size a multiple of the
  alignment; possibly none. This padding is required even at the end of the file, and is not counted in `BODY_SIZE`.

A reader of a body with a declared size must verify that the body and its padding are complete,
and that the padding bytes are all NUL.

A record is a header, a body and the body padding.
The size of a record with a declared body size is therefore a multiple of the alignment.
Such records can be concatenated, e.g. with `cat`, and every header and body in the sequence remains aligned.
What may follow a record is defined by the application.

# Limits

A reader must bound its work. The readers in this module require a maximum header size, which includes the padding.
This bounds the bytes read, and therefore the number of items and the size of every key and value.
A reader must check a declared `HEADER_SIZE` against its limit before reading the padding.

# Design rationale

Advisory keys. A format changes over time, and old readers will meet files written by newer writers.
An old reader cannot know what an unrecognized key means, so it needs a rule that it can apply without that knowledge.
* Rejection is the default because an unrecognized key might change how the body is located or interpreted.
  A reader that ignored such a key would misread the file without noticing.
* The `?` mark is the writer's statement that ignoring the key is safe. A checksum is an example.
  New advisory keys therefore cost nothing: old readers continue to read new files.
* The rule is part of the first version of the format because it is the old reader that applies it.
  It cannot be introduced after readers are deployed.
* A change that old readers must not ignore is made with an unmarked key or a new format version.
  Together with the mark this covers both kinds of change, which is why the format version is a single integer.
* PNG distinguishes critical and ancillary chunks in the same way.

Other decisions:
* The header is text so that it can be inspected with ordinary tools and parsed without a library.
  Tab-prefixed continuation lines keep multiline values readable, and keep the start of every item at the start of a line.
* Every key, value and integer has exactly one encoding. This leaves implementations less to disagree on.
* KVH itself has no version number. Reserved keys extend it, and an incompatible revision would use a different magic.
* The alignment of 64 suits SIMD operations and common cache line sizes, at a cost of less than 64 bytes of padding.
* `HEADER_SIZE` reserves space in general, where a placeholder value for each late-bound key would not.
  This keeps the single encoding of every value, and leaves a valid file at every stage of writing.

# This module

`parse_kvh_header` and `read_kvh_header` read a header from a buffer or a file, and `render_kvh_header` writes one.
`slice_kvh_body` and `read_kvh_body` then obtain the body from the buffer or file,
and verify the declared body size and the body padding. Code that reads a body by other means must do the same.
Writing the body and its padding is left to the application; `kvh_padding_size` gives the padding size.
`render_kvh_header` can reserve header space for items that are known only after the body is written.
The header readers return unrecognized advisory reserved items separately from the application items.
The writer rejects reserved keys in the items that it is given, and emits the defined ones from dedicated arguments.
'''

import re
from collections.abc import Buffer, Iterable, Mapping
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO


_context_keywords_ = [
  'binary format', 'container', 'file header', 'key value', 'kvh', 'magic number', 'metadata', 'payload alignment',
  'versioning']
_context_status_ = 'experimental'


kvh_magic = b'KVH\0 '
kvh_alignment = 64
kvh_max_format_id_len = 255
kvh_max_key_len = 255
kvh_max_int = (1<<53) - 1 # The largest integer that every target language represents exactly.

kvh_header_size_key = 'HEADER_SIZE'
kvh_body_size_key = 'BODY_SIZE'


class KvhError(ValueError):
  'The base class of KVH errors.'


class KvhHeaderError(KvhError):
  'Raised when a KVH header is malformed, exceeds the specified limits, or cannot be rendered.'


class KvhBodyError(KvhError):
  'Raised when a KVH body or its padding does not match its header, or exceeds the specified limits.'


@dataclass(frozen=True, slots=True)
class KvhHeader:
  '''
  A parsed KVH header.
  `items` contains the application items.
  `unrecognized_reserved_items` contains the advisory reserved items that this version of the module does not recognize.
  `body_size` is the value of `BODY_SIZE`, or None if the body extends to the end of the file.
  `header_size` is the body offset relative to the start of the header, whether or not `HEADER_SIZE` declares it.
  `padded_body_size` is the size of the body and its padding, or None if the body size is not declared.
  `record_size` is the size of the header, body and padding, or None if the body size is not declared.
  It is the offset of whatever follows the record, relative to the start of the header.
  '''
  format_name:str
  format_version:int
  items:dict[str,str]
  unrecognized_reserved_items:dict[str,str]
  body_size:int|None
  header_size:int

  @property
  def padded_body_size(self) -> int|None:
    return None if self.body_size is None else self.body_size + kvh_padding_size(self.body_size)

  @property
  def record_size(self) -> int|None:
    padded_body_size = self.padded_body_size
    return None if padded_body_size is None else self.header_size + padded_body_size


def parse_kvh_header(data:Buffer, *, max_size:int) -> KvhHeader:
  '''
  Parse a KVH header from the start of `data`. The body begins at `data[header.header_size:]`.
  See `read_kvh_header` for the limit.
  '''
  limit = max(max_size, len(kvh_magic)) # Bound the copy while always including the magic.
  return read_kvh_header(BytesIO(memoryview(data).cast('B')[:limit]), max_size=max_size)


def read_kvh_header(file:BinaryIO, *, max_size:int) -> KvhHeader:
  '''
  Read a KVH header from the current position of the buffered binary `file`, leaving it positioned at the body.
  `max_size` limits the header size in bytes, including the padding.
  '''
  magic = file.read(len(kvh_magic))
  if magic != kvh_magic: raise KvhHeaderError(f'not a KVH header; expected magic {kvh_magic!r}; received {magic!r}.')
  reader = _Reader(file, max_size=max_size, pos=len(magic))

  format_bytes = reader.read_line()
  if format_bytes.endswith(b'\r'): raise reader.error('magic line ends with CRLF; the file was damaged by newline conversion.')
  format_id = reader.decode(format_bytes)
  m = _format_id_re.fullmatch(format_id)
  format_version = _parse_int(m['version']) if m else None
  if not m or format_version is None or len(format_id) > kvh_max_format_id_len:
    raise reader.error(f'invalid format identifier: {format_id!r}.')

  items:dict[str,str] = {}
  key:str|None = None
  value_lines:list[str] = []
  while True:
    lead = reader.read(1)
    if lead == b'\0': break
    line = reader.read_line(lead)
    if lead == b'\t':
      if key is None: raise reader.error('continuation line precedes the first item.')
      if key in _int_reserved_keys: raise reader.error(f'invalid {key}: value has multiple lines.')
      value_lines.append(reader.decode_value(line[1:]))
      continue
    if key is not None: items[key] = '\n'.join(value_lines)
    key_bytes, sep, value_bytes = line.partition(b' ')
    key = reader.decode(key_bytes)
    if msg := _key_error(key): raise reader.error(msg)
    if key.isupper() and not key.startswith('?') and key not in _recognized_reserved_keys:
      raise reader.error(f'unrecognized reserved key: {key!r}; the file may require a newer KVH reader.')
    if key in items: raise reader.error(f'duplicate key: {key!r}.')
    if sep and not value_bytes: raise reader.error(f'key is followed by a space but no value: {key!r}.')
    value_lines = [reader.decode_value(value_bytes)]
    if key in _int_reserved_keys and _parse_int(value_lines[0]) is None:
      raise reader.error(f'invalid {key}: {value_lines[0]!r}.')
  if key is not None: items[key] = '\n'.join(value_lines)

  def pop_int(key:str) -> int|None:
    text = items.pop(key, None)
    return None if text is None else _parse_int(text)

  body_size = pop_int(kvh_body_size_key)
  header_size = pop_int(kvh_header_size_key)
  if header_size is None:
    header_size = reader.pos + kvh_padding_size(reader.pos)
  elif header_size % kvh_alignment or header_size < reader.pos:
    raise KvhHeaderError(f'invalid {kvh_header_size_key}: {header_size};'
      f' expected a multiple of {kvh_alignment} that is at least {reader.pos}.')
  if any(reader.read(header_size - reader.pos)): raise KvhHeaderError('header padding contains non-NUL bytes.')

  return KvhHeader(format_name=m['name'], format_version=format_version,
    items={k: v for k, v in items.items() if not k.isupper()},
    unrecognized_reserved_items={k: v for k, v in items.items() if k.isupper()},
    body_size=body_size,
    header_size=header_size)


def render_kvh_header(format_name:str, format_version:int, items:Mapping[str,str], *,
 body_size:int|None=None, header_size:int|None=None, reserve_size:int=0) -> bytes:
  '''
  Render a complete KVH header, including the terminator and padding. The body should immediately follow.

  If `body_size` is provided then the header declares it as `BODY_SIZE`,
  and the body must be followed by `kvh_padding_size(body_size)` NUL bytes.

  If `header_size` is provided then the header declares it as `HEADER_SIZE` and is padded to that size.

  If `reserve_size` is positive then the header declares a `HEADER_SIZE` that leaves at least that many bytes free
  for items to be added or enlarged later. Use `kvh_item_size` to calculate the size of an item.
  To fill in the items once the body is written, render the header again with the final items and arguments,
  and `header_size` equal to the length of the original header. Then write the result over the original.
  '''
  format_id = f'{format_name} v{format_version:d}'
  if not _format_name_re.fullmatch(format_name): raise KvhHeaderError(f'invalid format name: {format_name!r}.')
  if not 0 <= format_version <= kvh_max_int: raise KvhHeaderError(f'invalid format version: {format_version!r}.')
  if len(format_id) > kvh_max_format_id_len:
    raise KvhHeaderError(f'format identifier exceeds {kvh_max_format_id_len} characters: {format_id!r}.')
  if body_size is not None and not 0 <= body_size <= kvh_max_int:
    raise KvhHeaderError(f'invalid body size: {body_size!r}.')
  if header_size is not None and (not 0 < header_size <= kvh_max_int or header_size % kvh_alignment):
    raise KvhHeaderError(f'invalid header size: {header_size!r}; expected a positive multiple of {kvh_alignment}.')
  if reserve_size < 0: raise KvhHeaderError(f'invalid reserve size: {reserve_size!r}.')
  if reserve_size and header_size is not None: raise KvhHeaderError('reserve_size cannot be combined with header_size.')

  item_lines:list[str] = []
  for key, value in items.items():
    if key.isupper(): raise KvhHeaderError(f'all caps keys are reserved for KVH: {key!r}.')
    item_lines.extend(_render_item_lines(key, value))
  body_size_lines = [] if body_size is None else [f'{kvh_body_size_key} {body_size:d}']

  def text_size(*header_size_lines:str) -> int:
    'The size of the magic, the text and the terminator.'
    return len(kvh_magic) + _lines_size((format_id, *header_size_lines, *body_size_lines, *item_lines)) + 1

  if reserve_size: # Find the header size that also holds its own `HEADER_SIZE` item.
    base_size = text_size('') + reserve_size + len(kvh_header_size_key) + 1 # The empty line adds the item's terminator.
    reserved_size = 0
    for digits_len in range(1, len(str(kvh_max_int)) + 1):
      reserved_size = base_size + digits_len + kvh_padding_size(base_size + digits_len)
      if len(str(reserved_size)) <= digits_len: break
    if reserved_size > kvh_max_int: raise KvhHeaderError(f'invalid reserve size: {reserve_size!r}.')
    header_size = reserved_size

  header_size_lines = [] if header_size is None else [f'{kvh_header_size_key} {header_size:d}']
  size = text_size(*header_size_lines)
  if header_size is None: header_size = size + kvh_padding_size(size)
  elif size > header_size: raise KvhHeaderError(f'header requires {size} bytes, which exceeds the header size: {header_size}.')
  text = ''.join(line + '\n' for line in (format_id, *header_size_lines, *body_size_lines, *item_lines))
  return b''.join((kvh_magic, text.encode(), bytes(header_size - size + 1)))


def kvh_item_size(key:str, value:str) -> int:
  '''
  The size in bytes of the item as it is written in a header, including its continuation lines and line terminators.
  This is the amount of header space to reserve in order to add the item later.
  Reserved keys are accepted, e.g. `kvh_item_size(kvh_body_size_key, str(kvh_max_int))`.
  '''
  return _lines_size(_render_item_lines(key, value))


def slice_kvh_body(data:Buffer, header:KvhHeader) -> memoryview:
  '''
  Return a view of the body in `data`, without copying it. `header` must have been parsed from the start of `data`.
  If the header declares the body size then verify that the body and its padding are complete.
  Whatever follows the record begins at `data[header.record_size:]`.
  Otherwise the body is the remainder of `data`.
  '''
  view = memoryview(data).cast('B')
  start = header.header_size
  body_size = header.body_size
  if body_size is None: return view[start:]
  end = start + body_size
  if len(view) < end: raise _body_truncation_error(body_size, max(0, len(view) - start))
  padding_size = kvh_padding_size(body_size)
  _check_body_padding(view[end:end+padding_size], padding_size)
  return view[start:end]


def read_kvh_body(file:BinaryIO, header:KvhHeader, *, max_size:int) -> bytes:
  '''
  Read the body from the buffered binary `file`, which must be positioned where `read_kvh_header` left it.
  If the header declares the body size then verify that the body and its padding are complete,
  leaving the file positioned after the record.
  Otherwise read to the end of the file.
  `max_size` limits the body size in bytes, not including the padding.
  '''
  body_size = header.body_size
  if body_size is None:
    body = file.read(max_size + 1)
    if len(body) > max_size: raise KvhBodyError(f'body exceeds max_size: {max_size}.')
    return body
  if body_size > max_size: raise KvhBodyError(f'body size {body_size} exceeds max_size: {max_size}.')
  body = file.read(body_size)
  if len(body) != body_size: raise _body_truncation_error(body_size, len(body))
  padding_size = kvh_padding_size(body_size)
  _check_body_padding(file.read(padding_size), padding_size)
  return body


def kvh_padding_size(size:int) -> int:
  'The number of NUL bytes required to pad `size` to a multiple of `kvh_alignment`.'
  return -size % kvh_alignment


class _Reader:
  'Reads header bytes from a file while tracking the header offset and enforcing the size limit.'

  def __init__(self, file:BinaryIO, *, max_size:int, pos:int) -> None:
    self.file = file
    self.max_size = max_size
    self.pos = pos
    self.line_num = 0 # The number of the line most recently read.


  def read(self, size:int) -> bytes:
    'Read exactly `size` bytes.'
    if self.pos + size > self.max_size: raise self.size_error()
    data = self.file.read(size)
    self.pos += len(data)
    if len(data) != size: raise self.truncation_error()
    return data


  def read_line(self, lead:bytes=b'') -> bytes:
    'Read the remainder of the current line. Return the line including the already read `lead`, excluding the newline.'
    self.line_num += 1
    if lead == b'\n': return b''
    limit = self.max_size - self.pos
    if limit <= 0: raise self.size_error()
    line = self.file.readline(limit)
    self.pos += len(line)
    if not line.endswith(b'\n'): raise self.size_error() if len(line) == limit else self.truncation_error()
    return lead + line[:-1]


  def decode(self, text_bytes:bytes) -> str:
    try: return text_bytes.decode()
    except UnicodeDecodeError as e: raise self.error(f'invalid UTF-8: {e}.') from e


  def decode_value(self, text_bytes:bytes) -> str:
    text = self.decode(text_bytes)
    if m := _invalid_value_char_re.search(text): raise self.error(f'value contains invalid character: {m[0]!r}.')
    return text


  def error(self, msg:str) -> KvhHeaderError: return KvhHeaderError(f'line {self.line_num}: {msg}')


  def size_error(self) -> KvhHeaderError: return KvhHeaderError(f'header exceeds max_size: {self.max_size}.')


  def truncation_error(self) -> KvhHeaderError: return KvhHeaderError(f'header is truncated at offset {self.pos}.')


def _check_body_padding(padding:bytes|memoryview, padding_size:int) -> None:
  if len(padding) != padding_size:
    raise KvhBodyError(f'body padding is truncated: expected {padding_size} bytes; received {len(padding)}.')
  if any(padding): raise KvhBodyError('body padding contains non-NUL bytes.')


def _body_truncation_error(body_size:int, actual_size:int) -> KvhBodyError:
  return KvhBodyError(f'body is truncated: expected {body_size} bytes; received {actual_size}.')


def _render_item_lines(key:str, value:str) -> list[str]:
  'Validate the key and value, and return the lines of the item without their terminators.'
  if msg := _key_error(key): raise KvhHeaderError(msg)
  first, *rest = value.split('\n')
  for line in (first, *rest):
    if m := _invalid_value_char_re.search(line):
      raise KvhHeaderError(f'value for key {key!r} contains invalid character: {m[0]!r}.')
  return [f'{key} {first}' if first else key, *('\t' + line for line in rest)]


def _lines_size(lines:Iterable[str]) -> int:
  'The encoded size of the lines, including their terminators.'
  try: return sum(len(line.encode()) + 1 for line in lines)
  except UnicodeEncodeError as e: raise KvhHeaderError(f'header text cannot be encoded as UTF-8: {e}.') from e


def _key_error(key:str) -> str|None:
  if len(key) > kvh_max_key_len: return f'key exceeds {kvh_max_key_len} bytes: {key[:32]!r}...'
  if not _key_re.fullmatch(key): return f'invalid key: {key!r}.'
  return None


def _parse_int(text:str) -> int|None:
  'Parse a decimal integer as defined by the format, or return None if it is invalid.'
  if not _int_re.fullmatch(text): return None
  val = int(text)
  return val if val <= kvh_max_int else None


_int_reserved_keys = frozenset({kvh_header_size_key, kvh_body_size_key})
_recognized_reserved_keys = _int_reserved_keys

_format_name_pattern = r'[!-~]+(?: [!-~]+)*'
_format_name_re = re.compile(_format_name_pattern)
_format_id_re = re.compile(rf'(?P<name>{_format_name_pattern}) v(?P<version>[0-9]+)')
_key_re = re.compile(r'\??[!->@-~][!-~]*') # An optional advisory mark, followed by a name that does not begin with the mark.
_int_re = re.compile(r'0|[1-9][0-9]{0,15}') # The digit limit bounds the conversion cost; the value is checked separately.
_invalid_value_char_re = re.compile(r'[\x00-\x08\x0a-\x0c\x0e-\x1f\x7f-\x9f]') # Applies to single lines; allows tab and CR.
