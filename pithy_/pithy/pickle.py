# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from pickle import dump as _dump, HIGHEST_PROTOCOL, load as _load
from sys import stdout
from typing import Any, BinaryIO


def load_pickle(file:BinaryIO, *, fix_imports:bool=True, encoding:str="ASCII", errors:str="strict") -> Any:
  return _load(file, fix_imports=fix_imports, encoding=encoding, errors=errors)


def write_pickle(file:BinaryIO, obj:Any, protocol:int=HIGHEST_PROTOCOL, fix_imports:bool=True) -> None:
  _dump(obj, file, protocol=protocol, fix_imports=fix_imports)


def out_pickle(obj:Any, protocol:int=HIGHEST_PROTOCOL, fix_imports:bool=True) -> None:
  _dump(obj, stdout.buffer, protocol=protocol, fix_imports=fix_imports)
