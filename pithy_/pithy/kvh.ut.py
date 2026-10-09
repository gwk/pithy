# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from hashlib import sha256
from io import BytesIO

from pithy.kvh import (kvh_alignment, kvh_body_size_key, kvh_item_size, kvh_max_int, kvh_padding_size, KvhBodyError, KvhHeader,
  KvhHeaderError, parse_kvh_header, read_kvh_body, read_kvh_header, render_kvh_header, slice_kvh_body)
from utest import utest, utest_exc, utest_run, utest_val


def parse(data:bytes, max_size:int=1024) -> KvhHeader:
  return parse_kvh_header(data, max_size=max_size)


def padded(text:bytes) -> bytes:
  'Append the terminator and padding to the header text.'
  size = len(text) + 1
  return text + b'\0' * (1 + -size % kvh_alignment)


def format_id(id_bytes:bytes) -> tuple[str,int]:
  header = parse(padded(b'KVH\0 ' + id_bytes + b'\n'))
  return (header.format_name, header.format_version)


def item_text(key:str, value:str) -> bytes:
  'An independent rendering of the item.'
  first, *rest = value.split('\n')
  return ''.join(line + '\n' for line in (f'{key} {first}' if first else key, *(f'\t{line}' for line in rest))).encode()


json_value = '{\n  "a": 1,\n\t"b": [2, 3]\n}'

sample_items = {
  'name': 'example',
  'empty': '',
  'meta': json_value,
  'crlf': 'one\r\ntwo',
  'edges': '\n leading and trailing lines \n',
  'unicode': 'café',
}


@utest_run
def test_render() -> None:
  utest(padded(b'KVH\0 fmt v1\n'), render_kvh_header, 'fmt', 1, {})
  utest(padded(b'KVH\0 my fmt v20\n'), render_kvh_header, 'my fmt', 20, {})
  utest(padded(b'KVH\0 fmt v1\nBODY_SIZE 1\n'), render_kvh_header, 'fmt', True, {}, body_size=True) # Bools render as integers.
  utest(padded(b'KVH\0 fmt v0\nk v\ne\nm a\n\t\n\t b\n'), render_kvh_header, 'fmt', 0, {'k': 'v', 'e': '', 'm': 'a\n\n b'})
  # The header size is always a multiple of the alignment and always includes the terminator.
  for value_len in range(kvh_alignment * 2):
    data = render_kvh_header('fmt', 1, {'k': 'v' * value_len})
    utest_val(0, len(data) % kvh_alignment)
    utest_val(b'\n\0', data.rstrip(b'\0')[-1:] + data[-1:])


@utest_run
def test_render_errors() -> None:
  for format_name in ('', ' fmt', 'fmt ', 'my  fmt', 'fmt\n', 'fmt\r', 'café', 'x' * 253):
    utest_exc(KvhHeaderError, render_kvh_header, format_name, 1, {})
  utest(('x' * 252, 1), lambda: format_id(render_kvh_header('x' * 252, 1, {})[5:260]))
  utest_exc(KvhHeaderError('invalid format version: -1.'), render_kvh_header, 'fmt', -1, {})
  for key in ('', 'a b', 'a\tb', '\tk', 'k\n', 'k\0', 'café', '?', '??k'):
    utest_exc(KvhHeaderError(f'invalid key: {key!r}.'), render_kvh_header, 'fmt', 1, {key: 'v'})
  for key in ('k' * 256, '?' + 'k' * 255):
    utest_exc(KvhHeaderError(f'key exceeds 255 bytes: {key[:32]!r}...'), render_kvh_header, 'fmt', 1, {key: 'v'})
    utest_exc(KvhHeaderError(f'line 2: key exceeds 255 bytes: {key[:32]!r}...'),
      parse, padded(f'KVH\0 fmt v1\n{key} v\n'.encode()))
  for key in ('k' * 255, '?' + 'k' * 254):
    utest({key: 'v'}, lambda: parse(render_kvh_header('fmt', 1, {key: 'v'})).items)
  for key in ('K', 'KEY', 'A_1', 'X-Y', '?K', '?A_1'):
    utest_exc(KvhHeaderError(f'all caps keys are reserved for KVH: {key!r}.'), render_kvh_header, 'fmt', 1, {key: 'v'})
  for key in ('Key', 'kEY', '1', '_', 'a_B', '?k', '?Key', '?1', 'k?', 'K?k'):
    utest({key: 'v'}, lambda: parse(render_kvh_header('fmt', 1, {key: 'v'})).items)
  for value in ('\0', '\x1e', '\x0b', '\x0c', '\x7f', '\x85', '\ud800'):
    utest_exc(KvhHeaderError, render_kvh_header, 'fmt', 1, {'k': f'a\n{value}'})


