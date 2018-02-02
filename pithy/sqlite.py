# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from typing import *


class SqliteError(Exception): pass


class Cursor(sqlite3.Cursor):

  def run(self, *sql: str, **args: Any) -> 'Cursor':
    query = ' '.join(sql)
    try: return cast(Cursor, self.execute(query, args))
    except sqlite3.OperationalError as e:
      raise SqliteError(f'syntax error; query: {query!r}') from e


class Connection(sqlite3.Connection):

  def cursor(self, factory:Optional[type]=None) -> Cursor:
    if factory is None:
      factory = Cursor
    assert issubclass(factory, Cursor)
    return cast(Cursor, super().cursor(factory))

  def run(self, *sql: str, **args: Any) -> Cursor:
      return self.cursor().run(*sql, **args)

  def select(self, *sql: str, **args: Any) -> Cursor:
    return self.run('SELECT', *sql, **args)

  def select_opt(self, *sql: str, **args: Any) -> Optional[List[Any]]:
    return self.run('SELECT', *sql, **args).fetchone() # type: ignore

  def select_col(self, *sql: str, **args: Any) -> Iterator[Any]:
    for row in self.run('SELECT', *sql, **args):
      assert len(row) == 1
      yield row[0]
