# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import contextlib
import sqlite3
from random import random
from sqlite3 import OperationalError, ProgrammingError, SQLITE_BUSY
from sys import stderr
from time import monotonic as get_time, sleep
from typing import Any, Callable, Iterable, Literal, Self
from urllib.parse import quote as url_quote

from ..logs import logW
from ..meta import caller_src_loc
from ..path import path_name
from ..typing_utils import OptBaseExc, OptTraceback, OptTypeBaseExc
from .cursor import Cursor, SqlParameters
from .row import Row
from .util import sql_quote_entity


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

type Mode = Literal['ro','rw','rwc','memory']


class Conn(sqlite3.Connection):

  transaction_start:float = 0
  transaction_time:float = 0
  transaction_pre_rollback_time:float = 0

  retry_base_sec:float = 0.001
  retry_max_sec:float = 0.050

  retry_count:int = 0
  last_retry_error_code:int|None = None


  def __init__(self, path:str, *, mode:Mode, timeout:float=5.0, detect_types:int=0,
   check_same_thread:bool=True, cached_statements:int=100, immutable:bool=False, modeof:str='', psow:bool|None=None, vfs:str='',
   trace_caller_level:int=0) -> None:
    '''
    This subclass always uses `autocommit=True`.

    Using a Conn as a context manager runs an explicit transaction: `__enter__` issues a BEGIN
    (BEGIN IMMEDIATE for read-write connections, to acquire the write lock up front under WAL), and `__exit__`
    issues COMMIT, or ROLLBACK if an exception propagated. The same Conn can be used as a context manager
    repeatedly to run successive transactions.

    The connection is not closed on context manager exit. To guarantee closing, use `Conn.closing`,
    e.g. `with Conn(path).closing() as conn: ...`, or equivalently wrap the Conn in `contextlib.closing`.
    If a Conn is garbage-collected without having been closed, `__del__` logs a warning; pass a nonzero
    `trace_caller_level` to record the construction site for inclusion in that warning.

    URI parameters (https://www.sqlite.org/uri.html):
    - `immutable`: assert that the file is on read-only media; skips locking and change detection.
    - `modeof`: (Unix) set new file permissions to match the specified existing file path.
    - `psow`: override the power-safe overwrite property (True/False).
    - `vfs`: name of the VFS to use.
    The `cache` URI parameter is not exposed (SQLite shared cache is deprecated).
    The `nolock` URI parameter is not exposed (disabling locking risks database corruption).
    '''
    # Set all the attributes used in __del__ first to prevent AttributeErrors on early failures in __init__.
    self.closed = True
    self.caller_trace_loc = None

    if trace_caller_level:
      self.caller_trace_loc:tuple[str,int,str]|None = caller_src_loc(trace_caller_level) # type: ignore[no-redef]

    self.mode = mode
    self.timeout = timeout
    self.path = path
    uri = sqlite_file_uri(path, mode=mode, immutable=immutable, modeof=modeof, psow=psow, vfs=vfs)

    try:
      super().__init__(uri, timeout=timeout, detect_types=detect_types, check_same_thread=check_same_thread,
        cached_statements=cached_statements, uri=True, autocommit=True)
    except Exception as e:
      e.add_note(f'path: {path!r}.')
      raise

    self.closed = False

    self.row_factory = Row # Default for convenience.


  def __del__(self) -> None:
    '''
    On deletion, if the connection was never closed, log a warning.
    '''
    if not self.closed:
      if self.caller_trace_loc:
        file_path, line_number, fn_name = self.caller_trace_loc
        trace_loc = f'{file_path}:{line_number}:{fn_name}'
      else:
        trace_loc = ''
      logW('Conn.__del__: connection should have been closed already.', trace_loc=trace_loc)


  def __enter__(self) -> Self:
    '''
    On context manager enter, begin an explicit transaction.
    Read-only connections use BEGIN (DEFERRED).
    Read-write connections use BEGIN IMMEDIATE with retry on the SQLITE_BUSY family.
    '''
    if self.in_transaction: raise ProgrammingError('Conn.__enter__: a transaction is already active.')
    self.transaction_start = get_time()
    self.transaction_time = 0
    self.transaction_pre_rollback_time = 0
    if self.mode != 'ro':
      self._begin_immediate()
    else:
      self.execute_control('BEGIN')
    return self


  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> Literal[False]:
    '''
    On context manager exit, commit the transaction, or roll back if an exception propagated.
    The exit is guarded by `in_transaction` so a failed BEGIN (no active transaction) does not issue a spurious ROLLBACK.
    The connection is not closed; use `Conn.closing()` to guarantee closing.
    '''
    if self.in_transaction:
      if exc_type: # Exception raised.
        self.transaction_pre_rollback_time = get_time() - self.transaction_start
        self.execute_control('ROLLBACK')
      else:
        self.execute_control('COMMIT')
    self.transaction_time = get_time() - self.transaction_start
    if exc_value is not None:
      setattr(exc_value, 'transaction_time', self.transaction_time)
      exc_value.add_note(
        f'transaction_time: {self.transaction_time:.5f}s; pre_rollback_time: {self.transaction_pre_rollback_time:.5f}s.')
    return False


  def _begin_immediate(self) -> None:
    '''
    Issue BEGIN IMMEDIATE to acquire the write lock, retrying on any SQLITE_BUSY family errors.

    Under WAL, BEGIN IMMEDIATE internally takes a read snapshot then upgrades it to the write lock.
    If another connection commits a write between those two steps, the snapshot is already stale and SQLite raises
    SQLITE_BUSY_SNAPSHOT without invoking the busy handler; busy_timeout cannot help, so the only correct response is to retry
    the failed BEGIN, which takes a fresh snapshot.
    A write lock held by another writer can also cause a true timeout, resulting in SQLITE_BUSY or another subcode.
    Regardless of subcode, we retry with exponential backoff and full jitter until we exceed `self.timeout`.
    Retrying only the BEGIN is sufficient and safe for the context-manager protocol:
    once it succeeds this connection holds the write lock, so no further snapshot conflict can arise.
    '''
    deadline = get_time() + self.timeout
    attempt = 0
    self.retry_count = 0
    self.last_retry_error_code = None
    while True:
      try:
        self.execute_control('BEGIN IMMEDIATE')
        return
      except OperationalError as e:
        if not _is_busy(e): raise
        self.last_retry_error_code = getattr(e, 'sqlite_errorcode', None)
        remaining = deadline - get_time()
        if remaining <= 0:
          e.add_note(
            f'BEGIN IMMEDIATE failed after {self.retry_count} retries; '
            f'last sqlite_errorcode: {self.last_retry_error_code}; retry budget of {self.timeout:.5f}s exhausted.')
          raise
        backoff_ceiling = _backoff_ceiling(self.retry_max_sec, self.retry_base_sec, attempt)
        backoff_sec = min(remaining, backoff_ceiling * random())
        sleep(backoff_sec)
        attempt += 1
        self.retry_count += 1


  def attach(self, path:str, *, name:str, mode:Mode,
   immutable:bool=False, modeof:str='', psow:bool|None=None, vfs:str='') -> None:
    'Attach another database to this one using the URI syntax.'
    uri = sqlite_file_uri(path, mode=mode, immutable=immutable, modeof=modeof, psow=psow, vfs=vfs)
    self.execute_control(f'ATTACH DATABASE {sql_quote_entity(uri)} AS {sql_quote_entity(name)}')


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


  def closing(self) -> contextlib.closing[Self]:
    '''
    Return a context manager that closes this connection on exit, as a convenience for `contextlib.closing(self)`.
    This only closes the connection; it does not run a transaction. Nest `with conn:` inside to run a transaction.
    '''
    return contextlib.closing(self)


  def commit(self) -> None:
    '''
    Unsupported: this Conn always runs in sqlite autocommit mode, where Connection.commit() is a silent
    no-op. Use the Conn as a context manager to run an explicit transaction, or issue COMMIT directly via
    `execute_control('COMMIT')`.
    '''
    raise ProgrammingError(
      'Conn.commit() is unsupported in autocommit mode; use the Conn as a context manager or execute_control("COMMIT").')


  def rollback(self) -> None:
    '''
    Unsupported: this Conn always runs in sqlite autocommit mode, where Connection.rollback() is a silent
    no-op. Use the Conn as a context manager to roll back on exception, or issue ROLLBACK directly via
    `execute_control('ROLLBACK')`.
    '''
    raise ProgrammingError(
      'Conn.rollback() is unsupported in autocommit mode; use the Conn as a context manager or execute_control("ROLLBACK").')


  def cursor(self, factory:type[Cursor]|None=None) -> Cursor: # type: ignore[override]
    if factory is None: factory = Cursor
    assert issubclass(factory, Cursor)
    return super().cursor(factory)


  def execute_control(self, query:str, args:SqlParameters=()) -> None:
    '''
    Execute a control or DML statement whose result rows are not needed, closing the cursor immediately.
    Closing in a `finally` finalizes the underlying SQLite statement deterministically, even if the cursor would
    otherwise be kept alive by an exception traceback retaining the frame. Used for BEGIN/COMMIT/ROLLBACK and ATTACH.
    '''
    c = self.cursor()
    try:
      c.execute(query, args)
    finally:
      c.close()


  def execute(self, query:str, args:SqlParameters=()) -> Cursor:
    '''
    Execute a single SQL statement, optionally binding Python values using placeholders.

    Create a fresh cursor and return it open, like sqlite3.Connection.execute.
    The Cursor override sets `query` and `execute_time` on any resulting sqlite3.Error.
    The caller is responsible for closing the returned cursor;
    for statements with no result rows, use `execute_control` instead.
    '''
    return self.cursor().execute(query, args)


  def executemany(self, query:str, it_args:Iterable[SqlParameters]) -> Cursor:
    '''
    For every item in `it_args`, repeatedly execute the parameterized DML SQL statement sql.

    Create a fresh cursor and return it open, like sqlite3.Connection.executemany.
    The Cursor override sets `query` and `execute_time` on any resulting sqlite3.Error.
    '''
    return self.cursor().executemany(query, it_args)


  def executescript(self, sql_script:str) -> Cursor:
    '''
    Execute the SQL statements in sql_script.
    Since this Conn always uses autocommit=True, no implicit transaction control is performed;
    any transaction control must be added to sql_script.

    Create a fresh cursor and return it open, like sqlite3.Connection.executescript.
    The Cursor override sets `script` and `execute_time` on any resulting sqlite3.Error.
    '''
    return self.cursor().executescript(sql_script)


  def backup(self, target:sqlite3.Connection|str|None=None, *, pages:int=-1, progress:BackupProgressFn|bool|None=None,
   name:str='main', sleep:float=0.25) -> None:
    '''
    Back up this database to the `target` (backup destination) database, optionally printing progress to stdout.
    If `target` is a string:
      * if `target` ends with '/', it is interpreted as the backup destination directory, and the name of `self.path` is used.
      * a new Connection will be opened to that path and closed after the backup.
    If `target` is an existing Connection, it will not be closed after the backup.
    If `target` is None, a backup will be made to a file at `self.path + '.backup'`.

    This is an override of sqlite3.Connection.backup. It adds handling of `target:str` and the default progress function.
    '''

    if target is None: target = self.path + '.backup'

    should_close_target = False
    target_path:str|None
    if isinstance(target, str):
      should_close_target = True
      target_path = target
      if target.endswith('/'):
        src_name = path_name(self.path)
        if not src_name:
          raise ValueError('Cannot back up to directory when source database has no path name.')
        target += name
        if target == self.path:
          raise ValueError('Cannot back up to same path as source database.')
    else:
      target_path = getattr(target, 'path', None)

    name_suffix = '' if name == 'main' else (':' + name)
    target_label = f' -> {target_path}' if target_path else ''
    label = f'Backup {self.path}{name_suffix}{target_label}'

    tty_progress = False
    progress_fn:BackupProgressFn|None = None
    if progress:
      if pages == -1: pages = 4096 # Need to set pages to get progress callbacks.
      if callable(progress):
        progress_fn = progress
      else:
        tty_progress = stderr.isatty()
        progress_end = '\r' if tty_progress else '\n'
        def _progress_fn(_status:int, remaining:int, total:int) -> None:
          frac = (total - remaining) / total
          print(f'{label}: {frac:0.1%}…', end=progress_end, file=stderr)
        progress_fn = _progress_fn

    if isinstance(target, str): target = Conn(target, mode='rwc')

    try: # Once target is (possibly) opened, we must guard it with try/finally to ensure it gets closed.
      if tty_progress: print(f'{label}…', end='\r', file=stderr)
      super().backup(target, pages=pages, progress=progress_fn, name=name, sleep=sleep)
    except BaseException:
      if tty_progress: print(f'{label} INCOMPLETE.', file=stderr)
      raise
    else:
      if tty_progress: print(f'{label} complete.', file=stderr)
    finally:
      if should_close_target: target.close()


  def run(self, sql:str, *, _dbg:bool=False, **args:Any) -> Cursor:
    '''
    Execute a query with parameter values provided by keyword arguments.
    Argument values whose types are not sqlite-compatible are automatically converted to JSON.
    '''
    return self.cursor().run(sql, _dbg=_dbg, **args)


