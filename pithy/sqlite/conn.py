# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from sys import stderr
from typing import Any, Callable, Iterable, Literal, Self
from urllib.parse import quote as url_quote

from pithy.url import url_path

from ..meta import caller_src_loc
from ..typing_utils import OptBaseExc, OptTraceback, OptTypeBaseExc
from .cursor import Cursor, SqlParameters
from .row import Row
from .util import sql_quote_entity


IsolationLevel = Literal['DEFERRED', 'EXCLUSIVE', 'IMMEDIATE']

sqlite_version = sqlite3.sqlite_version
sqlite_threadsafe_dbapi_id = sqlite3.threadsafety

sqlite_threadsafe_dbapi_id_descs = [
  '0 - single-thread (threads may not share the module).',
  '1 - multi-thread (threads may share the module, but not connections).',
  '2 - invalid.',
  '3 - serialized (threads may share the module and connections).',
]

sqlite_threadsafe_desc = sqlite_threadsafe_dbapi_id_descs[sqlite_threadsafe_dbapi_id]


BackupProgressFn = Callable[[int,int,int],object]


class Conn(sqlite3.Connection):

  def __init__(self, path:str, timeout:float=5.0, detect_types:int=0, isolation_level:IsolationLevel|None='DEFERRED',
   check_same_thread:bool=True, cached_statements:int=100, uri:bool=False, *, autocommit:bool=True, closing:bool=True,
   mode:str='', trace_caller_level:int=0) -> None:
    '''
    Note: as of Python 3.12, the `autocommit` parameter is preferred over the `isolation_level` parameter.
    sqlite3.Connection `autocommit` defaults to LEGACY_TRANSACTION_CONTROL, in which case `isolation_level` takes effect.
    This subclass defaults to autocommit=True, so by default `isolation_level` is ignored.

    If `closing` is True (the default), the Conn will close itself when used as a context manager.
    This is different from the superclass, which does not close itself on context manager exit.
    '''

    self.path = url_path(path) if uri else path
    self.closing = closing
    self.closed = False
    self.mode = mode
    if mode:
      if uri: raise ValueError('Cannot specify both `uri` and `mode`')
      #^ TODO: this could be relaxed by parsing, validating and updating the URI, taking care to raise in event of a conflict of query parameters.
      path = sqlite_file_uri(path, mode=mode)
      uri = True

    if isolation_level not in (None, 'DEFERRED', 'IMMEDIATE', 'EXCLUSIVE'): raise ValueError(isolation_level)

    super().__init__(path, timeout=timeout, detect_types=detect_types, isolation_level=isolation_level,
      check_same_thread=check_same_thread, cached_statements=cached_statements, uri=uri, autocommit=autocommit)

    self.row_factory = Row # Default for convenience.

    if trace_caller_level:
      self.caller_trace_loc:tuple[str,int,str]|None = caller_src_loc(trace_caller_level)
    else:
      self.caller_trace_loc = None


  def __del__(self) -> None:
    '''
    On deletion, if `self.closing and not self.closed`, print a warning message.
    '''
    if self.closing and not self.closed:
      if self.caller_trace_loc:
        file_path, line_number, fn_name = self.caller_trace_loc
        trace_msg = f'; {file_path}:{line_number}:{fn_name}'
      else:
        trace_msg = ''
      print(f'WARNING: Conn.__del__: connection should have been closed already; id={id(self)}{trace_msg}.', file=stderr)


  def __enter__(self) -> Self:
    '''
    On context manager enter, Conn does nothing.
    '''
    return self


  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> Literal[False]:
    '''
    On context manager exit, Conn.closing == True, it closes itself after performing the superclass commit/rollback behavior.
    In contrast, the superclass `sqlite3.Connection` performs commit/rollback exit, but does not close.
    '''
    res = super().__exit__(exc_type, exc_value, traceback)
    if self.closing: self.close()
    return res


  def attach(self, path:str, *, name:str, mode:str='') -> None:
    '''
    Attach another database to this one using the URI syntax with the specified mode.
    `mode` must be one of '' (default, omitted in the SQL statement), 'ro', 'rw', 'rwc', or 'memory'.
    '''
    uri = sqlite_file_uri(path, mode=mode)
    super().execute(f'ATTACH DATABASE {sql_quote_entity(uri)} AS {sql_quote_entity(name)}')


  def validate(self, query:str) -> None:
    '''
    Validate a query string by calling the undocumented sqlite3 API to compile a statement.
    '''
    super().__call__(query)


  def close(self) -> None:
    '''
    Close the connection. This override sets `self.closed` to True prior to calling `super().close()`.
    '''
    self.closed = True
    super().close()


  def cursor(self, factory:type[Cursor]|None=None) -> Cursor: # type: ignore[override]
    if factory is None: factory = Cursor
    assert issubclass(factory, Cursor)
    return super().cursor(factory)


  def execute(self, query:str, args:SqlParameters=()) -> Cursor:
    '''
    Execute a single SQL statement, optionally binding Python values using placeholders.

    Override execute in order to set `query` on any resulting sqlite3.Error.
    '''
    with self.cursor() as c:
      return c.execute(query, args)


  def executemany(self, query:str, it_args:Iterable[SqlParameters]) -> Cursor:
    '''
    For every item in `it_args`, repeatedly execute the parameterized DML SQL statement sql.

    Override executemany in order to set `query` on any resulting sqlite3.Error.
    '''
    with self.cursor() as c:
      return c.executemany(query, it_args)


  def executescript(self, sql_script:str) -> Cursor:
    '''
    Execute the SQL statements in sql_script. If the autocommit is LEGACY_TRANSACTION_CONTROL and there is a pending transaction, an implicit COMMIT statement is executed first. No other implicit transaction control is performed; any transaction control must be added to sql_script.

    Override executemany in order to set `query` on any resulting sqlite3.Error.
    '''
    with self.cursor() as c:
      return c.executescript(sql_script)


  def backup(self, target:sqlite3.Connection|str|None=None, *, pages:int=-1, progress:BackupProgressFn|bool|None=None,
   name:str='main', sleep:float=0.250) -> None:
    '''
    Backup this database to the target database, optionally printing progress to stdout.
    This is an override of sqlite3.Connection.backup, adding the `progress` argument for convenience.
    '''
    if target is None: target = self.path + '.backup'

    should_close_target = False
    if isinstance(target, str):
      target = sqlite3.connect(target)
      should_close_target = True

    path = getattr(target, 'path', '')

    progress_fn:BackupProgressFn|None = None
    if progress:
      if callable(progress):
        progress_fn = progress
      else:
        def _progress_fn(_status:int, remaining:int, total:int) -> None:
          frac = (total - remaining) / total
          print(f'Backup {path}:{name}: {frac:0.1%}…', end='\r')
        progress_fn = _progress_fn

      print(f'Backup {path}:{name}…', end='\r')

    try:
      super().backup(target, pages=pages, progress=progress_fn, name=name, sleep=sleep)
    finally:
      if should_close_target: target.close()

    if progress: print(f'Backup {path}:{name} complete.')


  def run(self, sql:str, *, _dbg:bool=False, **args:Any) -> Cursor:
    '''
    Execute a query with parameter values provided by keyword arguments.
    Argument values whose types are not sqlite-compatible are automatically converted to JSON.
    '''
    return self.cursor().run(sql, _dbg=_dbg, **args)


def sqlite_file_uri(path:str, *, mode:str='') -> str:
  '''
  Format an SQLite file URI.
  Mode must be one of '' (default, omitted), 'ro', 'rw', 'rwc', or 'memory'.
  TODO: suppport the other documented attributes: https://www.sqlite.org/uri.html.

  '''
  valid_modes = ('', 'ro', 'rw', 'rwc', 'memory')
  if mode not in valid_modes: raise ValueError(mode)
  uri = f'file:{url_quote(path)}'
  if mode:
    uri += f'?mode={mode}'
  return uri
