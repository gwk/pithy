# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Dict, List

from ..lex import c_like_punctuation_patterns, Lexer, LexMode, whitespace_patterns


patterns=dict(
  # These are ordered roughly to improve matching speed on a sample (all .py files in the repository).

  # Python keywords must come before `name`.
  const = r'None|True|False',
  kw_as       = 'as',
  kw_async    = 'async',
  kw_await    = 'await',
  kw_break    = 'break',
  kw_class    = 'class',
  kw_continue = 'continue',
  kw_def      = 'def',
  kw_elif     = 'elif',
  kw_else     = 'else',
  kw_for      = 'for',
  kw_from     = 'from',
  kw_if       = 'if',
  kw_import   = 'import',
  kw_while    = 'while',
  kw_yield    = 'yield',

  name  = r'[_A-Za-z][_A-Za-z0-9]*', # Most common.
  **whitespace_patterns,
  int_h = r'0x[_0-9A-Fa-f]+',
  int_b = r'0b[_01]+',
  int_o = r'0o[_07]+',
  flt   = r'([0-9]+\.|\.[0-9])[_0-9]*',
  int_d = r'[0-9][_0-9]*',

  **c_like_punctuation_patterns,

  comment_type_ignore = r'\# type: ignore',
  comment_type      = r'\# type:[\n]*',
  comment           = r'\#[^\n]*',
)

main_pattern_names = list(patterns.keys())


str_pattern_names:Dict[str,List[str]] = {}

def add_str_patterns(quote:str, label:str, multiline:bool):
  '''
  Note about lexing string literals:
  general pattern for quoting with escapes is Q([^EQ]|EQ|EE)*Q.
  It is crucial that the escape character E is excluded in the '[^EQ]' clause,
  or else when matching against 'QEQQ', the pattern greedily matches 'QEQ'.
  To allow a trailing escape character, the 'EE' clause is also required.
  '''
  q = quote
  q0 = q[0]
  n = r'\n' # Normally, newline is part of the exclusion set.
  or_ml = '' # Multiline has an additional choice clause.
  if multiline:
    n = '' # For multiline, newline is not excluded.
    or_ml = r'|' + q0 + r'{1,2}(?!' + q0 + ')' # Accept one or two quotes, so long as they aren't followed by a third.
  # The leading "(?:r[bf]|[bf]?r?)" pattern is for all the valid combinations of [rbf] flags.
  patterns.update({
    f'str_{label}'      : fr'(?:r[bf]|[bf]?r?){q}(?s:[^{n}\\{q0}]|\\.{or_ml})*{q}',
    f'str_{label}_o'    : fr'(?:r[bf]|[bf]?r?){q}',
    f'str_{label}_c'    : q,
    f'str_{label}_re'   : r'[][(){}|^?*+]+',
    f'str_{label}_txt'  : fr'[^\\{q[0]}]',
    f'str_{label}_esc'  : r'\\.',
  })


for l, q in [('s', "'"), ('d', '"')]:
  for multiline in [True, False]:
    label = l + '3' if multiline else l
    quote = q * 3 if multiline else q
    add_str_patterns(label=label, quote=quote, multiline=multiline)
    main_pattern_names.append('str_' + label) # TODO: generalize to allow choosing multimode lexer.

lexer = Lexer(flags='x', patterns=patterns, modes=[LexMode('main', main_pattern_names)])
