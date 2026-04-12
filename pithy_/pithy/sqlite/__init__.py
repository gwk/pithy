# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from sqlite3 import (DatabaseError, DataError, IntegrityError, InterfaceError, InternalError, NotSupportedError,
  OperationalError, ProgrammingError)
from typing import TypeAlias

from .conn import Conn
from .cursor import Cursor
from .row import Row


# Silence linter by referencing imported names.

_:tuple = (Row, Cursor, Conn)

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