def _is_busy(exc:OperationalError) -> bool:
  '''
  Return True if `exc` is a retryable busy error, i.e. any member of the SQLITE_BUSY family:
  * SQLITE_BUSY (primary code 5)
  * SQLITE_BUSY_RECOVERY (extended code 261): another process is recovering a hot journal/WAL.
  * SQLITE_BUSY_SNAPSHOT (extended code 517): the read snapshot went stale before the write-lock upgrade.
  * SQLITE_BUSY_TIMEOUT (extended code 773): a VFS-level lock timeout expired.
  All arrive as OperationalError. `sqlite_errorcode` is the extended result code;
  masking it with 0xFF reduces it to the primary code, matching so comparing to SQLITE_BUSY matches the whole family, including future subcodes.
  '''
  code = getattr(exc, 'sqlite_errorcode', None) # Only conditionally set.
  return code is not None and (code & 0xFF) == SQLITE_BUSY


def _backoff_ceiling(retry_max_sec:float, retry_base_sec:float, attempt:int) -> float:
  return min(retry_max_sec, retry_base_sec * (1 << attempt))


def sqlite_file_uri(path:str, *, mode:Mode,
 immutable:bool=False, modeof:str='', psow:bool|None=None, vfs:str='') -> str:
  '''
  Format an SQLite file URI. See https://www.sqlite.org/uri.html for parameter documentation.
  The `cache` parameter is not exposed (SQLite shared cache is deprecated).
  The `nolock` parameter is not exposed (disabling locking risks database corruption).
  '''
  params:list[str] = [f'mode={mode}']
  if immutable: params.append('immutable=1')
  if modeof: params.append(f'modeof={url_quote(modeof)}')
  if psow is not None: params.append(f'psow={int(psow)}')
  if vfs: params.append(f'vfs={url_quote(vfs)}')
  return f'file:{url_quote(path)}?{"&".join(params)}'
