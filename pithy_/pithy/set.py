# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


'Set utilities.'

from typing import TypeVar


_T = TypeVar('_T')


def is_present_then_remove(s: set[_T], el: _T) -> bool:
  try: s.remove(el)
  except KeyError: return False
  else: return True
