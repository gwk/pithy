# Derived from the tomli-w library: https://github.com/hukkin/tomli-w.
# All changes are dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.
#
# Original license:
#
# MIT License
#
# Copyright (c) 2021 Taneli Hukkinen
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


'''
Tomul: a simple TOML library.
'''

from collections.abc import Iterator, Mapping, Sequence
from datetime import date, datetime, time
from decimal import Decimal
from tomllib import load as load_toml, loads as parse_toml
from types import MappingProxyType
from typing import Any, IO


__version__ = '0.0.0'

_convenience_exports = (load_toml, parse_toml)


ascii_ctrl_chars = frozenset(chr(i) for i in range(32)) | frozenset(chr(127))
escaped_chars_inline = (ascii_ctrl_chars - frozenset('\t')) | frozenset('"\\')
escaped_chars_multiline = escaped_chars_inline - {'\n'}

bare_key_chars = frozenset('abcdefghijklmnopqrstuvwxyz' 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' '0123456789' '-_')
max_line_len = 128

char_escapes = MappingProxyType({ # TODO: use frozendict in Python3.15.
  '\b': '\\b',
  '\n': '\\n',
  '\f': '\\f',
  '\r': '\\r',
  '"': '\\"',
  '\\': '\\\\'})


def render_toml(obj:Mapping[str,Any], /, *, indent:int=2) -> str:
  'Render `obj` (a dictionary or other Mapping) as TOML syntax.'
  if indent < 0: raise ValueError(f'`indent` must be non-negative; received: {indent!r}.')
  return ''.join(render_table(obj, indent=indent, name=''))


def write_toml(file:IO[bytes], obj:Mapping[str,Any], *, indent:int=2) -> None:
  '''
  Write `obj` (a dictionary or other Mapping) as TOML syntax to `file` (a binary file open for writing).
  Note: file must be binary so that we do not accidentally write invalid TOML in an encoding other than UTF-8,
  or with incorrect newline conversion.
  '''
  if indent < 0: raise ValueError(f'`indent` must be non-negative; received: {indent!r}.')
  for chunk in render_table(obj, indent=indent, name=''):
    file.write(chunk.encode())


def render_table(table:Mapping[str,Any], *, indent:int, name:str, is_inside_aot:bool=False) -> Iterator[str]:
  yielded = False
  literals = [] # Literals must precede tables or else they would be parsed as inside a child table namespace.
  tables:list[tuple[str, Any, bool]] = [] # Items are: (key, value, is_item_inside_aot).
  for k, v in table.items():
    if isinstance(v, Mapping):
      tables.append((k, v, False))
    elif is_aot(v) and not all(is_suitable_inline_table(t, indent=indent) for t in v):
      tables.extend((k, t, True) for t in v)
    else:
      literals.append((k, v))

  if is_inside_aot or name and (literals or not tables):
    yielded = True
    yield f'[[{name}]]\n' if is_inside_aot else f'[{name}]\n'

  if literals:
    yielded = True
    for k, v in literals:
      yield f'{render_key_part(k)} = {render_literal(v, indent=indent)}\n'

  for k, v, is_item_inside_aot in tables:
    if yielded:
      yield '\n'
    else:
      yielded = True
    key_part = render_key_part(k)
    display_name = f'{name}.{key_part}' if name else key_part
    yield from render_table(v, indent=indent, name=display_name, is_inside_aot=is_item_inside_aot)


def render_literal(obj:object, *, indent:int, nest_level:int=0) -> str:
  if isinstance(obj, str):
    return render_str(obj, allow_multiline=True)
  if isinstance(obj, bool):
    return 'true' if obj else 'false'
  if isinstance(obj, (int, float, date, datetime)):
    return str(obj)
  if isinstance(obj, time):
    if obj.tzinfo: raise ValueError('TOML does not support offset times')
    return str(obj)
  if isinstance(obj, Sequence):
    return render_inline_array(obj, indent, nest_level)
  if isinstance(obj, Mapping):
    return render_inline_table(obj, indent)

  if hasattr(obj, 'number_class'):
    from decimal import Decimal
    if isinstance(obj, Decimal):
      return render_decimal(obj)
  raise TypeError(f'Object of type {type(obj).__qualname__!r} is not TOML serializable')


def render_str(s:str, allow_multiline:bool) -> str:
  is_multiline = allow_multiline and ('\n' in s)
  if is_multiline:
    delim = '"""'
    parts = [delim + '\n']
    escaped_chars = escaped_chars_multiline
  else:
    delim = '"'
    parts = [delim]
    escaped_chars = escaped_chars_inline

  for c in s:
    if c in escaped_chars:
      if c in char_escapes:
        parts.append(char_escapes[c])
      else:
        parts.append(f'\\u{ord(c):04x}' if ord(c) <= 0xFFFF else f'\\U{ord(c):08x}')
    else:
      parts.append(c)
  parts.append(delim)
  return ''.join(parts)


def render_decimal(obj:Decimal) -> str:
  if obj.is_nan(): return 'nan'
  if obj.is_infinite(): return '-inf' if obj.is_signed() else 'inf'
  dec_str = str(obj).lower()
  return dec_str if ('.' in dec_str or 'e' in dec_str) else dec_str + '.0'


def render_inline_array(obj:Sequence, indent:int, nest_level:int) -> str:
  if not obj: return '[]'
  item_indent = ' ' * indent * (1 + nest_level)
  closing_bracket_indent = ' ' * indent * nest_level
  middle = ',\n'.join(item_indent + render_literal(item, indent=indent, nest_level=nest_level + 1) for item in obj)
  return '[\n' + middle + f',\n{closing_bracket_indent}]'


def render_inline_table(obj: Mapping, indent:int) -> str:
  if not obj: return '{}'
  middle = ', '.join(f'{render_key_part(k)} = {render_literal(v, indent=indent)}' for k, v in obj.items())
  return '{ ' + middle + ' }'


def render_key_part(part:str) -> str:
  try:
    only_bare_key_chars = bare_key_chars.issuperset(part)
  except TypeError:
    raise TypeError(f'Invalid mapping key {part!r} of type {type(part).__qualname__!r}; a string is required.') from None

  if part and only_bare_key_chars:
    return part
  return render_str(part, allow_multiline=False)


def is_aot(obj:Any) -> bool:
  'Decides if an object behaves as an array of tables (i.e. a nonempty list of dicts).'
  return bool(isinstance(obj, Sequence) and obj and all(isinstance(v, Mapping) for v in obj))


def is_suitable_inline_table(obj:Mapping, indent:int) -> bool:
  'Use heuristics to decide if the inline-style representation is a good choice for a given table.'
  rendered_inline = f'{' '*indent}{render_inline_table(obj, indent)},'
  return len(rendered_inline) <= max_line_len and '\n' not in rendered_inline