@utest_run
def test_round_trip() -> None:
  data = render_kvh_header('my fmt', 12, sample_items)
  exp = KvhHeader(format_name='my fmt', format_version=12, items=sample_items, unrecognized_reserved_items={},
    body_size=None, header_size=len(data))
  utest(exp, parse, data)
  utest_val(list(sample_items), list(parse(data).items), 'item order')
  # The body does not affect parsing, even when it begins with NUL bytes.
  body = b'\0\0payload\n'
  utest_val(body, (data + body)[parse(data + body).header_size:])
  utest(exp, parse, data + body)
  utest(exp, parse, bytearray(data + body))
  utest(exp, parse, memoryview(data + body))


@utest_run
def test_read() -> None:
  data = render_kvh_header('fmt', 1, sample_items)
  body = b'\0payload'
  prefix = b'prefix'
  file = BytesIO(prefix + data + body)
  file.seek(len(prefix))
  header = read_kvh_header(file, max_size=1024)
  utest_val(len(data), header.header_size)
  utest_val(body, file.read())


@utest_run
def test_format_id() -> None:
  utest(('fmt', 0), lambda: format_id(b'fmt v0'))
  utest(('a b', 12), lambda: format_id(b'a b v12'))
  utest(('fmt v1', 2), lambda: format_id(b'fmt v1 v2'))
  utest(('v1', 2), lambda: format_id(b'v1 v2'))
  max_int = (1<<53) - 1
  utest(('fmt', max_int), lambda: format_id(f'fmt v{max_int}'.encode()))
  utest(padded(f'KVH\0 fmt v{max_int}\n'.encode()), render_kvh_header, 'fmt', max_int, {})
  utest_exc(KvhHeaderError(f'invalid format version: {max_int+1}.'), render_kvh_header, 'fmt', max_int+1, {})
  for id_bytes in (b'', b'fmt', b'v1', b'fmt 1', b'fmt v', b'fmt v01', b'fmt v1.0', b'fmt v-1', b'fmt V1', b'fmt v1 ',
   b' fmt v1', b'fmt  v1', b'fmt\tv1', b'x' * 253 + b' v1', f'fmt v{max_int+1}'.encode(), b'fmt v' + b'1' * 100):
    utest_exc(KvhHeaderError(f'line 1: invalid format identifier: {id_bytes.decode()!r}.'), format_id, id_bytes)
  utest_exc(KvhHeaderError('line 1: magic line ends with CRLF; the file was damaged by newline conversion.'),
    parse, padded(b'KVH\0 fmt v1\r\nk v\r\n'))


