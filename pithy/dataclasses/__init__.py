# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sys
if sys.version_info[:2] >= (3, 7):
  from dataclasses import *
else:
  import typing
  typing._GenericAlias = ... # type: ignore # Hack 3.6.
  from .backport import *

# copied from cpython/Lib/dataclasses.py.
__all__ = ['dataclass',
           'field',
           'FrozenInstanceError',
           'InitVar',
           'MISSING',

           # Helper functions.
           'fields',
           'asdict',
           'astuple',
           'make_dataclass',
           'replace',
           'is_dataclass',
           ]
