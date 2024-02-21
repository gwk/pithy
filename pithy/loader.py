# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
File open/load dispatch by file extension.
'''

from io import BufferedReader, TextIOWrapper
from typing import Any, BinaryIO, Callable, cast, IO, Iterable, TextIO, TypeAlias


__all__ = [
  'add_loader',
  'FileOrPath',
  'LoaderException',
  'load',
  'LoadFn',
]

FileOrPath:TypeAlias = IO|str
LoadFn:TypeAlias = Callable[..., Any]


def load(file_or_path:FileOrPath, ext:str|None=None, **kwargs:Any) -> Any:
  '''
  Select an appropriate loader based on the file extension, or `ext` if specified.

  If a loader is found, then it is called, passing `kwargs`.

  If no loader is found, raises KeyError.
  '''
  if ext is None:
    if isinstance(file_or_path, str):
      ext = _path_cmpd_ext(file_or_path)
    else:
      try: name = file_or_path.name
      except AttributeError as e:
        raise ValueError(f'load: no `ext` specified and file does not have `name` attribute: {file_or_path}') from e
      if not isinstance(name, str):
        raise ValueError(f'load: no `ext` specified and file has non-string `name` attribute: {name!r}')
      ext = _path_cmpd_ext(name)
  dispatch_ext = _last_ext(ext)
  try: load_fn = _loaders[dispatch_ext]
  except KeyError as e:
    raise ValueError(f'load: extension {dispatch_ext!r} does not match any available loader: {file_or_path!r}') from e
  try: return load_fn(file_or_path, ext=ext, **kwargs)
  except Exception as e:
    raise LoaderException(f'load failed: {file_or_path!r}') from e


class LoaderException(Exception): pass



def text_file_for(f:FileOrPath, **kwargs:Any) -> TextIO:
  if isinstance(f, TextIOWrapper): return f
  if isinstance(f, str): return cast(TextIO, open(f, 'r', **kwargs))
  try: return TextIOWrapper(f, **kwargs)
  except Exception as e:
    raise ValueError(f'load: required text file or path; received {f!r}') from e


def binary_file_for(f:FileOrPath) -> BinaryIO:
  if isinstance(f, BufferedReader): return f
  #^ Not sure about the reachability error above. Has to do with the relationship between abstract IO and concrete BufferedReader.
  if isinstance(f, str): return open(f, 'rb')
  try: return BufferedReader(f) # type: ignore[arg-type]
  except Exception as e:
    raise ValueError(f'load: required binary file or path; received {f!r}') from e


def add_loader(ext:str, fn:LoadFn, _dflt=False) -> None:
  '''
  Register a loader function, which will be called by `load` for matching `ext`.
  `_dflt` is used to mark the default loaders as such so that they can be overridden without triggering an error.
  '''
  if ext and not ext.startswith('.'):
    raise ValueError(f"file extension does not start with '.': {ext!r}")
  try: prev_loader = _loaders[ext]
  except KeyError: pass
  else:
    if prev_loader not in _dflt_loaders:
      raise Exception(f'add_loader: extension previously registered: {ext!r}; loader: {prev_loader!r}')
  _loaders[ext] = fn
  if _dflt:
    _dflt_loaders.add(fn)


_loaders:dict[str,LoadFn] = {}
_dflt_loaders:set[LoadFn] = set()


def load_archive(f:FileOrPath, single_name=None, single_ext=None, **kwargs:Any) -> Any:
  from .archive import Archive
  archive = Archive(binary_file_for(f))
  if single_name is None and single_ext is None:
    if kwargs:
      raise ValueError('load_archive: `single_name` or `single_ext` not specified; no other options should be set')
    return archive
  # load single file.
  match_exact = (single_name is not None)
  for file in archive: # type: ignore[attr-defined]
    if match_exact:
      if file.name != single_name: continue
    else:
      if not file.name.endswith(single_ext): continue
    return load(file, ext=single_ext, **kwargs)
  raise LookupError(f'load_archive: could not find specified {"single_name" if match_exact else "single_ext"} in archive: {single_name!r}; archive.file_names: {archive.file_names}')


def load_binary(f:FileOrPath, ext:str, **kwargs:Any) -> BinaryIO:
  assert not kwargs, kwargs # To allow for opening as bytes or text with any encoding.
  return binary_file_for(f)


#def load_brotli(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
#  from brotli import decompress
#  with binary_file_for(f) as f:
#    data = decompress(f.read())
#  sub_ext = _sub_ext(ext)
#  from gzip import GzipFile
#  df = GzipFile(mode='rb', fileobj=binary_file_for(f))
#  return load(df, ext=sub_ext, **kwargs) # type: ignore


def load_csv(f:FileOrPath, ext:str, encoding:str|None=None, **kwargs:Any) -> Iterable[list[str]]:
  from .csv import load_csv as _load_csv
  return _load_csv(text_file_for(f, newline='', encoding=encoding), **kwargs)


def load_html(f:FileOrPath, ext:str, encoding:str='utf8', **kwargs:Any) -> Any:
  from .html.loader import load_html as _load_html
  bf = binary_file_for(f)
  return _load_html(bf, encoding=encoding, **kwargs)


def load_gz(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  sub_ext = _sub_ext(ext)
  if sub_ext.endswith('.tar'): # load_archive handles compressed tar stream faster.
    return load_archive(f, **kwargs)
  from gzip import GzipFile
  df = GzipFile(mode='rb', fileobj=binary_file_for(f))
  return load(df, ext=sub_ext, **kwargs) # type: ignore[arg-type]


def load_json(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .json import load_json as _load_json
  return _load_json(text_file_for(file_or_path), **kwargs)

def load_jsonl(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .json import load_jsonl as _load_jsonl
  return _load_jsonl(text_file_for(file_or_path), **kwargs)

def load_jsons(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .json import load_jsons as _load_jsons
  return _load_jsons(text_file_for(file_or_path), **kwargs)


def load_msgpack(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .msgpack import load_msgpack as _load_msgpack
  return _load_msgpack(binary_file_for(file_or_path), **kwargs)


def load_msgpacks(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .msgpack import load_msgpacks as _load_msgpacks
  return _load_msgpacks(binary_file_for(file_or_path), **kwargs)


def load_pickle(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .pickle import load_pickle as _load_pickle
  return _load_pickle(binary_file_for(file_or_path), **kwargs)


def load_plist(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from plistlib import load as _load_plist
  return _load_plist(binary_file_for(file_or_path), **kwargs)


def load_pyl(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  'Load a python literal AST file (Python equivalent of JSON).'
  from ast import literal_eval
  return literal_eval(text_file_for(f, **kwargs).read())


def load_sqlite(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .sqlite import Connection
  if not isinstance(f, str):
    raise ValueError(f'load: sqlite files can only be opened with a string path; received {f!r}')
  return Connection(f, mode='ro', **kwargs)


def load_txt(f:FileOrPath, ext:str, clip_ends=False, **kwargs:Any) -> Iterable[str]:
  f = text_file_for(f, **kwargs)
  if clip_ends: return (line.rstrip('\n\r') for line in f)
  return f


def load_xls(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from openpyxl import load_workbook  # type: ignore[import-untyped]
  if isinstance(f, str):
    return load_workbook(filename=f, **kwargs)
  else:
    raise Exception(f'load_xls cannot load from an already open file handle: {f}')


def load_xz(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  sub_ext = _sub_ext(ext)
  if sub_ext.endswith('.tar'): # load_archive handles compressed stream faster.
    # TODO: investigate whether a multithreaded subprocess and/or pipeline between two processes could be faster.
    return load_archive(f, **kwargs)
  from lzma import LZMAFile
  d = LZMAFile(binary_file_for(f))
  #b = BufferedReader(d) # type: ignore[import]
  return load(d, ext=sub_ext, **kwargs)


def load_yaml(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from yaml import load as _load_yaml, SafeLoader
  loader = kwargs.pop('Loader', SafeLoader)
  return _load_yaml(binary_file_for(f), Loader=loader, **kwargs)


def load_zst(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from zstandard import ZstdDecompressor
  decompressor = ZstdDecompressor()
  d = decompressor.stream_reader(binary_file_for(f))
  return load(d, ext=_sub_ext(ext), **kwargs)


add_loader('',          load_binary,    _dflt=True)
add_loader('.css',      load_txt,       _dflt=True)
add_loader('.csv',      load_csv,       _dflt=True)
add_loader('.gz',       load_gz,        _dflt=True)
add_loader('.html',     load_html,      _dflt=True)
add_loader('.json',     load_json,      _dflt=True)
add_loader('.jsonl',    load_jsonl,     _dflt=True)
add_loader('.jsons',    load_jsons,     _dflt=True)
add_loader('.msgpack',  load_msgpack,   _dflt=True)
add_loader('.msgpacks', load_msgpacks,  _dflt=True)
add_loader('.p',        load_pickle,    _dflt=True)
add_loader('.pickle',   load_pickle,    _dflt=True)
add_loader('.plist',    load_plist,     _dflt=True)
add_loader('.pyl',      load_pyl,       _dflt=True)
add_loader('.sqlite',   load_sqlite,    _dflt=True)
add_loader('.sqlite3',  load_sqlite,    _dflt=True)
add_loader('.tar',      load_archive,   _dflt=True)
add_loader('.txt',      load_txt,       _dflt=True)
add_loader('.xls',      load_xls,       _dflt=True)
add_loader('.xlsx',     load_xls,       _dflt=True)
add_loader('.xz',       load_xz,        _dflt=True)
add_loader('.yaml',     load_yaml,      _dflt=True)
add_loader('.zip',      load_archive,   _dflt=True)
add_loader('.zst',      load_zst,       _dflt=True)


# Compound path utilities.

def _path_cmpd_ext(path:str) -> str:
  start = 1 if path.startswith('.') else 0 # Account for hidden files.
  try: idx = path.index('.', start)
  except ValueError: return ''
  else: return path[idx:]


def _last_ext(cmpd_ext:str) -> str:
  try: idx = cmpd_ext.rindex('.')
  except ValueError: return cmpd_ext
  else: return cmpd_ext[idx:]


def _sub_ext(cmpd_ext:str) -> str:
  try: idx = cmpd_ext.rindex('.')
  except ValueError: return cmpd_ext
  else: return cmpd_ext[:idx]


def main() -> None:
  from sys import argv

  from .io import outD
  from .parse import ParseError

  args = argv[1:] or ['/dev/stdin']
  for path in args:
    try: obj = load(path)
    except ParseError as e: e.fail()
    outD(path, obj)


if __name__ == '__main__': main()
