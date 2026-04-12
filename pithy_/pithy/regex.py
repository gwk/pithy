# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from re import compile, Match, Pattern
from typing import Iterator


def find_matches_interleaved(pattern:str|Pattern, s:str) -> Iterator[Match|str]:
  'Find all matches, like re.finditer, but also yield the intervening text.'
  if isinstance(pattern, str): pattern = compile(pattern)
  pos = 0
  for m in pattern.finditer(s):
    start = m.start()
    if pos < start: yield s[pos:start]
    yield m
    pos = m.end()
  if pos < len(s): yield s[pos:]


def find_match_text_interleaved(pattern:str|Pattern, s:str) -> Iterator[str]:
  'Find matches with re.finditer, yielding matching text interleaved with the intervening text.'
  return (m[0] if isinstance(m, Match) else m for m in find_matches_interleaved(pattern, s))
