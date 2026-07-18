# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from sqlite3 import (DatabaseError, DataError, IntegrityError, InterfaceError, InternalError, NotSupportedError,
  OperationalError, ProgrammingError)
from typing import TypeAlias

from .conn import Conn, Mode
from .cursor import Cursor
from .row import Row
from .util import (CURRENT_DATE, CURRENT_TIME, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP_Z, forbid_default_adapters_and_converters,
  SqlExpr, sqlite_native_val, SqliteDatatype)


# Silence linter by referencing imported names.

_:tuple = (Row, Cursor, Conn, Mode, CURRENT_DATE, CURRENT_TIME, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP_Z,
  forbid_default_adapters_and_converters, SqlExpr, SqliteDatatype, sqlite_native_val)

_ = (DatabaseError, DataError, IntegrityError, InterfaceError, InternalError, NotSupportedError, OperationalError,
  ProgrammingError)

SqliteError:TypeAlias = sqlite3.Error
SqliteWarning:TypeAlias = sqlite3.Warning


sqlite_version = sqlite3.sqlite_version
sqlite_threadsafe_dbapi_id = sqlite3.threadsafety

sqlite_threadsafe_dbapi_id_descs = [
  '0 - single-thread (threads may not share the module).',
  '1 - multi-thread (threads may share the module, but not connections).',
  '2 - invalid.',
  '3 - serialized (threads may share the module and connections).',
]

sqlite_threadsafe_desc = sqlite_threadsafe_dbapi_id_descs[sqlite_threadsafe_dbapi_id]


def enable_resource_warnings() -> None:
  '''
  Enabling resource warnings will cause messages about leaked SQLite connections, which can cause serious availability problems.
  '''
  from warnings import filterwarnings
  filterwarnings("default", category=ResourceWarning)
