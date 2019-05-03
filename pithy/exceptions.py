# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Various exception classes.
'''


class DeleteNode(Exception):
  'Signals a traverser to delete the current node.'


class OmitNode(Exception):
  'Signals a transformer to omit the current node.'


class MultipleMatchesError(KeyError):
  'Raised when a query matches multiple children.'


class NoMatchError(KeyError):
  'Raised when a query matches no children.'

