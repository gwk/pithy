# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Various exception classes.
'''


class ConflictingValues(ValueError):
  '''
  Raised when an incoming value collides with an existing value.
  In one sense, it is both a KeyError and a ValueError.
  '''

class DeleteNode(Exception):
  'Signals a traverser to delete the current node.'

class FlattenNode(Exception):
  'Signals a traverser to delete the current node.'

class OmitNode(Exception):
  'Signals a transformer to omit the current node.'


class MultipleMatchesError(KeyError):
  'Raised when a query matches multiple children.'


class NoMatchError(KeyError):
  'Raised when a query matches no children.'

