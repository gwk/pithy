# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
File open/load dispatch by file extension.
'''

from io import BufferedReader, RawIOBase, TextIOBase, TextIOWrapper
from typing import Any, BinaryIO, Callable, Dict, IO, Iterable, Iterator, Sequence, Set, TextIO, Union

from .io import stderr, errL, errSL
from .fs import path_ext, path_stem

__all__ = [
  'add_loader',
  'FileOrPath',
  'LoaderException',
  'load',
  'LoadFn',
]

FileOrPath = Union[IO, str]
LoadFn = Callable[..., Any]


def load(file_or_path:FileOrPath, ext:str=None, encoding:str=None, **kwargs:Any) -> Any:
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
        raise ValueError(f'load: no `ext` specified and file has non-string `name` attribute: {name!r}') from e
      ext = _path_cmpd_ext(name)
  dispatch_ext = _last_ext(ext)
  try: load_fn = _loaders[dispatch_ext]
  except KeyError as e:
    raise ValueError(f'load: extension {dispatch_ext!r} does not match any available loader: {file_or_path!r}') from e
  try: return load_fn(file_or_path, ext=ext, **kwargs)
  except Exception as e:
    raise LoaderException(f'load failed: {file_or_path!r}') from e


class LoaderException(Exception): pass



def _text_file_for(f:FileOrPath, **kwargs:Any) -> TextIO:
  if isinstance(f, TextIOWrapper): return f
  if isinstance(f, str): return open(f, 'r', **kwargs)
  try: return TextIOWrapper(f, **kwargs)
  except Exception as e:
    raise ValueError(f'load: required text file or path; received {f!r}') from e


def _binary_file_for(f:FileOrPath) -> BinaryIO:
  if isinstance(f, BufferedReader): return f
  if isinstance(f, str): return open(f, 'rb')
  try: return BufferedReader(f) # type: ignore
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


_loaders:Dict[str,LoadFn] = {}
_dflt_loaders:Set[LoadFn] = set()


def load_archive(f:FileOrPath, single_name=None, single_ext=None, **kwargs:Any) -> Any:
  from .archive import Archive
  archive = Archive(_binary_file_for(f))
  if single_name is None and single_ext is None:
    if kwargs:
      raise ValueError('load_archive: `single_name` or `single_ext` not specified; no other options should be set')
    return archive
  # load single file.
  match_exact = (single_name is not None)
  for file in archive: # type: ignore
    if match_exact:
      if file.name != single_name: continue
    else:
      if not file.name.endswith(single_ext): continue
    return load(file, ext=single_ext, **kwargs)
  raise LookupError(f'load_archive: could not find specified {"single_name" if match_exact else "single_ext"} in archive: {single_name!r}; archive.file_names: {archive.file_names}')


def load_binary(f:FileOrPath, ext:str, **kwargs:Any) -> BinaryIO:
  assert not kwargs, kwargs # To allow for opening as bytes or text with any encoding.
  return _binary_file_for(f)


#def load_brotli(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
#  from brotli import decompress
#  with _binary_file_for(f) as f:
#    data = decompress(f.read())
#  sub_ext = _sub_ext(ext)
#  from gzip import GzipFile
#  df = GzipFile(mode='rb', fileobj=_binary_file_for(f))
#  return load(df, ext=sub_ext, **kwargs) # type: ignore


def load_csv(f:FileOrPath, ext:str, encoding:str=None, **kwargs:Any) -> Iterator[Sequence[str]]:
  from .csv import load_csv # type: ignore
  return load_csv(_text_file_for(f, newline='', encoding=encoding), **kwargs)


def load_html(f:FileOrPath, ext:str, encoding:str=None, **kwargs:Any) -> Any:
  from html5_parser import parse

  tf = _binary_file_for(f)
  text = tf.read()
  html = parse(text, transport_encoding=encoding, return_root=True, **kwargs)
  if 'treebuilder' in kwargs: return html

  def transform(obj:Any) -> Any:
    res:Dict = {'': obj.tag}
    res.update(sorted(obj.items()))
    idx = 0
    t = obj.text
    if t:
      t = t.strip()
      if t:
        res[idx] = t
        idx += 1
    for child in obj:
      res[idx] = transform(child)
      idx += 1
      t = child.tail
      if t:
        t = t.strip()
        if t:
          res[idx] = t
          idx += 1
    return res

  return transform(html)



def load_gz(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  sub_ext = _sub_ext(ext)
  if sub_ext.endswith('.tar'): # load_archive handles compressed tar stream faster.
    return load_archive(f, **kwargs)
  from gzip import GzipFile
  df = GzipFile(mode='rb', fileobj=_binary_file_for(f))
  return load(df, ext=sub_ext, **kwargs) # type: ignore


def load_json(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .json import load_json # type: ignore
  return load_json(_text_file_for(file_or_path), **kwargs)

def load_jsonl(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .json import load_jsonl # type: ignore
  return load_jsonl(_text_file_for(file_or_path), **kwargs)

def load_jsons(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .json import load_jsons # type: ignore
  return load_jsons(_text_file_for(file_or_path), **kwargs)


def load_msgpack(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .msgpack import load_msgpack as _load_msgpack
  return _load_msgpack(_binary_file_for(file_or_path), **kwargs)


def load_msgpacks(file_or_path:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .msgpack import load_msgpacks as _load_msgpacks
  return _load_msgpacks(_binary_file_for(file_or_path), **kwargs)


def load_pyl(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  'Load a python literal AST file (Python equivalent of JSON).'
  from ast import literal_eval
  return literal_eval(_text_file_for(f, **kwargs).read())


def load_sqlite(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from .sqlite import Connection
  if not isinstance(f, str):
    raise ValueError(f'load: sqlite files can only be opened with a string path; received {f!r}')
  return Connection(f'file:{path}?mode=ro', uri=True, **kwargs) # type: ignore # Open in read-only mode.


def load_txt(f:FileOrPath, ext:str, clip_ends=False, **kwargs:Any) -> Iterable[str]:
  f = _text_file_for(f, **kwargs)
  if clip_ends: return (line.rstrip('\n\r') for line in f)
  return f


def load_xls(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from xlrd import open_workbook # type: ignore
  if isinstance(f, str):
    return open_workbook(filename=f, logfile=stderr, **kwargs)
  # Unfortunately load_xls will not take an open file handle.
  # Since we might be passing in an in-memory file like ArchiveFile,
  # the best we can do for now is read file contents into memory.
  # Alternative would be to make ArchiveFile conform to mmap protocol
  # (xrld supports passing in mmap objects),
  # or patch xlrd to support passing in an open binary file descriptor.
  return open_workbook(filename=None, logfile=stderr, file_contents=_binary_file_for(f).read(), **kwargs)


def load_xz(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  sub_ext = _sub_ext(ext)
  if sub_ext.endswith('.tar'): # load_archive handles compressed stream faster.
    # TODO: investigate whether a multithreaded subprocess and/or pipeline between two processes could be faster.
    return load_archive(f, **kwargs)
  from lzma import LZMAFile
  d = LZMAFile(_binary_file_for(f))
  #b = BufferedReader(d) # type: ignore
  return load(d, ext=sub_ext, **kwargs)


def load_zst(f:FileOrPath, ext:str, **kwargs:Any) -> Any:
  from zstandard import ZstdDecompressor # type: ignore
  decompressor = ZstdDecompressor()
  d = decompressor.stream_reader(_binary_file_for(f))
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
add_loader('.pyl',      load_pyl,       _dflt=True)
add_loader('.sqlite',   load_sqlite,    _dflt=True)
add_loader('.sqlite3',  load_sqlite,    _dflt=True)
add_loader('.tar',      load_archive,   _dflt=True)
add_loader('.txt',      load_txt,       _dflt=True)
add_loader('.xls',      load_xls,       _dflt=True)
add_loader('.xz',       load_xz,        _dflt=True)
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
