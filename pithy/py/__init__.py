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


py_builtin_type_names = frozenset({
  'bool',
  'bytearray',
  'bytes',
  'complex',
  'dict',
  'float',
  'frozenset',
  'int',
  'list',
  'memoryview',
  'object',
  'range',
  'set',
  'slice',
  'str',
  'tuple',
  'type',
})


py_keywords_and_type_names = py_keywords | py_builtin_type_names

py_reserved_words = py_keywords.union(n for n in builtins.__dict__.keys())


py_keywords_remap = { w : w+'_' for w in py_keywords }

py_keywords_and_type_names_remap = { w : w+'_' for w in py_keywords_and_type_names }

py_reserved_words_remap = { w : w+'_' for w in py_reserved_words }


def sanitize_for_py_keywords(s:str) -> str:
  '''
  Sanitize a string, appending a trailing underscore to Python keywords.
  '''
  return py_keywords_remap.get(s, s)




def sanitize_for_py_keywords_and_type_names(s:str) -> str:
  '''
  Sanitize a string, appending a trailing underscore to Python keywords and type names.
  '''
  return py_keywords_and_type_names_remap.get(s, s)



def sanitize_for_py_reserved_words(s:str) -> str:
  '''
  Sanitize a string, appending a trailing underscore to Python reserved words (keywords and builtins).
  '''
  return py_reserved_words_remap.get(s, s)
