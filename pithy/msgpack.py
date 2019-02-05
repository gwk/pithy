# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from msgpack import dump, load # type: ignore
from sys import stdout
from typing import Any, BinaryIO, Callable, Dict, List, Tuple

DefaultFn = Callable[[Any], Any]

ObjectHook = Callable[[Dict[str,Any]], Any]
ObjectPairsHook = Callable[[List[Tuple[str,Any]]], Any]
ListHook = Callable[[List[Any]], Any]


def load_msgpack(file:BinaryIO, use_list=True, raw=False,
 object_hook:ObjectHook=None, object_pairs_hook:ObjectPairsHook=None, list_hook:ListHook=None,
 encoding:str=None, unicode_errors:str=None, ext_hook=None,
 max_str_len=2147483647, max_bin_len=2147483647, max_array_len=2147483647,
 max_map_len=2147483647, max_ext_len=2147483647):
  # read_size=0,
  # max_buffer_size=0,
  return load(file, use_list=use_list, raw=raw,
    object_hook=object_hook, object_pairs_hook=object_pairs_hook, list_hook=list_hook,
    encoding=encoding, unicode_errors=unicode_errors, ext_hook=ext_hook,
    max_str_len=max_str_len, max_bin_len=max_bin_len, max_array_len=max_array_len,
    max_map_len=max_map_len, max_ext_len=max_ext_len)


def write_msgpack(file:BinaryIO, obj:Any, default:DefaultFn=None, unicode_errors='strict',
 use_single_float=False, autoreset=False, use_bin_type=True, strict_types=False) -> None:

  dump(obj, file, default=default, unicode_errors=unicode_errors,
    use_single_float=use_single_float, use_bin_type=use_bin_type, strict_types=strict_types)


def out_msgpack(obj:Any, default:DefaultFn=None, unicode_errors='strict',
 use_single_float=False, autoreset=False, use_bin_type=True, strict_types=False) -> None:

  write_msgpack(stdout.buffer, obj, default=default, unicode_errors=unicode_errors,
    use_single_float=use_single_float, use_bin_type=use_bin_type, strict_types=strict_types)
