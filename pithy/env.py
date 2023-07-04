# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from os import environ
from typing import Iterable, Iterator


def parse_env_lines(name:str, lines:Iterable[str]) -> Iterator[tuple[str,str]]:
  '''
  Parse shell-style environment variable lines of the form "KEY=value" or "export KEY=value".'
  Comments indicated by `#` are ignored.
  Quoted strings are not supported.
  '''
  for line_num, line in enumerate(lines, 1):
    line = line.strip()
    if not line or line.startswith('#'): continue
    if line.startswith('export '): line = line[7:].lstrip()
    key, _, value = line.partition('=')
    if key.rstrip() != key: raise ValueError(f'{name}:{line_num}: key has trailing whitespace: {key!r}.')
    value, _, _ = value.partition('#')
    value = value.rstrip()
    if value.lstrip() != value: raise ValueError(f'{name}:{line_num}: value has leading whitespace: {value!r}.')
    yield key, value


def load_env(path:str) -> None:
  '''
  Load shell-style environment definitions from `path` into `os.environ`.
  See `parse_env_lines` for details.
  '''
  with open(path) as f:
    for key, value in parse_env_lines(path, f):
      environ[key] = value
