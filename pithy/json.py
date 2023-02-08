# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import json as _json
import re
from dataclasses import fields, is_dataclass
from io import BytesIO
from json.decoder import JSONDecodeError
from sys import stderr, stdout
from typing import (IO, AbstractSet, Any, BinaryIO, Callable, Dict, FrozenSet, Iterable, List, Optional, Sequence, TextIO,
  Tuple, Union)

from .encode import EncodeObj, all_slots, encode_obj


JsonAny = Any # TODO: remove this once recursive types work.
JsonList = List[JsonAny]
JsonDict = Dict[str, JsonAny]
Json = Union[None, int, float, str, bool, JsonList, JsonDict]

JsonText = Union[str,bytes,bytearray]

class JSONEmptyDocument(JSONDecodeError): pass

ObjDecodeFn = Callable[[Dict],Any]
ObjDecodeHook = Union[type, Tuple[AbstractSet[str],Union[type,ObjDecodeFn]]]
ObjDecodeHooks = Sequence[ObjDecodeHook]

_Seps = Optional[Tuple[str,str]]


def render_json(item:Any, default:EncodeObj=encode_obj, sort=True, indent:int|None=2, separators:_Seps|None=None, **kwargs) -> str:
  'Render `item` as a json string.'
  if not separators:
    separators = (',', ': ') if indent else (',', ':')
  return _json.dumps(item, indent=indent, default=default, sort_keys=sort, separators=separators, **kwargs)


def write_json(file:TextIO, *items:Any, default:EncodeObj=encode_obj, sort=True, indent:int|None=2, separators:_Seps|None=None, end='\n', flush=False, **kwargs) -> None:
  'Write each item in `items` as json to file.'
  try: write = file.write # If the `file` argument was omitted, the first `item` may have taken its place.
  except AttributeError as e: # We must check for this or else `items` could be empty and we will silently fail.
    raise ValueError('`file` (first) argument does not have a `write` attribute; was the file omitted from the call?') from e

  if not separators:
    separators = (',', ': ') if indent else (',', ':')
  for item in items:
    _json.dump(item, file, indent=indent, default=default, sort_keys=sort, separators=separators, **kwargs)
    if end: write(end)
    if flush: file.flush()


def err_json(*items:Any, default:EncodeObj=encode_obj, sort=True, indent:int|None=2, separators:_Seps|None=None, end='\n', flush=False, **kwargs) -> None:
  'Write items as json to std err.'
  write_json(stderr, *items, default=default, sort=sort, indent=indent, separators=separators, end=end, flush=flush, **kwargs)


def out_json(*items:Any, default:EncodeObj=encode_obj, sort=True, indent:int|None=2, separators:_Seps|None=None, end='\n', flush=False, **kwargs) -> None:
  write_json(stdout, *items, default=default, sort=sort, indent=indent, separators=separators, end=end, flush=flush, **kwargs)


def write_jsonl(file:TextIO, *items:Any, default:EncodeObj=encode_obj, sort=True, separators:_Seps|None=None, flush=False, **kwargs) -> None:
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


def err_jsonl(*items:Any, default:EncodeObj=encode_obj, sort=True, separators:_Seps|None=None, flush=False, **kwargs) -> None:
  'Write items as jsonl to std err.'
  write_jsonl(stderr, *items, default=default, sort=sort, separators=separators, flush=flush, **kwargs)


def out_jsonl(*items:Any, default:EncodeObj=encode_obj, sort=True, separators:_Seps|None=None, flush=False, **kwargs) -> None:
  'Write items as jsonl to std out.'
  write_jsonl(stdout, *items, default=default, sort=sort, separators=separators, flush=flush, **kwargs)


# input.


def parse_json(text:JsonText, hook:ObjDecodeFn|None=None, hooks:ObjDecodeHooks=()) -> Any:
  '''
  Parse json from `text`.
  '''
  return _json.loads(text, object_hook=_mk_hook(hook, hooks))


def load_json(file:IO, hook: ObjDecodeFn|None=None, hooks:ObjDecodeHooks=()) -> Any:
  '''
  Read json from `file`.
  '''
  try:
    return _json.load(file, object_hook=_mk_hook(hook, hooks))
  except JSONDecodeError as e:
    if e.pos == 0 and e.msg == 'Expecting value':
      raise JSONEmptyDocument(msg=e.msg, doc=e.doc, pos=e.pos) from e
    else:
      raise


def parse_jsonl(text:JsonText, hook:ObjDecodeFn|None=None, hooks:ObjDecodeHooks=()) -> Iterable[Any]:
  return load_jsonl(text.splitlines(), hook=hook, hooks=hooks)


def load_jsonl(stream:Iterable[JsonText], hook:ObjDecodeFn|None=None, hooks:ObjDecodeHooks=()) -> Iterable[Any]:
  if isinstance(stream, (str,bytes,bytearray)): raise TypeError('`stream` argument must be an iterable of text.')
  hook = _mk_hook(hook, hooks)
  for line in stream:
    if not line or line.isspace(): continue
    yield _json.loads(line, object_hook=hook)


