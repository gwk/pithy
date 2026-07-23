# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.python.lint import lint_text
from utest import utest


# Module scope.

utest('', lint_text, '')
utest('', lint_text, 'a = 1')
utest('', lint_text, 'a = 1; b = 2')
utest('', lint_text, 'a = 1; print(a)') # Variable used; builtin reference.

utest('<str>:1: private variable `_a` in module scope never used.', lint_text, '_a = 1')

utest('''\
<str>:1: private variable `_a` in module scope never used.
<str>:1: private variable `_b` in module scope never used.''',
  lint_text, '_a, _b = 1, 2')

utest('', lint_text, '_a = 1\nprint(_a)') # Private variable used at module scope.
utest('', lint_text, '_a = 1\ndef f() -> int: return _a') # Private variable used by a nested function.
utest('', lint_text, '_a = 1\n_ = [_a for i in range(3)]') # Private variable used by an inlined comprehension.


# Never defined.

utest('<str>:1: variable `undefined` never defined.', lint_text, 'print(undefined)')
utest('<str>:2: variable `undefined` never defined.', lint_text, 'def f() -> None:\n  print(undefined)')
utest('<str>:1: deleted variable `x` never defined.', lint_text, 'del x')
utest('', lint_text, 'if __name__ == "__main__": pass') # Implicit module names are exempt.
utest('', lint_text, 'from os import *\nprint(getcwd())') # A star import suppresses never-defined checks.

utest('<str>:3: variable `attr` never defined.', lint_text, 'class C:\n  attr = 1\n  def m(self) -> int: return attr')
#^ Method bodies do not see class attributes as names.


# Function scope.

utest('', lint_text, 'def f(): pass')
utest('<str>:1: local variable `a` never used.', lint_text, 'def f(): a = 1')
utest('', lint_text, 'def f(): _a = 1') # Underscore-prefixed locals are exempt.
utest('', lint_text, 'def f(a:int) -> None: pass') # Parameters are exempt.
utest('<str>:2: local def `g` never used.', lint_text, 'def f() -> None:\n  def g() -> None: pass')
utest('<str>:2: local import `os` never used.', lint_text, 'def f() -> None:\n  import os')
utest('<str>:3: local exception `e` never used.', lint_text, 'def f() -> None:\n  try: pass\n  except ValueError as e:\n    pass')

utest('', lint_text, 'def f() -> list[int]:\n  a = 1\n  return [a for b in range(3)]') # Local used by an inlined comprehension.
utest('', lint_text, 'def f() -> None:\n  a = 1\n  def g() -> int: return a\n  g()') # Local used as a free variable.


# Global and nonlocal declarations.

utest('<str>:1: global declaration `g` in module scope.', lint_text, 'global g')
utest('<str>:3: global variable `g` never used.', lint_text, 'g = 0\ndef f() -> None:\n  global g')
utest('', lint_text, '_g = 0\ndef f() -> None:\n  global _g\n  _g += 1') # A store via `global` marks the module variable as used.

utest('', lint_text, 'def f() -> int:\n  v = 0\n  def g() -> None:\n    nonlocal v\n    v = 1\n  g()\n  return v')

utest('''\
<str>:2: local variable `v` never used.
<str>:4: nonlocal variable `v` never used.''',
  lint_text, 'def f() -> None:\n  v = 0\n  def g() -> None:\n    nonlocal v\n  g()')


# Class scope: no unused checks, because names may be used via attribute access.

utest('', lint_text, 'class C: pass')
utest('', lint_text, 'class _C: pass')

utest('', lint_text, '''
class C:
  def f(self): pass
  def _p(self): pass
''')

utest('', lint_text, '''
class _C:
  def f(self): pass
  def _p(self): pass
''')
