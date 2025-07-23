# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from typing import Match


def is_ref(string:str) -> bool:
  return bool(re.fullmatch(r'[0-9A-F]{24}', string))


def quote_string(string:str) -> str:
  if re.fullmatch(r'[\w\./]+', string): return string
  escaped = re.sub(r'[\\"\n]', char_escape, string)
  return f'"{escaped}"'


def unquote_string(string:str) -> str:
  contents = string[1:-1]
  return re.sub(r'\\(.)', char_unescape, contents)


def char_escape(m:Match[str]) -> str: return char_escapes[m[0]]

char_escapes = {
  '\\' : '\\\\',
  '"' : '\\"',
  '\n' : '\\n',
}

def char_unescape(m:Match[str]) -> str: return char_unescapes[m[1]]

char_unescapes = {
  '\\' : '\\',
  '"' : '"',
  'n': '\n',
}
