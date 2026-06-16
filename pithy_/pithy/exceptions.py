# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Various exception classes.
'''

from contextlib import AbstractContextManager, ContextDecorator
from traceback import print_exception
from typing import Any

from .typing_utils import OptBaseExc, OptTraceback, OptTypeBaseExc


class ConflictingValues(KeyError):
  '''
  Raised when an incoming value collides with an existing value.
  In one sense, it is similar to both a key error and a value error.
  Since it arises from a key lookup, it subclasses KeyError.
  '''
  def __init__(self, *, key:Any, existing:Any, incoming:Any) -> None:
    self.key = key
    self.existing = existing
    self.incoming = incoming
    super().__init__(key) # Initialized like a KeyError.


class DeleteNode(Exception):
  'Signals a traverser to delete the current node.'

class FlattenNode(Exception):
  'Signals a traverser or transformer to delete the current node.'

class OmitNode(Exception):
  'Signals a transformer to omit the current node.'


class MultipleMatchesError(KeyError):
  'Raised when a query matches multiple children.'


class NoMatchError(KeyError):
  'Raised when a query matches no children.'


class print_traceback_and_suppress(AbstractContextManager, ContextDecorator):
  '''
  Context manager to catch and suppress specified exceptions, printing the traceback to stderr.

  After the exception is printed, execution proceeds with the next statement following the with statement.

  This context manager can also be used as a decorator.

  This implementation is derived from the `suppress` context manager in the Python standard library.
  '''

  def __init__(self, *exceptions:type[BaseException]) -> None:
    self._exceptions = exceptions

  def __enter__(self) -> print_traceback_and_suppress:
    return self

  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> bool:
    if exc_type is None: return False
    if issubclass(exc_type, self._exceptions):
      print_exception(exc_type, exc_value, traceback)
      return True
    if isinstance(exc_value, BaseExceptionGroup):
      _, rest = exc_value.split(self._exceptions)
      if rest is None: # Every leaf matched: report the whole group and suppress.
        print_exception(exc_value)
        return True
      return False # Some leaf did not match: propagate the original group unchanged.
    return False
