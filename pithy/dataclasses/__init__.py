# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

try:
  from dataclasses import * # type: ignore
except ImportError:
  from .backport import * # copied from cpython/Lib/dataclasses.py.

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
