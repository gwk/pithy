# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from utest import utest
from utest.lint import lint_source


def lint(line:str) -> list[str]:
  'Lint a single line and strip the constant location prefix from each message.'
  return [m.removeprefix('t.ut.py:1:1: ') for m in lint_source('t.ut.py', line)]


# Values that are not the result of a direct call are accepted.
for line in [
  'utest_val(1, obj.attr)',
  'utest_val(1, d["k"])',
  'utest_val(True, "a" in f(x))',
  'utest_val([1], [el.x for el in f()])',
  'utest_val((1, 2), (f(), g()))',
  'utest_val_ne(1, f(x))',
  'utest_val(*pair)',
  'utest(1, f, x)',
]:
  utest([], lint, line)

utest(['`utest_val` wraps a call to `f`; use `utest(exp, f, ...)`.'], lint, 'utest_val(1, f(x))')
utest(['`utest_val` wraps a call to `f`; use `utest(exp, f, ...)`.'], lint, 'utest_val(exp_val=1, act_val=f(x))')
utest(['`utest_val` wraps a call to `obj.method`; use `utest(exp, obj.method, ...)`.'], lint, 'utest_val(1, obj.method(), "desc")')
utest(['`utest_val` wraps a call to `len`; use `utest(exp, len, ...)`.'], lint, 'utest_val(1, len(items))')
utest(['`utest_val_type` wraps a call to `f`; use `utest_type(exp, f, ...)`.'], lint, 'utest_val_type(int, f(x))')

# Builtins that a test function applies itself.
utest(['`utest_val` wraps a call to `list`; use `utest_seq(exp, f, ...)`.'], lint, 'utest_val([1], list(f(x)))')
utest(['`utest_val` wraps a call to `sorted`; use `utest_seq(exp, f, ..., _sort=True)`.'], lint, 'utest_val([1], sorted(f(x)))')
utest(['`utest_val` wraps a call to `repr`; use `utest_repr(exp, f, ...)`.'], lint, 'utest_val("1", repr(f(x)))')
utest(['`utest_val` wraps a call to `list`; use `utest(exp, list, ...)`.'], lint, 'utest_val([1], list(items))')

# A keyword argument that collides with a test function parameter cannot be forwarded.
utest([], lint, 'utest_val(1, f(fn=g))')

utest(['t.ut.py:2:3: `utest_val` wraps a call to `f`; use `utest(exp, f, ...)`.'], lint_source, 't.ut.py',
  'def t():\n  utest_val(1, f(x))\n')

utest(["t.ut.py:1:2: syntax error: '(' was never closed."], lint_source, 't.ut.py', 'f(')
