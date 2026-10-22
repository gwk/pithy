# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.python.sem import sem_for_source, SemModule, SemName
from pithy.python.sem.scopes import build_scope_info, ScopeInfo
from tolkien import Source
from utest import utest_run, utest_seq, utest_val


def parse(code:str) -> SemModule:
  return sem_for_source(Source(name='<test>', text=code))


def scope_info_for(code:str) -> ScopeInfo:
  source = Source(name='<test>', text=code)
  return build_scope_info(sem_for_source(source), source=source)


# iter_refs: explicit scope boundary — refs inside a nested function are not yielded.

_scope_mod = parse('x = 1\ndef foo():\n  y = x\nx + 1')
utest_seq(
  sorted(['x', 'x']),
  lambda m: sorted(r.ast_name.id for r in m.iter_refs() if isinstance(r, SemName)),
  _scope_mod)


# build_scope_info with symtable attachment: nested function free variable classification.

@utest_run
def _() -> None:
  info = scope_info_for('def outer():\n  a = 1\n  def inner():\n    return a\n')
  outer = info.children[0]
  inner = outer.children[0]
  utest_val('def', outer.kind, desc='outer scope kind')
  utest_val(True, info.table is not None and outer.table is not None and inner.table is not None, desc='tables attached')
  utest_val('free', inner.free_kind('a'), desc='`a` is free in inner scope')
  outer_a = outer.symbol('a')
  assert outer_a is not None
  utest_val(True, outer_a.is_local(), desc='`a` is local to outer scope')


# free_kind at module scope distinguishes builtins from other unresolved names.

@utest_run
def _() -> None:
  info = scope_info_for('print(undefined_name)\n')
  utest_val('builtin', info.free_kind('print'), desc='`print` classified as builtin')
  utest_val('global', info.free_kind('undefined_name'), desc='unresolved module name classified as global')


# Comprehension scopes have no symtable of their own (PEP 709 inlines them); symbol lookup falls back to the parent.

@utest_run
def _() -> None:
  info = scope_info_for('zs = [1]\nys = [x*2 for x in zs]\n')
  comp = info.children[0]
  utest_val('comprehension', comp.kind, desc='comp scope kind')
  utest_val(None, comp.table, desc='comp scope table')
  sym_x = comp.symbol('x')
  assert sym_x is not None
  utest_val(True, sym_x.is_local(), desc='`x` found via parent table')
  utest_val(True, 'x' in comp.local_names(), desc='`x` recorded as local usage of comp scope')


# Walrus assignment inside a comprehension binds in the enclosing scope.

@utest_run
def _() -> None:
  info = scope_info_for('zs = [1]\nys = [y := x*2 for x in zs]\n')
  comp = info.children[0]
  utest_val(True, 'y' in info.local_names(), desc='walrus target is local to module scope')
  utest_val(False, 'y' in comp.local_names(), desc='walrus target is not local to comp scope')


# Generator expressions and lambdas get their own symtables.

@utest_run
def _() -> None:
  info = scope_info_for('f = lambda a: (a+i for i in range(3))\n')
  lam = info.children[0]
  gen = lam.children[0]
  utest_val('lambda', lam.kind, desc='lambda scope kind')
  utest_val('generator', gen.kind, desc='generator scope kind')
  assert lam.table is not None and gen.table is not None
  utest_val('<lambda>', lam.table.get_name(), desc='lambda table name')
  utest_val('<genexpr>', gen.table.get_name(), desc='generator table name')
  utest_val('free', gen.free_kind('a'), desc='lambda param is free in generator scope')


# Match statement pattern captures are recorded as stores.

@utest_run
def _() -> None:
  info = scope_info_for('match cmd:\n  case [first, *rest]:\n    pass\n  case {"k": v, **extra}:\n    pass\n  case Point(x=0) as pt:\n    pass\n')
  pattern_names = {n for n, u in info.usages.items() if u.kind == 'pattern'}
  utest_val({'first', 'rest', 'v', 'extra', 'pt'}, pattern_names, desc='match pattern capture names')
  utest_val('global', info.free_kind('Point'), desc='`Point` is an unresolved load')