def parse_jsons(string:str, hook:ObjDecodeFn|None=None, hooks:ObjDecodeHooks=()) -> Iterable[Any]:
  '''
  Parse multiple json objects from `string`.
  '''
  hook = _mk_hook(hook, hooks)
  decoder = _json.JSONDecoder(object_hook=hook)
  m = _ws_re.match(string, 0)
  assert m is not None
  idx = m.end() # must consume leading whitespace for the decoder.

  while idx < len(string):
    obj, end = decoder.raw_decode(string, idx)
    yield obj
    m = _ws_re.match(string, end)
    assert m is not None
    idx = m.end()


def load_jsons(file:TextIO, hook:ObjDecodeFn|None=None, hooks:ObjDecodeHooks=()) -> Iterable[Any]:
  # TODO: it seems like we ought to be able to stream the file into the parser,
  # but JSONDecoder requires the entire string for a single JSON segment.
  # Therefore in order to stream we would need to read into a buffer,
  # count nesting tokens (accounting for strings and escaped characters inside of them),
  # identify object boundaries and create substrings to pass to the decoder.
  # For now just read the whole thing at once.
  return parse_jsons(file.read(), hook=hook, hooks=hooks)


def _mk_hook(hook:ObjDecodeFn|None, hooks:ObjDecodeHooks) -> Optional[Callable[[Dict[Any,Any]],Any]]:
  '''
  Provide a hook function to deserialize JSON into the provided types.
  '''
  if not hooks: return hook
  dflt_hook:ObjDecodeFn = lambda d: d if hook is None else hook

  type_map:Dict[FrozenSet[str],Any] = {}
  for h in hooks:

    fn:ObjDecodeFn
    if isinstance(h, type):
      keys_raw = _hook_type_keys(h)
      fn = _hook_type_fn(h)
    else:
      try: keys_raw, fn_raw = h # Explicit pair.
      except Exception as e:
        raise ValueError(f'malformed decoder hook; expected (keys, constructor) pair; received: {h!r}') from e
      fn = _hook_type_fn(fn_raw) if isinstance(fn_raw, type) else fn_raw
      if isinstance(keys_raw, str): raise TypeError(keys_raw) # type: ignore[unreachable]

    keys = frozenset(keys_raw)
    if keys in type_map:
      raise ValueError(f'conflicting type hooks for key set {keys}:\n  {type_map[keys]}\n  {fn}')
    type_map[keys] = fn

  def types_object_hook(d:Dict) -> Any:
    keys = frozenset(d.keys())
    try: record_type = type_map[keys]
    except KeyError: return dflt_hook(d)
    return record_type(**d)

  return types_object_hook


def _hook_type_keys(t:type) -> AbstractSet[str]:
  if is_dataclass(t): return frozenset(f.name for f in fields(t))

  try: return frozenset(t._fields) # type: ignore[attr-defined,unreachable] # NamedTuple.
  except AttributeError: pass

  slots = all_slots(t)
  if slots: return frozenset(slots)
  else: raise TypeError(f'type must be either a dataclass, namedtuple, or define `__slots__`: {type}')


def _hook_type_fn(t:type) -> ObjDecodeFn:
  try: return t.from_json # type: ignore[attr-defined, no-any-return]
  except AttributeError: return t



def format_json_bytes(bytes_or_file: Union[BinaryIO, bytes], out_raw: BinaryIO) -> None:
  file: BinaryIO = bytes_or_file if hasattr(bytes_or_file, 'read') else BytesIO(bytes_or_file) # type: ignore[assignment]

  s_start, s_open, s_close, s_comma, s_colon, s_mid, s_str, s_str_esc = range(8)

  indent = 0
  state = s_start
  is_open_fresh = True
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

    if prev_state == s_colon or (prev_state == s_open and is_open_fresh) or (prev_state not in (s_open, s_close) and state == s_close):
      out_raw.write(b' ')
    elif prev_state == s_open and state != s_close:
      out_raw.write(b'\n')
      out_raw.write(b'  ' * indent)
      is_open_fresh = True

    if prev_state in (s_comma, s_close) and state not in (s_comma, s_close): # Done closing; emit newline.
      out_raw.write(b'\n')
      out_raw.write(b'  ' * indent)
      is_open_fresh = True

    out_raw.write(byte)

    if state == s_open:
      indent += 1
    elif state == s_close:
      indent -= 1
    if state != s_open:
      is_open_fresh = False

  # Final newline for non-empty output.
  if state != s_start:
    out_raw.write(b'\n')

  out_raw.flush()
  if indent != 0:
    print(f'WARNING: unbalanced levels: {indent}', file=stderr)


_ws_re = re.compile(r'[ \t\n\r]*') # identical to json.decoder.WHITESPACE.
