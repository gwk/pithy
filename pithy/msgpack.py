# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import stdout
from typing import Any, BinaryIO, Callable

from msgpack import dump as _dump, ExtraData, ExtType, FormatError, load as _load, OutOfData, StackError, Unpacker

from .encode import encode_obj, EncodeObj


_convenience_exports = (ExtraData, FormatError, StackError)


ObjectHook = Callable[[dict[str,Any]], Any]
ObjectPairsHook = Callable[[list[tuple[str,Any]]], Any]
ListHook = Callable[[list[Any]], Any]
ExtHook = Callable[[int,bytes], Any] # Arguments are integer code [0-127], bytes data.

_ml = 2147483647


def load_msgpack(file:BinaryIO, use_list=False, raw=False, strict_map_key=False,
 object_hook:ObjectHook|None=None, object_pairs_hook:ObjectPairsHook|None=None, list_hook:ListHook|None=None,
 unicode_errors:str|None=None, ext_hook:ExtHook=ExtType,
 max_str_len=_ml, max_bin_len=_ml, max_array_len=_ml, max_map_len=_ml, max_ext_len=_ml) -> Any:
  # Omitted: read_size=0, max_buffer_size=0.
  return _load(file, use_list=use_list, raw=raw, strict_map_key=strict_map_key,
    object_hook=object_hook, object_pairs_hook=object_pairs_hook, list_hook=list_hook,
    unicode_errors=unicode_errors, ext_hook=ext_hook,
    max_str_len=max_str_len, max_bin_len=max_bin_len, max_array_len=max_array_len,
    max_map_len=max_map_len, max_ext_len=max_ext_len)


def load_msgpacks(file:BinaryIO, use_list=False, raw=False, strict_map_key=False,
 object_hook:ObjectHook|None=None, object_pairs_hook:ObjectPairsHook|None=None, list_hook:ListHook|None=None,
 unicode_errors:str|None=None, ext_hook=ExtType,
 max_str_len=_ml, max_bin_len=_ml, max_array_len=_ml, max_map_len=_ml, max_ext_len=_ml) -> Any:

  return Unpacker(file, use_list=use_list, raw=raw, strict_map_key=strict_map_key,
    object_hook=object_hook, object_pairs_hook=object_pairs_hook, list_hook=list_hook,
    unicode_errors=unicode_errors, ext_hook=ext_hook,
    max_str_len=max_str_len, max_bin_len=max_bin_len, max_array_len=max_array_len,
    max_map_len=max_map_len, max_ext_len=max_ext_len)


def count_msgpacks(file:BinaryIO) -> int:
  unpacker = Unpacker(file)
  i = 0
  while True:
    try: unpacker.skip()
    except OutOfData: return i
    i += 1


def write_msgpack(file:BinaryIO, obj:Any, default:EncodeObj=encode_obj, unicode_errors='strict',
 use_single_float=False, autoreset=False, use_bin_type=True, strict_types=False) -> None:

  _dump(obj, file, default=encode_obj, unicode_errors=unicode_errors,
    use_single_float=use_single_float, use_bin_type=use_bin_type, strict_types=strict_types)


def out_msgpack(obj:Any, default:EncodeObj=encode_obj, unicode_errors='strict',
 use_single_float=False, autoreset=False, use_bin_type=True, strict_types=False) -> None:

  _dump(obj, stdout.buffer, default=encode_obj, unicode_errors=unicode_errors,
    use_single_float=use_single_float, use_bin_type=use_bin_type, strict_types=strict_types)
