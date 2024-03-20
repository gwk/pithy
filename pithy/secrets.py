# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from dataclasses import dataclass


@dataclass(frozen=True)
class SecretStr:
  '''
  A string that is secret and should not be printed or logged.
  '''

  val:str = ''

  def __repr__(self) -> str: return 'SecretStr(*)'

  def __bool__(self) -> bool: return bool(self.val)


@dataclass(frozen=True)
class SecretBytes:
  '''
  Bytes object that is secret and should not be printed or logged.
  '''

  val:bytes = b''

  def __repr__(self) -> str: return 'SecretBytes(*)'

  def __bool__(self) -> bool: return bool(self.val)
