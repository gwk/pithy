# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


import builtins


py_keywords = frozenset({
  'None',
  'True',
  'False',
  'as',
  'async',
  'await',
  'break',
  'class',
  'continue',
  'def',
  'elif',
  'else',
  'for',
  'from',
  'if',
  'import',
  'while',
  'yield',
})


py_reserved_words = py_keywords.union(n for n in builtins.__dict__.keys())


def sanitize_for_py_keywords(s:str) -> str:
  '''
  Sanitize a string, appending a trailing underscore to Python keywords.
  '''
  return s + '_' if s in py_keywords else s



def sanitize_for_py_reserved_words(s:str) -> str:
  '''
  Sanitize a string, appending a trailing underscore to Python reserved words (keywords and builtins).
  '''
  return s + '_' if s in py_reserved_words else s
