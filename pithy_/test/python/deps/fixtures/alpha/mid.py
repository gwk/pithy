import os

from .base import Base, helper


class Mid(Base):

  def value(self) -> int:
    return helper(1)


def make() -> Mid:
  print(os.devnull)
  return Mid()