@utest_run
def test_advisory_keys() -> None:
  data = padded(b'KVH\0 fmt v1\n?SUM abc\na 1\n?b 2\n?X_1 m\n\tn\nc\n')
  header = parse(data)
  utest_val({'a': '1', '?b': '2', 'c': ''}, header.items)
  utest_val({'?SUM': 'abc', '?X_1': 'm\nn'}, header.unrecognized_reserved_items)
  # Reserved keys without the advisory mark are rejected because none are defined.
  utest_exc(KvhHeaderError("line 3: unrecognized reserved key: 'SIZE'; the file may require a newer KVH reader."),
    parse, padded(b'KVH\0 fmt v1\nk v\nSIZE 1\n'))
  utest_exc(KvhHeaderError("line 3: duplicate key: '?SUM'."), parse, padded(b'KVH\0 fmt v1\n?SUM 1\n?SUM 2\n'))
  utest({'k': '1', '?k': '2'}, lambda: parse(padded(b'KVH\0 fmt v1\nk 1\n?k 2\n')).items)


@utest_run
def test_body_size() -> None:
  utest(padded(b'KVH\0 fmt v1\nBODY_SIZE 0\nk v\n'), render_kvh_header, 'fmt', 1, {'k': 'v'}, body_size=0)
  max_size = (1<<53) - 1
  for body_size in (None, 0, 1, 7, 1234567890, max_size):
    header = parse(render_kvh_header('fmt', 1, {'k': 'v'}, body_size=body_size))
    utest_val(body_size, header.body_size)
    utest_val({'k': 'v'}, header.items)
    utest_val({}, header.unrecognized_reserved_items)
  utest_exc(KvhHeaderError('invalid body size: -1.'), render_kvh_header, 'fmt', 1, {}, body_size=-1)
  utest_exc(KvhHeaderError(f'invalid body size: {max_size+1}.'), render_kvh_header, 'fmt', 1, {}, body_size=max_size+1)
  utest_exc(KvhHeaderError("all caps keys are reserved for KVH: 'BODY_SIZE'."),
    render_kvh_header, 'fmt', 1, {'BODY_SIZE': '1'})
  # The key can appear at any position.
  utest(12, lambda: parse(padded(b'KVH\0 fmt v1\nk v\nBODY_SIZE 12\n')).body_size)
  for text in (b'', b' ', b'01', b'-1', b'+1', b'1.0', b'0x10', b'1 ', b'1k', str(max_size+1).encode(), b'1' * 5000):
    sep = b' ' if text else b''
    utest_exc(KvhHeaderError(f'line 2: invalid BODY_SIZE: {text.decode()!r}.'),
      parse, padded(b'KVH\0 fmt v1\nBODY_SIZE' + sep + text + b'\n'), max_size=8192)
  utest_exc(KvhHeaderError('line 3: invalid BODY_SIZE: value has multiple lines.'),
    parse, padded(b'KVH\0 fmt v1\nBODY_SIZE 1\n\t2\n'))
  utest_exc(KvhHeaderError("line 3: duplicate key: 'BODY_SIZE'."),
    parse, padded(b'KVH\0 fmt v1\nBODY_SIZE 1\nBODY_SIZE 1\n'))
  utest({'?BODY_SIZE': '1'}, lambda: parse(padded(b'KVH\0 fmt v1\n?BODY_SIZE 1\n')).unrecognized_reserved_items)


@utest_run
def test_padding() -> None:
  utest_val([0, 63, 1, 0, 63], [kvh_padding_size(size) for size in (0, 1, 63, 64, 65)])
  for body_size, exp in ((None, None), (0, 0), (1, 64), (64, 64), (65, 128)):
    utest(exp, lambda: parse(render_kvh_header('fmt', 1, {}, body_size=body_size)).padded_body_size)


