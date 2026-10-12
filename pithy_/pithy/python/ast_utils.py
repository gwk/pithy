# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ast import AnnAssign, Global, Nonlocal


_context_keywords_ = ['AnnAssign', 'Global', 'Nonlocal', 'SyntaxError', 'declarations', 'diagnostics', 'error formatting']


type AstDecl = AnnAssign|Global|Nonlocal


def fmt_syntax_error(name:str, error:SyntaxError) -> str:
  return f'{name}:{error.lineno}: {error.msg}'
