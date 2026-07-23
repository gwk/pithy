from .base import CONST
from .mid import make, Mid


def run() -> int:
  m = make()
  return m.value() + CONST


def lazy_json() -> object:
  import json
  return json.loads('{}')


_ = Mid