@utest_run
def test_concatenation() -> None:
  bodies = [b'first payload', b'', b'\0\0third\n', b'x' * 64]
  records = [render_kvh_header('fmt', 1, {'idx': str(idx)}, body_size=len(p)) + p + bytes(kvh_padding_size(len(p)))
    for idx, p in enumerate(bodies)]
  data = b''.join(records)
  file = BytesIO(data)
  offset = 0
  for idx, (record, body) in enumerate(zip(records, bodies)):
    utest_val(0, file.tell() % kvh_alignment, 'header offset')
    header = read_kvh_header(file, max_size=1024)
    utest_val({'idx': str(idx)}, header.items)
    utest_val(0, file.tell() % kvh_alignment, 'body offset')
    utest_val(len(record), header.record_size)
    utest(body, read_kvh_body, file, header, max_size=64)
    # The same record, read from a buffer.
    view = memoryview(data)[offset:]
    utest(header, parse, view)
    utest(body, lambda: bytes(slice_kvh_body(view, header)))
    assert header.record_size is not None
    offset += header.record_size
  utest_val(b'', file.read())
  utest_val(len(data), offset)


@utest_run
def test_body() -> None:

  def read(data:bytes, max_size:int=1024) -> bytes:
    file = BytesIO(data)
    return read_kvh_body(file, read_kvh_header(file, max_size=1024), max_size=max_size)

  def slice_body(data:bytes) -> bytes: return bytes(slice_kvh_body(data, parse(data)))

  # Without a declared size the body extends to the end.
  header_bytes = render_kvh_header('fmt', 1, {})
  utest_val(None, parse(header_bytes).record_size)
  for body in (b'', b'payload', bytes(100)):
    utest(body, read, header_bytes + body)
    utest(body, slice_body, header_bytes + body)
  utest(b'x' * 8, read, header_bytes + b'x' * 8, max_size=8)
  utest_exc(KvhBodyError('body exceeds max_size: 7.'), read, header_bytes + b'x' * 8, max_size=7)

  # With a declared size the body and padding are verified.
  header_bytes = render_kvh_header('fmt', 1, {}, body_size=7)
  record = header_bytes + b'payload' + bytes(57)
  for fn in (read, slice_body):
    utest(b'payload', fn, record)
    utest(b'payload', fn, record + b'following data')
    utest_exc(KvhBodyError('body is truncated: expected 7 bytes; received 0.'), fn, header_bytes)
    utest_exc(KvhBodyError('body is truncated: expected 7 bytes; received 3.'), fn, header_bytes + b'pay')
    utest_exc(KvhBodyError('body padding is truncated: expected 57 bytes; received 0.'), fn, header_bytes + b'payload')
    utest_exc(KvhBodyError('body padding is truncated: expected 57 bytes; received 56.'), fn, record[:-1])
    utest_exc(KvhBodyError('body padding contains non-NUL bytes.'), fn, record[:-1] + b'x')
    utest_exc(KvhBodyError('body padding contains non-NUL bytes.'), fn, header_bytes + b'payloadx' + bytes(56))
  utest(b'payload', read, record, max_size=7)
  utest_exc(KvhBodyError('body size 7 exceeds max_size: 6.'), read, record, max_size=6)
  # A declared size that exceeds the limit is rejected without reading the body.
  utest_exc(KvhBodyError('body size 9007199254740991 exceeds max_size: 1024.'),
    read, render_kvh_header('fmt', 1, {}, body_size=(1<<53)-1))

  # A body whose size is a multiple of the alignment has no padding.
  header_bytes = render_kvh_header('fmt', 1, {}, body_size=64)
  for fn in (read, slice_body):
    utest(b'x' * 64, fn, header_bytes + b'x' * 64)
    utest(b'', fn, render_kvh_header('fmt', 1, {}, body_size=0))

  # Reading leaves the file positioned after the record.
  file = BytesIO(record + b'following data')
  utest(b'payload', lambda: read_kvh_body(file, read_kvh_header(file, max_size=1024), max_size=1024))
  utest_val(b'following data', file.read())


