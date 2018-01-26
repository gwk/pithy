# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
File open/load dispatch by file extension.
'''

from io import TextIOWrapper
from typing import *
from typing import IO, TextIO, BinaryIO

from .io import stderr, errL, errSL
from .fs import path_ext, path_stem


LoadFn = Callable[..., Any]


def load(file_or_path: Any, ext:str=None, **kwargs) -> Any:
  '''
  Select an appropriate loader based on the file extension, or `ext` if specified.

  If no loader is found, raise an error.

  If a loader is found, then `open` is called with the `open_args` registered by `add_loader`,
  except updated by any values in `kwargs` whose keys match the loader `open_keys`.
  The remaining `kwargs` are passed to the loader function.
  '''
  is_file = hasattr(file_or_path, 'read')
  if is_file:
    if ext is None:
      try: path = file_or_path.name
      except AttributeError as e:
        raise ValueError(f'load: file object does not have `name` attribute and no `ext` specified: {file_or_path}') from e
      ext = path_ext(path)
  else:
    path = file_or_path
    if ext is None:
      ext = path_ext(path)

  loader = _loaders[ext]

  # Construct args for `open`.
  open_args = dict(loader.open_args)
  for k in tuple(open_args):
    try: v = kwargs[k]
    except KeyError: pass
    else: # this arg is meant for `open`, not `load`.
      open_args[k] = v
      del kwargs[k] # Safe to delete because kwargs is local.

  if is_file:
    file = file_or_path
    if open_args['encoding'] is not None and not hasattr(file, 'encoding'): # want text but have binary file.
      del open_args['buffering'] # TextIOWrapper does not support this argument.
      file = TextIOWrapper(file, **open_args)
  else:
    file = open(file_or_path, **open_args)

  return loader.fn(file, **kwargs)


def add_loader(ext: str, _fn: LoadFn, buffering=-1, encoding='UTF-8', errors=None, newline=None, _dflt=False) -> None:
  '''
  Register a loader function, which will be called by `muck.load` for matching `ext`.
  `buffering`, `encoding`, `errors`, and `newline` are all passed on to `open` when it is called by `load`.
  `_dflt` is used to mark the default loaders as such so that they can be overridden without triggering an error.
  '''
  if not ext.startswith('.'):
    raise ValueError(f"file extension does not start with '.': {ext!r}")
  if not _dflt:
    try: prev_loader = _loaders[ext]
    except KeyError: pass
    else: raise Exception(f'add_loader: extension previously registered: {ext!r}; loader: {prev_loader!r}')
  _loaders[ext] = Loader(ext=ext, fn=_fn, open_args=(
    ('buffering', buffering), ('encoding', encoding), ('errors', errors), ('newline', newline)))


class Loader(NamedTuple):
  ext: str
  fn: LoadFn
  open_args: Tuple[Tuple[str, Any], ...]


_loaders: Dict[str, Loader] = {}


def load_archive(f: BinaryIO, single_name=None, single_ext=None, **kwargs:Any) -> Any:
  from .archive import Archive
  archive = Archive(f)
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


def load_csv(file: IO, **kwargs) -> Iterator[Sequence[str]]:
  from .csv import load_csv # type: ignore
  return load_csv(file, **kwargs)


def load_gz(f: BinaryIO, sub_ext=None, **kwargs:Any) -> Any:
  stem = path_stem(f.name)
  if sub_ext is None:
    sub_ext = path_ext(stem)
  if sub_ext == '.tar': # load_archive handles compressed stream faster.
    return load_archive(f, **kwargs)
  from gzip import GzipFile
  df = GzipFile(mode='rb', fileobj=f)
  df.name = stem # strip off '.gz' for secondary dispatch by `load`.
  return load(df, ext=sub_ext, **kwargs)


def load_json(file: IO, **kwargs) -> Any:
  from .json import load_json # type: ignore
  return load_json(cast(TextIO, file), **kwargs)

def load_jsonl(file: IO, **kwargs) -> Any:
  from .json import load_jsonl # type: ignore
  return load_jsonl(cast(TextIO, file), **kwargs)

def load_jsons(file: IO, **kwargs) -> Any:
  from .json import load_jsons # type: ignore
  return load_jsons(cast(TextIO, file), **kwargs)


def load_pyl(file: IO, **kwargs) -> Any:
  'Load a python literal AST file (Python equivalent of JSON).'
  from ast import literal_eval
  return literal_eval(file.read())


def load_txt(f: TextIO, clip_ends=False) -> Iterable[str]:
  if clip_ends: return (line.rstrip('\n\r') for line in f)
  return f


def load_xls(file: BinaryIO) -> Any:
  from xlrd import open_workbook # type: ignore
  # Unfortunately load_xls will not take an open file handle.
  # Since we might be passing in an in-memory file like ArchiveFile,
  # the best we can do for now is always read file contents into memory.
  # Alternative would be to make ArchiveFile conform to mmap protocol
  # (xrld supports passing in mmap objects),
  # or patch xlrd to support passing in an open binary file descriptor.
  return open_workbook(filename=None, logfile=stderr, file_contents=file.read())


add_loader('.css',    load_txt,     _dflt=True)
add_loader('.csv',    load_csv,     _dflt=True, newline='') # newline specified as per footnote in csv module.
add_loader('.gz',     load_gz,      _dflt=True, encoding=None)
add_loader('.json',   load_json,    _dflt=True)
add_loader('.jsonl',  load_jsonl,   _dflt=True)
add_loader('.jsons',  load_jsons,   _dflt=True)
add_loader('.pyl',    load_pyl,    _dflt=True)
add_loader('.tar',    load_archive, _dflt=True, encoding=None)
add_loader('.txt',    load_txt,     _dflt=True)
add_loader('.xls',    load_xls,     _dflt=True, encoding=None)
add_loader('.zip',    load_archive, _dflt=True, encoding=None)

