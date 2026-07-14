# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
A simple SQLite REPL for the pithy.sqlite package.

This mirrors the Python standard library `sqlite3.__main__` module, but builds the REPL on
`pithy.interactive.Interpreter` and the pithy `Conn` connection class.
'''

import sqlite3
from argparse import ArgumentParser, Namespace
from sys import stderr

from ..filestatus import is_dir, is_file
from ..interactive import Interpreter
from ..path import path_join
from . import sqlite_version, SqliteError
from .conn import Conn, Mode, valid_modes
from .cursor import Cursor
from .database import Database, DbConfig, manifest_filename


def main() -> None:
  parser = ArgumentParser(prog='pithy.sqlite', description='Pithy sqlite3 CLI.')
  parser.add_argument('filename', nargs='?', default=':memory:',
    help="SQLite database file or group directory to open (defaults to ':memory:'). "
      'A new file is created if a file path does not exist. '
      f'A directory containing a {manifest_filename!r} manifest is opened as an attached group; see pithy.sqlite.Database.')
  parser.add_argument('sql', nargs='?', help='An SQL query to execute. Any returned rows are printed to stdout.')
  parser.add_argument('-mode', choices=valid_modes, default=None,
    help="Connection mode. Defaults to 'memory' for an in-memory database, or 'ro' for a file or group. "
      "A group accepts only 'ro' or 'rw'.")
  parser.add_argument('-version', action='version', version=f'SQLite version {sqlite_version}',
    help='Print the underlying SQLite library version.')
  args = parser.parse_args()

  if args.filename != ':memory:' and is_dir(args.filename, follow=True):
    run_group(args)
    return

  if args.filename == ':memory:':
    mode:Mode = args.mode or 'memory'
    db_desc = ':memory:'
  else:
    mode = args.mode or 'ro'
    db_desc = repr(args.filename)

  with Conn(args.filename, mode=mode).closing() as conn:
    run_repl_or_sql(conn, args.sql, db_desc)


def run_group(args:Namespace) -> None:
  'Open an attached group directory described by its manifest, attaching all member databases.'
  data_dir = args.filename
  manifest_path = path_join(data_dir, manifest_filename)
  if not is_file(manifest_path, follow=True):
    exit(f'error: database directory has no {manifest_filename!r} manifest: {data_dir!r}.')
  mode = args.mode or 'ro'
  if mode not in ('ro', 'rw'):
    exit(f"error: database group accepts only 'ro' or 'rw' modes; got {mode!r}.")
  config = DbConfig.load_manifest(data_dir)
  db = Database.rw(config) if mode == 'rw' else Database.ro(config)
  with db:
    db_desc = f'{data_dir!r} (group {mode}: {", ".join(config.names)})'
    run_repl_or_sql(db.conn, args.sql, db_desc)


def run_repl_or_sql(conn:Conn, sql:str|None, db_desc:str) -> None:
  'Execute `sql` and exit, or run the interactive REPL against `conn`.'
  if sql:
    ok = execute(conn.cursor(), sql)
    exit(0 if ok else 1)
  try:
    import readline
    _ = readline # Enable line editing and history if available.
  except ImportError: pass
  banner = '\n'.join([
    f'pithy.sqlite shell, running on SQLite version {sqlite_version}; connected to {db_desc}.',
    'Type ".quit" or CTRL-D to quit; type ".help" for more help.',])
  interpreter = SqliteInterpreter(conn)
  interpreter.interact(banner=banner, exit_msg='')


def execute(c:Cursor, sql:str) -> bool:
  '''
  Execute `sql` on a connection or cursor, printing any result rows to stdout.
  On error, print a description to stderr; returns `ok` status.
  '''
  try:
    for row in c.execute(sql):
      print(tuple(row))
    return True
  except SqliteError as e:
    name = type(e).__name__
    errorname = getattr(e, 'sqlite_errorname', None)
    if errorname:
      print(f'{name} ({errorname}): {e}', file=stderr)
    else:
      print(f'{name}: {e}', file=stderr)
    return False


class SqliteInterpreter(Interpreter):

  def __init__(self, conn:Conn) -> None:
    super().__init__()
    self.conn = conn
    self.cursor = conn.cursor()


  def runsource(self, source:str, filename:str='<input>', symbol:str='single') -> bool:
    '''
    Execute a complete SQL statement or dot-command.
    Return True if more input is needed (an incomplete statement is buffered automatically), else False.
    '''
    if not source or source.isspace():
      return False
    if source[0] == '.':
      command = source[1:].strip()
      match command:
        case 'version':
          print(sqlite_version)
        case 'help':
          print('Enter SQL code and press enter.')
        case 'quit':
          raise SystemExit(0)
        case '':
          pass
        case _:
          self.write(f'Error: unknown command or invalid arguments:  "{command}".\n')
      return False
    if not sqlite3.complete_statement(source):
      return True
    execute(self.cursor, source)
    return False


if __name__ == '__main__': main()
