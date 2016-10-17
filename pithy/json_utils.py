# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import json as _json
import json.decoder as _json_dec

from sys import stdout


class JsonEncoder(_json.JSONEncoder):
  'JSONEncoder subclass that handles all sequence types.'

  def default(self, obj):
    try: return obj._asdict()
    except AttributeError: pass
    return list(obj)


def write_json(file, *items, indent=2, sort=True, end='\n', cls=JsonEncoder, flush=False):
  'Write `items` as json to file.'
  # TODO: remaining options with sensible defaults.
  for item in items:
    _json.dump(item, file, indent=indent, sort_keys=sort, cls=cls)
    if end:
      file.write(end)
  if flush:
    file.flush()


def err_json(*items, indent=2, sort=True, end='\n', cls=JsonEncoder, flush=False):
  'Write items as json to std err.'
  write_json(stderr, *items, indent=indent, sort=sort, end=end, cls=cls, flush=flush)


def out_json(*items, indent=2, sort=True, end='\n', cls=JsonEncoder, flush=False):
  write_json(stdout, *items, indent=indent, sort=sort, end=end, cls=cls, flush=flush)



# input.


def _mk_json_types_hook(types):
  '''
  Provide a hook function that creates custom objects from json.
  `types` is a sequence of type objects, each of which must have a `_fields` property.
  NamedTuple instances are compatible.
  '''
  if not types: return None

  type_map = { frozenset(t._fields) : t for t in types }
  if len(type_map) < len(types):
    # TODO: find all offending pairs.
    raise ValueError('provided record types are ambiguous (identical field name sets).')

  def _read_json_object_hook(d):
    keys = frozenset(d.keys())
    try:
      record_type = type_map[keys]
    except KeyError: return d
    return record_type(**d)

  return _read_json_object_hook


def parse_json(string, types=()):
  '''
  Parse json from `string`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  hook = _mk_json_types_hook(types)
  return _json.loads(string, object_hook=hook)


def parse_jsons(string, types=()):
  '''
  Parse multiple json objects from `string`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  hook = _mk_json_types_hook(types)
  decoder = _json.JSONDecoder(object_hook=hook)
  ws_re = _json_dec.WHITESPACE

  idx = ws_re.match(string, 0).end() # must consume leading whitespace for the decoder.
  while idx < len(string):
    obj, end = decoder.raw_decode(string, idx)
    yield obj
    idx = ws_re.match(string, end).end()


def load_json(file, types=()):
  '''
  Read json from `file`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  hook = _mk_json_types_hook(types)
  return _json.load(file, object_hook=hook)


def load_jsons(file, types=()):
  # TODO: it seems like we ought to be able to stream the file into the parser,
  # but JSONDecoder requires the entire string for a single JSON segment.
  # Therefore in order to stream we would need to read into a buffer,
  # count nesting tokens (accounting for strings and escaped characters inside of them),
  # identify object boundaries and create substrings to pass to the decoder.
  # For now just read the whole thing at once.
  return parse_jsons(file.read(), types=types)
