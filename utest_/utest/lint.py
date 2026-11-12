#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Lint utest unit tests for `utest_val` and `utest_val_type` calls that should use a calling test function.

A call such as `utest_val(exp, f(x))` evaluates `f(x)` before `utest_val` runs.
A failure report then omits the arguments, and an exception raised by `f` aborts the remaining tests in the file.
The lint reports each such call and names the replacement; see the `utest` module documentation for the rationale.

Usage: `python3 -m utest.lint [paths...]`.
'''

import ast
from sys import stderr

from pithy.cmdparse import Cmd, pos
from pithy.fs import walk_files


_context_keywords_ = ['linter', 'static analysis', 'test style', 'unit tests']


def main() -> None:
  args = LintUtest.parse_or_exit()
  messages:list[str] = []
  for path in walk_files(*args.paths, file_exts='.ut.py'):
    with open(path) as f: text = f.read()
    messages.extend(lint_source(path, text))
  for message in messages: print(message, file=stderr)
  if messages: raise SystemExit(1)


class LintUtest(Cmd):
  'Report `utest_val` and `utest_val_type` calls in `.ut.py` files that wrap a function call.'
  paths:list[str] = pos(doc='Files and directories to search for `.ut.py` files.')


def lint_source(path:str, text:str) -> list[str]:
  'Return a message for each `utest_val` or `utest_val_type` call in `text` whose actual value is a function call.'
  try: tree = ast.parse(text, filename=path)
  except SyntaxError as e: return [f'{path}:{e.lineno}:{e.offset}: syntax error: {e.msg}.']
  messages = []
  for node in ast.walk(tree):
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)): continue
    replacement = val_replacements.get(node.func.id)
    if replacement is None: continue
    actual = _actual_arg(node)
    if not isinstance(actual, ast.Call): continue
    if any(kw.arg in reserved_param_names for kw in actual.keywords): continue
    #^ The calling test functions bind these names themselves, so the call cannot be forwarded.
    callee = ast.unparse(actual.func)
    view = view_replacements.get(callee)
    if view and node.func.id == 'utest_val' and _is_sole_call_arg(actual):
      inner = actual.args[0]
      assert isinstance(inner, ast.Call)
      view_fn, view_note = view
      advice = f'use `{view_fn}(exp, {ast.unparse(inner.func)}, ...{view_note})`'
    else:
      advice = f'use `{replacement}(exp, {callee}, ...)`'
    messages.append(f'{path}:{node.lineno}:{node.col_offset+1}: `{node.func.id}` wraps a call to `{callee}`; {advice}.')
  return messages


val_replacements = {
  'utest_val': 'utest',
  'utest_val_type': 'utest_type',
}
'Each value-checking function mapped to the test function that calls the function under test.'

view_replacements = {
  'list': ('utest_seq', ''),
  'repr': ('utest_repr', ''),
  'sorted': ('utest_seq', ', _sort=True'),
  'tuple': ('utest_seq', ''),
}
'Builtins that a test function applies to the result itself, mapped to that function and any extra argument it needs.'

reserved_param_names = frozenset({'exp', 'exp_type', 'fn'})
'Parameter names of the calling test functions; a keyword argument with one of these names cannot be forwarded.'


def _actual_arg(call:ast.Call) -> ast.expr|None:
  'Return the expression passed as `act_val`, or None if it cannot be determined statically.'
  if len(call.args) >= 2:
    if any(isinstance(arg, ast.Starred) for arg in call.args[:2]): return None
    return call.args[1]
  for kw in call.keywords:
    if kw.arg == 'act_val': return kw.value
  return None


def _is_sole_call_arg(call:ast.Call) -> bool:
  'Return whether `call` has exactly one argument and that argument is itself a call.'
  return len(call.args) == 1 and not call.keywords and isinstance(call.args[0], ast.Call)


if __name__ == '__main__': main()
