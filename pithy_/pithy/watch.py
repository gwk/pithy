# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Iterable
from os import sep as path_sep
from os.path import realpath
from typing import TYPE_CHECKING


if TYPE_CHECKING: from watchfiles import DefaultFilter


_context_keywords_ = ['change detection', 'file watching', 'ignore paths', 'watch filter', 'watchfiles']


'''
File watching helpers built on `watchfiles`.

`watchfiles` is imported lazily, so importing this module does not require it.
'''


def watch_filter(ignore:Iterable[str]=()) -> DefaultFilter:
  '''
  Return a `watchfiles` filter for watching source trees during development.

  It extends the watchfiles `DefaultFilter`, which skips bytecode, version control and editor files,
  to also skip isort's `.isorted` temporaries and every file under the `ignore` directories.
  Pass the result as the `watch_filter` argument of `watchfiles.watch` or `watchfiles.run_process`.
  '''
  from watchfiles import DefaultFilter

  # watchfiles matches ignore paths as string prefixes against the real paths it reports; the trailing separator
  # prevents a directory from also matching its siblings with the same prefix.
  return DefaultFilter(ignore_entity_patterns=(*DefaultFilter.ignore_entity_patterns, r'\.isorted$'),
    ignore_paths=[realpath(path).rstrip(path_sep) + path_sep for path in ignore])
