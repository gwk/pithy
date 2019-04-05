# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import json as _json
import re
from dataclasses import fields, is_dataclass
from json.decoder import JSONDecodeError
from sys import stderr, stdout, version_info
from typing import IO, Any, Callable, Dict, FrozenSet, Hashable, Iterable, List, Optional, Sequence, TextIO, Tuple, Union

from .util import EncodeObj, all_slots, encode_obj


JsonAny = Any # TODO: remove this once recursive types work.
JsonList = List[JsonAny]
JsonDict = Dict[str, JsonAny]
Json = Union[None, int, float, str, bool, JsonList, JsonDict]

JsonText = Union[str,bytes,bytearray]

class JSONEmptyDocument(JSONDecodeError): pass

_Seps = Optional[Tuple[str,str]]


def render_json(item:Any, default:EncodeObj=encode_obj, sort=True, indent:Optional[int]=2, separators:_Seps=None, **kwargs) -> str:
  'Render `item` as a json string.'
  if not separators:
    separators = (',', ': ') if indent else (',', ':')
  return _json.dumps(item, indent=indent, default=default, sort_keys=sort, separators=separators, **kwargs)


def write_json(file:TextIO, *items:Any, default:EncodeObj=encode_obj, sort=True, indent:Optional[int]=2, separators:_Seps=None, end='\n', flush=False, **kwargs) -> None:
  'Write each item in `items` as json to file.'
  if not separators:
    separators = (',', ': ') if indent else (',', ':')
  for item in items:
    _json.dump(item, file, indent=indent, default=default, sort_keys=sort, separators=separators, **kwargs)
    if end: file.write(end)
    if flush: file.flush()


def err_json(*items:Any, default:EncodeObj=encode_obj, sort=True, indent:Optional[int]=2, separators:_Seps=None, end='\n', flush=False, **kwargs) -> None:
  'Write items as json to std err.'
  write_json(stderr, *items, default=default, sort=sort, indent=indent, separators=separators, end=end, flush=flush, **kwargs)


def out_json(*items:Any, default:EncodeObj=encode_obj, sort=True, indent:Optional[int]=2, separators:_Seps=None, end='\n', flush=False, **kwargs) -> None:
  write_json(stdout, *items, default=default, sort=sort, indent=indent, separators=separators, end=end, flush=flush, **kwargs)


def write_jsonl(file:TextIO, *items:Any, default:EncodeObj=encode_obj, sort=True, separators:_Seps=None, flush=False, **kwargs) -> None:
  'Write each item in `items` as jsonl to file.'
  if separators:
    assert '\n' not in separators[0]
    assert '\n' not in separators[1]
  else:
    separators = (',', ':')
  for item in items:
    _json.dump(item, file, indent=None, default=default, sort_keys=sort, separators=separators, **kwargs)
    file.write('\n')
    if flush: file.flush()


def err_jsonl(*items:Any, default:EncodeObj=encode_obj, sort=True, separators:_Seps=None, flush=False, **kwargs) -> None:
  'Write items as jsonl to std err.'
  write_jsonl(stderr, *items, default=default, sort=sort, separators=separators, flush=flush, **kwargs)


def out_jsonl(*items:Any, default:EncodeObj=encode_obj, sort=True, separators:_Seps=None, flush=False, **kwargs) -> None:
  'Write items as jsonl to std out.'
  write_jsonl(stdout, *items, default=default, sort=sort, separators=separators, flush=flush, **kwargs)


# input.


def _hook_type_keys(type) -> FrozenSet[str]:
  if is_dataclass(type): return frozenset(f.name for f in fields(type))

  try: return frozenset(type._fields) # namedtuple or similar.
  except AttributeError: pass

  slots = all_slots(type)
  if slots: return frozenset(slots)
  else: raise TypeError(f'JSON decode type must be either a dataclass, namedtuple, or define `__slots__`: {type}')


def _mk_hook(types:Sequence) -> Optional[Callable[[Dict[Any, Any]], Any]]:
  '''
  Provide a hook function that creates custom objects from json.
  `types` is a sequence of type objects, each of which must be a dataclass or NamedTuple.
  '''
  if not types: return None

  type_map = { _hook_type_keys(t) : t for t in types }
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


def _mk_decoder(types:Sequence) -> _json.JSONDecoder:
  return _json.JSONDecoder(object_hook=_mk_hook(types))


_ws_re = re.compile(r'[ \t\n\r]*') # identical to json.decoder.WHITESPACE.


def parse_json(text:JsonText, types:Sequence[type]=()) -> Any:
  '''
  Parse json from `text`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  return _json.loads(text, object_hook=_mk_hook(types))


def load_json(file:IO, types:Sequence[type]=()) -> Any:
  '''
  Read json from `file`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching namedtuple types,
  based on field name sets.
  The sets of field names must be unambiguous for all provided record types.
  '''
  try:
    return _json.load(file, object_hook=_mk_hook(types))
  except JSONDecodeError as e:
    if e.pos == 0 and e.msg == 'Expecting value':
      raise JSONEmptyDocument(msg=e.msg, doc=e.doc, pos=e.pos) from e
    else:
      raise


def parse_jsonl(text:JsonText, types:Sequence[type]=()) -> Iterable[Any]:
  hook = _mk_hook(types)
  return (_json.loads(line, object_hook=hook) for line in text.splitlines())


def load_jsonl(stream:Iterable[JsonText], types:Sequence[type]=()) -> Iterable[Any]:
  hook = _mk_hook(types)
  return (_json.loads(line, object_hook=hook) for line in stream)


def parse_jsons(string:str, types:Sequence[type]=()) -> Iterable[Any]:
  '''
  Parse multiple json objects from `string`.
  If `types` is a non-empty sequence,
  then an object hook is passed to the decoder transforms JSON objects into matching dataclass types.
  '''
  decoder = _mk_decoder(types)
  m = _ws_re.match(string, 0)
  assert m is not None
  idx = m.end() # must consume leading whitespace for the decoder.

  while idx < len(string):
    obj, end = decoder.raw_decode(string, idx)
    yield obj
    m = _ws_re.match(string, end)
    assert m is not None
    idx = m.end()


def load_jsons(file:TextIO, types:Sequence[type]=()) -> Iterable[Any]:
  # TODO: it seems like we ought to be able to stream the file into the parser,
  # but JSONDecoder requires the entire string for a single JSON segment.
  # Therefore in order to stream we would need to read into a buffer,
  # count nesting tokens (accounting for strings and escaped characters inside of them),
  # identify object boundaries and create substrings to pass to the decoder.
  # For now just read the whole thing at once.
  return parse_jsons(file.read(), types=types)
