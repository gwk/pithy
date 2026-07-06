# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import json as _json
import re
from io import Reader, Writer
from json.decoder import JSONDecodeError
from sys import stderr, stdout
from typing import Any, Callable, Iterable, Literal, overload, Sequence

from ..encode import encode_obj, EncodeObj
from .fmt import fmt_json_bytes


type JsonList = list['Json']
type JsonDict = dict[str, 'Json']
type Json = None|int|float|str|bool|JsonList|JsonDict

type JsonSequence = Sequence['JsonCo']
type JsonMapping = dict[str, 'JsonCo']
type JsonCo = None|int|float|str|bool|JsonSequence|JsonMapping

JsonText = str|bytes|bytearray

type Syntax = Literal['json', 'jsonc']

json_types = (type(None), bool, int, float, str, list, dict)


class JsonEmptyError(JSONDecodeError): pass

ObjDecodeFn = Callable[[dict],Any]

_Seps = tuple[str,str]|None


def render_json(item:Any, default:EncodeObj=encode_obj, sort:bool=True, indent:int|None=2, separators:_Seps|None=None,
 **kwargs:Any) -> str:
  'Render `item` as a json string.'
  if not separators:
    separators = (',', ': ') if indent else (',', ':')
  return _json.dumps(item, indent=indent, default=default, sort_keys=sort, separators=separators, **kwargs)


def write_json(file:Writer[str], *items:Any, default:EncodeObj=encode_obj, sort:bool=True, indent:int|None=2,
 separators:_Seps|None=None, end:str='\n', flush:bool=False, **kwargs:Any) -> None:
  'Write each item in `items` as json to file.'
  try: write = file.write # If the `file` argument was omitted, the first `item` may have taken its place.
  except AttributeError as e: # We must check for this or else `items` could be empty and we will silently fail.
    raise ValueError('`file` (first) argument does not have a `write` attribute; was the file omitted from the call?') from e

  if not separators:
    separators = (',', ': ') if indent else (',', ':')
  for item in items:
    _json.dump(item, file, indent=indent, default=default, sort_keys=sort, separators=separators, **kwargs)
    if end: write(end)
    if flush:
      try: flush_fn = file.flush # type: ignore[attr-defined]
      except AttributeError: pass
      else: flush_fn()


def err_json(*items:Any, default:EncodeObj=encode_obj, sort:bool=True, indent:int|None=2, separators:_Seps|None=None,
 end:str='\n', flush:bool=False, **kwargs:Any) -> None:
  'Write items as json to std err.'
  write_json(stderr, *items, default=default, sort=sort, indent=indent, separators=separators, end=end, flush=flush, **kwargs)


def out_json(*items:Any, default:EncodeObj=encode_obj, sort:bool=True, indent:int|None=2, separators:_Seps|None=None,
 end:str='\n', flush:bool=False, **kwargs:Any) -> None:
  write_json(stdout, *items, default=default, sort=sort, indent=indent, separators=separators, end=end, flush=flush, **kwargs)


def write_jsonl(file:Writer[str], *items:Any, default:EncodeObj=encode_obj, sort:bool=True, separators:_Seps|None=None,
 flush:bool=False, **kwargs:Any) -> None:
  'Write each item in `items` as jsonl to file.'
  if separators:
    assert '\n' not in separators[0]
    assert '\n' not in separators[1]
  else:
    separators = (',', ':')
  for item in items:
    _json.dump(item, file, indent=None, default=default, sort_keys=sort, separators=separators, **kwargs)
    file.write('\n')
    if flush:
      try: flush_fn = file.flush # type: ignore[attr-defined]
      except AttributeError: pass
      else: flush_fn()


def err_jsonl(*items:Any, default:EncodeObj=encode_obj, sort:bool=True, separators:_Seps|None=None, flush:bool=False,
 **kwargs:Any) -> None:
  'Write items as jsonl to std err.'
  write_jsonl(stderr, *items, default=default, sort=sort, separators=separators, flush=flush, **kwargs)


def out_jsonl(*items:Any, default:EncodeObj=encode_obj, sort:bool=True, separators:_Seps|None=None, flush:bool=False,
 **kwargs:Any) -> None:
  'Write items as jsonl to std out.'
  write_jsonl(stdout, *items, default=default, sort=sort, separators=separators, flush=flush, **kwargs)


# Input.


@overload
def parse_json(text:JsonText|None, object_hook:ObjDecodeFn, syntax:Syntax='json') -> Any: ...

@overload
def parse_json(text:JsonText|None, object_hook:None=None, syntax:Syntax='json') -> Json: ...

def parse_json(text:JsonText|None, object_hook:ObjDecodeFn|None=None, syntax:Syntax='json') -> Any:
  '''
  Parse json from `text`.
  If `syntax` is `'jsonc'`, `text` is first preprocessed to strip comments and fix commas.
  '''
  if text is None: return None
  if syntax == 'jsonc':
    data = text.encode() if isinstance(text, str) else bytes(text)
    text = b''.join(fmt_json_bytes(data, fix=True))
  return _json.loads(text, object_hook=object_hook)