@utest_run
def test_header_size() -> None:
  utest(padded(b'KVH\0 fmt v1\nHEADER_SIZE 64\nk v\n'), render_kvh_header, 'fmt', 1, {'k': 'v'}, header_size=64)
  utest(padded(b'KVH\0 fmt v1\nHEADER_SIZE 192\nBODY_SIZE 5\nk v\n') + bytes(128),
    render_kvh_header, 'fmt', 1, {'k': 'v'}, header_size=192, body_size=5)
  for header_size in (64, 128, 4096):
    data = render_kvh_header('fmt', 1, {'k': 'v'}, header_size=header_size)
    utest_val(header_size, len(data))
    header = parse(data + b'payload', max_size=header_size)
    utest_val(header_size, header.header_size)
    utest_val(({'k': 'v'}, {}), (header.items, header.unrecognized_reserved_items))
    utest_exc(KvhHeaderError(f'header exceeds max_size: {header_size-1}.'), parse, data, max_size=header_size-1)
  for header_size in (-64, 0, 1, 63, 65, 100, (1<<53)):
    utest_exc(KvhHeaderError(f'invalid header size: {header_size}; expected a positive multiple of 64.'),
      render_kvh_header, 'fmt', 1, {}, header_size=header_size)
  utest_exc(KvhHeaderError('header requires 79 bytes, which exceeds the header size: 64.'),
    render_kvh_header, 'fmt', 1, {'k': 'v' * 48}, header_size=64)
  utest(64, lambda: len(render_kvh_header('fmt', 1, {'k': 'v' * 33}, header_size=64))) # The text and terminator fill the block.
  utest_exc(KvhHeaderError('header requires 65 bytes, which exceeds the header size: 64.'),
    render_kvh_header, 'fmt', 1, {'k': 'v' * 34}, header_size=64)

  def text(header_size_text:bytes) -> bytes: return b'KVH\0 fmt v1\nk v\nHEADER_SIZE ' + header_size_text + b'\n\0'

  utest(128, lambda: parse(text(b'128') + bytes(128)).header_size)
  utest_exc(KvhHeaderError('invalid HEADER_SIZE: 0; expected a multiple of 64 that is at least 31.'),
    parse, text(b'0') + bytes(128))
  utest_exc(KvhHeaderError('invalid HEADER_SIZE: 100; expected a multiple of 64 that is at least 33.'),
    parse, text(b'100') + bytes(128))
  long_text = b'KVH\0 fmt v1\nHEADER_SIZE 64\nk ' + b'v' * 40 + b'\n\0'
  utest_exc(KvhHeaderError('invalid HEADER_SIZE: 64; expected a multiple of 64 that is at least 71.'),
    parse, long_text + bytes(128))
  utest_exc(KvhHeaderError('header padding contains non-NUL bytes.'), parse, text(b'128') + bytes(64) + b'x' + bytes(63))
  utest_exc(KvhHeaderError('header is truncated at offset 100.'), parse, (text(b'128') + bytes(128))[:100])
  utest_exc(KvhHeaderError('header exceeds max_size: 1024.'), parse, text(b'9007199254740928') + bytes(128))
  utest_exc(KvhHeaderError("line 3: invalid HEADER_SIZE: '064'."), parse, text(b'064') + bytes(128))
  utest_exc(KvhHeaderError('line 4: invalid HEADER_SIZE: value has multiple lines.'), parse, text(b'64\n\t') + bytes(128))


@utest_run
def test_item_size() -> None:
  for key, value in (('k', 'v'), ('k', ''), ('?k', ' v '), ('k', 'a\n\n b'), ('k', 'café\n'), ('BODY_SIZE', '12'),
   ('?SUM', 'abc')):
    utest(len(item_text(key, value)), kvh_item_size, key, value)
  utest_val([4, 2, 10, 6], [kvh_item_size(k, v) for k, v in (('k', 'v'), ('k', ''), ('k', 'a\n\n b'), ('k', '\n\n'))])
  utest_val(27, kvh_item_size(kvh_body_size_key, str(kvh_max_int)))
  utest_exc(KvhHeaderError("invalid key: 'a b'."), kvh_item_size, 'a b', 'v')
  utest_exc(KvhHeaderError("value for key 'k' contains invalid character: '\\x00'."), kvh_item_size, 'k', '\0')
  utest_exc(KvhHeaderError, kvh_item_size, 'k', '\ud800')


