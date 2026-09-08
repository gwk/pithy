# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from enum import auto, StrEnum


class DomainEvent(StrEnum):
  'Application events dispatched to the document body. Values are identical to the member names.'
  user_updated = auto()
