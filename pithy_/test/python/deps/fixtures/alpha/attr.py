import alpha.base
from os import path

from . import base


def via_attr() -> int:
  return alpha.base.helper(base.CONST)


def via_stdlib() -> str:
  return path.join('a', 'b')