@utest_run
def test_reserve_size() -> None:
  utest_exc(KvhHeaderError('reserve_size cannot be combined with header_size.'),
    render_kvh_header, 'fmt', 1, {}, reserve_size=1, header_size=64)
  utest_exc(KvhHeaderError('invalid reserve size: -1.'), render_kvh_header, 'fmt', 1, {}, reserve_size=-1)
  utest_exc(KvhHeaderError(f'invalid reserve size: {kvh_max_int}.'), render_kvh_header, 'fmt', 1, {}, reserve_size=kvh_max_int)
  utest(padded(b'KVH\0 fmt v1\nk v\n'), render_kvh_header, 'fmt', 1, {'k': 'v'}, reserve_size=0) # No header size is declared.

  # The reserved space is sufficient for the measured items, whatever the length of the header text.
  late_items = {'?sha256': '0' * 64, 'count': '123456\n7'}
  reserve_size = kvh_item_size(kvh_body_size_key, str(kvh_max_int)) + sum(kvh_item_size(k, v) for k, v in late_items.items())
  for value_len in range(kvh_alignment * 2):
    items = {'k': 'v' * value_len}
    reserved = render_kvh_header('fmt', 1, items, reserve_size=reserve_size)
    header = parse(reserved)
    utest_val((None, len(reserved), items), (header.body_size, header.header_size, header.items))
    filled = render_kvh_header('fmt', 1, items | late_items, body_size=kvh_max_int, header_size=len(reserved))
    utest_val(len(reserved), len(filled))
    utest_val((kvh_max_int, items | late_items), (parse(filled).body_size, parse(filled).items))
    # The reservation is exact: the terminator and padding of the filled header fit in one block.
    assert len(filled) - len(filled.rstrip(b'\0')) <= kvh_alignment, (value_len, len(filled))
  # An item of exactly the reserved size fits.
  for reserve_size in range(4, kvh_alignment * 2):
    reserved = render_kvh_header('fmt', 1, {}, reserve_size=reserve_size)
    late_items = {'k': 'v' * (reserve_size - 3)}
    utest_val(reserve_size, kvh_item_size('k', late_items['k']))
    utest(len(reserved), lambda: len(render_kvh_header('fmt', 1, late_items, header_size=len(reserved))))

  # A body size that is already known can be combined with a reservation.
  reserved = render_kvh_header('fmt', 1, {}, body_size=5, reserve_size=100)
  utest_val((5, len(reserved)), (parse(reserved).body_size, parse(reserved).header_size))

  # Stream a body of unknown size, then fill in the size and a hash.
  items = {'name': 'example', 'meta': json_value}
  body = b'\0streamed payload' * 10
  file = BytesIO()
  file.write(b'prefix')
  reserve_size = kvh_item_size(kvh_body_size_key, str(kvh_max_int)) + kvh_item_size('?sha256', '0' * 64)
  reserved = render_kvh_header('fmt', 1, items, reserve_size=reserve_size)
  file.write(reserved)
  file.write(body)
  file.write(bytes(kvh_padding_size(len(body))))
  file.write(render_kvh_header('fmt', 1, {'idx': '2'}))
  file.seek(len(b'prefix'))
  final_items = items | {'?sha256': sha256(body).hexdigest()}
  file.write(render_kvh_header('fmt', 1, final_items, body_size=len(body), header_size=len(reserved)))
  file.seek(len(b'prefix'))
  header = read_kvh_header(file, max_size=1024)
  utest_val((final_items, len(body), len(reserved)), (header.items, header.body_size, header.header_size))
  utest(body, read_kvh_body, file, header, max_size=1024)
  utest({'idx': '2'}, lambda: read_kvh_header(file, max_size=1024).items)


