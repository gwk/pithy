# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import stdout
from typing import Any, BinaryIO, Callable, Dict, List, Tuple

from msgpack import ExtraData, FormatError, OutOfData, StackError, Unpacker, dump as _dump, load as _load  # type: ignore

from .encode import EncodeObj, encode_obj


ObjectHook = Callable[[Dict[str,Any]], Any]
ObjectPairsHook = Callable[[List[Tuple[str,Any]]], Any]
ListHook = Callable[[List[Any]], Any]
ExtHook = Any # TODO

_ml = 2147483647


def load_msgpack(file:BinaryIO, use_list=False, raw=False, strict_map_key=False,
 object_hook:ObjectHook=None, object_pairs_hook:ObjectPairsHook=None, list_hook:ListHook=None,
 encoding:str=None, unicode_errors:str=None, ext_hook:ExtHook=None,
 max_str_len=_ml, max_bin_len=_ml, max_array_len=_ml, max_map_len=_ml, max_ext_len=_ml) -> Any:
  # Omitted: read_size=0, max_buffer_size=0.
  return _load(file, use_list=use_list, raw=raw, strict_map_key=strict_map_key,
    object_hook=object_hook, object_pairs_hook=object_pairs_hook, list_hook=list_hook,
    encoding=encoding, unicode_errors=unicode_errors, ext_hook=ext_hook,
    max_str_len=max_str_len, max_bin_len=max_bin_len, max_array_len=max_array_len,
    max_map_len=max_map_len, max_ext_len=max_ext_len)


def load_msgpacks(file:BinaryIO, use_list=False, raw=False, strict_map_key=False,
 object_hook:ObjectHook=None, object_pairs_hook:ObjectPairsHook=None, list_hook:ListHook=None,
 encoding:str=None, unicode_errors:str=None, ext_hook=None,
 max_str_len=_ml, max_bin_len=_ml, max_array_len=_ml, max_map_len=_ml, max_ext_len=_ml) -> Any:

  return Unpacker(file, use_list=use_list, raw=raw, strict_map_key=strict_map_key,
    object_hook=object_hook, object_pairs_hook=object_pairs_hook, list_hook=list_hook,
    encoding=encoding, unicode_errors=unicode_errors, ext_hook=ext_hook,
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
