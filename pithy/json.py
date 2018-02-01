# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
import json as _json

from json.decoder import JSONDecodeError
from datetime import datetime
from sys import stderr, stdout
from typing import Any, Callable, Dict, Iterable, Hashable, List, Optional, Sequence, TextIO, Union


JsonAny = Any # TODO: remove this once recursive types work.
JsonList = List[JsonAny]
JsonDict = Dict[Hashable, JsonAny]
JsonDictIn = Dict[str, Any]

Json = Union[None, int, float, str, bool, JsonList, JsonDict]

JsonDefaulter = Callable[[Any], Any]


def json_encode_default(obj: Any) -> Any:
  try: return list(obj) # try to convert sequences first.
  except TypeError: pass
  return str(obj) # convert to string as last resort.


def json_encode_with_asdict(obj: Any) -> Any:
  '''
  JsonEncoder default function that first tries to invoke the `_asdict` method on `obj`.
  This is supported by namedtuple, NamedTuple, and pithy.immutbale.Immutable.
  '''
  try: return obj._asdict()
  except AttributeError: pass
  return json_encode_default(obj)


def write_json(file: TextIO, *items: Any, default: JsonDefaulter=json_encode_default, sort=True, indent=2, end='\n', flush=False, **kwargs) -> None:
  'Write each item in `items` as json to file.'
  for item in items:
    _json.dump(item, file, indent=indent, default=default, sort_keys=sort, **kwargs)
    if end:
      file.write(end)
  if flush:
    file.flush()


def err_json(*items: Any, default: JsonDefaulter=json_encode_default, sort=True, indent=2, end='\n', flush=False, **kwargs) -> None:
  'Write items as json to std err.'
  write_json(stderr, *items, default=default, sort=sort, indent=indent, **kwargs)


def out_json(*items: Any, default: JsonDefaulter=json_encode_default, sort=True, indent=2, end='\n', flush=False, **kwargs) -> None:
  write_json(stdout, *items, default=default, sort=sort, indent=indent, **kwargs)


def write_jsonl(file: TextIO, *items: Any, default: JsonDefaulter=json_encode_default, sort=True, flush=False, **kwargs) -> None:
  'Write each item in `items` as jsonl to file.'
  for item in items:
    _json.dump(item, file, indent=None, default=default, sort_keys=sort, **kwargs)
    file.write('\n')
  if flush:
    file.flush()


def err_jsonl(*items: Any, default: JsonDefaulter=json_encode_default, sort=True, flush=False, **kwargs) -> None:
  'Write items as jsonl to std err.'
  write_jsonl(stderr, *items, default=default, sort=sort, flush=flush, **kwargs)


def out_jsonl(*items: Any, default: JsonDefaulter=json_encode_default, sort=True, flush=False, **kwargs) -> None:
  'Write items as jsonl to std out.'
  write_jsonl(stdout, *items, default=default, sort=sort, flush=flush, **kwargs)


# input.


def _mk_hook(types: Sequence) -> Optional[Callable[[Dict[Any, Any]], Any]]:
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

  def _read_json_object_hook(d: Dict) -> Any:
    keys = frozenset(d.keys())
    try:
      record_type = type_map[keys]
    except KeyError: return d
    return record_type(**d)

  return _read_json_object_hook


def _mk_decoder(types: Sequence) -> _json.JSONDecoder:
  return _json.JSONDecoder(object_hook=_mk_hook(types))


_ws_re = re.compile(r'[ \t\n\r]*') # identical to json.decoder.WHITESPACE.


def parse_json(string: str, types: Sequence[type]=()) -> Any:
  '''
  Parse json from `string`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  return _json.loads(string, object_hook=_mk_hook(types))


def load_json(file: TextIO, types: Sequence[type]=()) -> Any:
  '''
  Read json from `file`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  return _json.load(file, object_hook=_mk_hook(types))


def parse_jsonl(string: str, types: Sequence[type]=()) -> Iterable[Any]:
  hook = _mk_hook(types)
  return (_json.loads(line, object_hook=hook) for line in string.splitlines())


def load_jsonl(stream: Iterable[str], types: Sequence[type]=()) -> Iterable[Any]:
  hook = _mk_hook(types)
  return (_json.loads(line, object_hook=hook) for line in stream)


def parse_jsons(string: str, types: Sequence[type]=()) -> Iterable[Any]:
  '''
  Parse multiple json objects from `string`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  decoder = _mk_decoder(types)
  idx = _ws_re.match(string, 0).end() # must consume leading whitespace for the decoder.
  while idx < len(string):
    obj, end = decoder.raw_decode(string, idx)
    yield obj
    idx = _ws_re.match(string, end).end()


def load_jsons(file: TextIO, types: Sequence[type]=()) -> Iterable[Any]:
  # TODO: it seems like we ought to be able to stream the file into the parser,
  # but JSONDecoder requires the entire string for a single JSON segment.
  # Therefore in order to stream we would need to read into a buffer,
  # count nesting tokens (accounting for strings and escaped characters inside of them),
  # identify object boundaries and create substrings to pass to the decoder.
  # For now just read the whole thing at once.
  return parse_jsons(file.read(), types=types)
