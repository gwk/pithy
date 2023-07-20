# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from os import environ
from typing import Iterable, Iterator


class EnvParseError(ValueError): pass


def parse_env_lines(name:str, lines:Iterable[str]) -> Iterator[tuple[str,str]]:
  '''
  Parse shell-style environment variable lines of the form "KEY=value" or "export KEY=value".'
  Comments indicated by `#` are ignored.
  Quoted strings are not supported.
  '''
  for line_num, line in enumerate(lines, 1):
    line = line.strip()
    if not line or line.startswith('#'): continue
    m = _env_line_re.fullmatch(line)
    if not m: raise EnvParseError(f'{name}:{line_num}: invalid line: {line!r}')
    yield m['key'], m['value']


_env_line_re = re.compile(r'''(?x)
  ^
  (?P<export> export \s+ )?
  (?P<key> [A-Za-z_][A-Za-z0-9_]* )
  =
  (?P<value> [^#'"\n\s]* )
  \s*
  (?P<comment> [#].* )?
  $
''')


def load_env(path:str) -> None:
  '''
  Load shell-style environment definitions from `path` into `os.environ`.
  See `parse_env_lines` for details.
  '''
  with open(path) as f:
    for key, value in parse_env_lines(path, f):
      environ[key] = value
