
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


def sanitize_for_py_keywords(s:str) -> str:
  '''
  Sanitize a string, appending a trailing underscore to Python keywords.
  '''
  return s + '_' if s in py_keywords else s