@overload
def load_json(file:Reader, object_hook:ObjDecodeFn, syntax:Syntax='json') -> Any: ...

@overload
def load_json(file:Reader, object_hook:None=None, syntax:Syntax='json') -> Json: ...

def load_json(file:Reader, object_hook:ObjDecodeFn|None=None, syntax:Syntax='json') -> Any:
  '''
  Read json from `file`.
  If `syntax` is `'jsonc'`, the file contents are first preprocessed to strip comments and fix commas.
  '''
  try:
    if syntax == 'jsonc':
      return parse_json(file.read(), object_hook=object_hook, syntax=syntax)
    return _json.load(file, object_hook=object_hook)
  except JSONDecodeError as e:
    if e.pos == 0 and e.msg == 'Expecting value':
      raise JsonEmptyError(msg=e.msg, doc=e.doc, pos=e.pos) from e
    else:
      raise


@overload
def parse_jsonl(text:JsonText, object_hook:ObjDecodeFn, syntax:Syntax='json') -> Iterable[Any]: ...

@overload
def parse_jsonl(text:JsonText, object_hook:None=None, syntax:Syntax='json') -> Iterable[Json]: ...

def parse_jsonl(text:JsonText, object_hook:ObjDecodeFn|None=None, syntax:Syntax='json') -> Iterable[Any]:
  return load_jsonl(text.splitlines(), object_hook=object_hook, syntax=syntax)


@overload
def load_jsonl(stream:Iterable[JsonText], object_hook:ObjDecodeFn, syntax:Syntax='json') -> Iterable[Any]: ...

@overload
def load_jsonl(stream:Iterable[JsonText], object_hook:None=None, syntax:Syntax='json') -> Iterable[Json]: ...

def load_jsonl(stream:Iterable[JsonText], object_hook:ObjDecodeFn|None=None, syntax:Syntax='json') -> Iterable[Any]:
  if isinstance(stream, (str,bytes,bytearray)): raise TypeError('`stream` argument must be an iterable of text.')
  for line in stream:
    if not line or line.isspace(): continue
    yield parse_json(line, object_hook=object_hook, syntax=syntax)


@overload
def parse_jsons(string:str, object_hook:ObjDecodeFn, syntax:Syntax='json') -> Iterable[Any]: ...

@overload
def parse_jsons(string:str, object_hook:None=None, syntax:Syntax='json') -> Iterable[Json]: ...

def parse_jsons(string:str, object_hook:ObjDecodeFn|None=None, syntax:Syntax='json') -> Iterable[Any]:
  '''
  Parse multiple json objects from `string`.
  If `syntax` is `'jsonc'`, `string` is first preprocessed to strip comments and fix commas.
  '''
  if syntax == 'jsonc':
    string = b''.join(fmt_json_bytes(string.encode(), fix=True)).decode()
  decoder = _json.JSONDecoder(object_hook=object_hook)
  m = _json_ws_re.match(string, 0)
  assert m is not None
  idx = m.end() # must consume leading whitespace for the decoder.

  while idx < len(string):
    obj, end = decoder.raw_decode(string, idx)
    yield obj
    if syntax == 'jsonc' and end < len(string) and string[end] == ',':
      end += 1 # `fmt_json_bytes` inserts commas between sibling top-level values; skip over them.
    m = _json_ws_re.match(string, end)
    assert m is not None
    idx = m.end()


@overload
def load_jsons(file:Reader[str], object_hook:ObjDecodeFn, syntax:Syntax='json') -> Iterable[Any]: ...

@overload
def load_jsons(file:Reader[str], object_hook:None=None, syntax:Syntax='json') -> Iterable[Json]: ...

def load_jsons(file:Reader[str], object_hook:ObjDecodeFn|None=None, syntax:Syntax='json') -> Iterable[Any]:
  # TODO: it seems like we ought to be able to stream the file into the parser,
  # but JSONDecoder requires the entire string for a single JSON segment.
  # Therefore in order to stream we would need to read into a buffer,
  # count nesting tokens (accounting for strings and escaped characters inside of them),
  # identify object boundaries and create substrings to pass to the decoder.
  # For now just read the whole thing at once.
  return parse_jsons(file.read(), object_hook=object_hook, syntax=syntax)


def req_json_list(obj:Json) -> JsonList:
  if not isinstance(obj, list): raise TypeError(f'expected type: list; actual type: {type(obj)}; value: {obj!r}')
  return obj


def req_json_dict(obj:Json) -> JsonDict:
  if not isinstance(obj, dict): raise TypeError(f'expected type: dict; actual type: {type(obj)}; value: {obj!r}')
  return obj


def req_opt_json_list(obj:Json) -> JsonList|None:
  if not (obj is None or isinstance(obj, list)):
    raise TypeError(f'expected type: JsonList|None; actual type: {type(obj)}; value: {obj!r}')
  return obj


def req_opt_json_dict(obj:Json) -> JsonDict|None:
  if not (obj is None or isinstance(obj, dict)):
    raise TypeError(f'expected type: JsonDict|None; actual type: {type(obj)}; value: {obj!r}')
  return obj


_json_ws_re = re.compile(r'[ \t\n\r]*') # identical to json.decoder.WHITESPACE.