@utest_run
def test_limits() -> None:
  data = render_kvh_header('fmt', 1, {'a': '1', 'b': '2\n3'})
  utest_val(kvh_alignment, len(data))
  utest(kvh_alignment, lambda: parse(data, max_size=kvh_alignment).header_size)
  for max_size in range(kvh_alignment):
    utest_exc(KvhHeaderError(f'header exceeds max_size: {max_size}.'), parse, data, max_size=max_size)
  # A header without a terminator is rejected at the size limit, regardless of the data length.
  endless = b'KVH\0 fmt v1\nk v\n' + b'\tline\n' * 1000
  utest_exc(KvhHeaderError('header exceeds max_size: 256.'), parse, endless, max_size=256)
  utest_exc(KvhHeaderError('header exceeds max_size: 256.'), parse, b'KVH\0 fmt v1\nk ' + b'v' * 1000, max_size=256)


@utest_run
def test_parse_errors() -> None:
  utest_exc(KvhHeaderError("not a KVH header; expected magic b'KVH\\x00 '; received b''."), parse, b'')
  utest_exc(KvhHeaderError("not a KVH header; expected magic b'KVH\\x00 '; received b'kvh\\x00 '."),
    parse, padded(b'kvh\0 fmt v1\n'))
  utest_exc(KvhHeaderError('line 2: continuation line precedes the first item.'), parse, padded(b'KVH\0 fmt v1\n\tv\n'))
  utest_exc(KvhHeaderError("line 2: invalid key: ''."), parse, padded(b'KVH\0 fmt v1\n\nk v\n'))
  utest_exc(KvhHeaderError("line 3: invalid key: ''."), parse, padded(b'KVH\0 fmt v1\nk v\n v\n'))
  utest_exc(KvhHeaderError("line 2: invalid key: 'k\\tv'."), parse, padded(b'KVH\0 fmt v1\nk\tv\n'))
  utest_exc(KvhHeaderError("line 2: invalid key: '?'."), parse, padded(b'KVH\0 fmt v1\n? v\n'))
  utest_exc(KvhHeaderError("line 2: invalid key: '??k'."), parse, padded(b'KVH\0 fmt v1\n??k v\n'))
  utest_exc(KvhHeaderError("line 4: duplicate key: 'k'."), parse, padded(b'KVH\0 fmt v1\nk v\nj\nk w\n'))
  utest_exc(KvhHeaderError("line 2: key is followed by a space but no value: 'k'."), parse, padded(b'KVH\0 fmt v1\nk \n'))
  utest_exc(KvhHeaderError("line 3: value contains invalid character: '\\x1e'."),
    parse, padded(b'KVH\0 fmt v1\nk v\n\ta\x1eb\n'))
  utest_exc(KvhHeaderError("line 2: value contains invalid character: '\\x00'."), parse, padded(b'KVH\0 fmt v1\nk a\0b\n'))
  utest_exc(KvhHeaderError, parse, padded(b'KVH\0 fmt v1\nk \xff\n')) # Invalid UTF-8.
  utest_exc(KvhHeaderError('header padding contains non-NUL bytes.'), parse, b'KVH\0 fmt v1\n\0' + b'x' * 64)


@utest_run
def test_truncation() -> None:
  data = render_kvh_header('fmt', 1, {'a': '1', 'b': '2\n3'})
  for size in range(len(data)):
    utest_exc(KvhHeaderError, parse, data[:size])
  utest_exc(KvhHeaderError('header is truncated at offset 16.'), parse, b'KVH\0 fmt v1\nk v\n')
  utest_exc(KvhHeaderError('header is truncated at offset 15.'), parse, b'KVH\0 fmt v1\nk v')
  utest_exc(KvhHeaderError('header is truncated at offset 17.'), parse, b'KVH\0 fmt v1\nk v\n\0')
