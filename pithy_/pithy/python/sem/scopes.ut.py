# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.python.sem import sem_for_source, SemExpr, SemModule, SemName, SemRef
from pithy.python.sem.scopes import build_import_map, build_scope_info, dependencies, dotted_name, ScopeInfo
from tolkien import Source
from utest import utest, utest_run, utest_seq, utest_val


def parse(code:str) -> SemModule:
  return sem_for_source(Source(name='<test>', text=code))


def scope_info_for(code:str) -> ScopeInfo:
  source = Source(name='<test>', text=code)
  return build_scope_info(sem_for_source(source), source=source)


def first_expr_ref(module:SemModule) -> SemRef:
  el = module.els[0]
  assert isinstance(el, SemExpr)
  ref = el.els[0]
  assert isinstance(ref, SemRef)
  return ref


# dotted_name: simple name, attribute chain, and non-simple ref (subscript).

utest('x', dotted_name, first_expr_ref(parse('x')))
utest('a.b.c', dotted_name, first_expr_ref(parse('a.b.c')))
utest(None, dotted_name, first_expr_ref(parse('a[0]')))


# build_import_map: various import forms.

utest({'os': 'os'}, build_import_map, parse('import os'))
utest({'os': 'os'}, build_import_map, parse('import os.path'))  # `os` is the local binding, not `os.path`.
utest({'o': 'os'}, build_import_map, parse('import os as o'))
utest({'p': 'os.path'}, build_import_map, parse('import os.path as p'))
utest({'join': 'os.path.join'}, build_import_map, parse('from os.path import join'))
utest({'j': 'os.path.join'}, build_import_map, parse('from os.path import join as j'))
utest({'foo': '.foo'}, build_import_map, parse('from . import foo'))  # Relative imports kept with leading dots.

utest(
  {'walk_files': 'pithy.fs.walk_files', 'ArgParser': 'pithy.argparser.ArgParser'},
  build_import_map,
  parse('from pithy.fs import walk_files\nfrom pithy.argparser import ArgParser'))


# iter_refs: explicit scope boundary — refs inside a nested function are not yielded.

_scope_mod = parse('x = 1\ndef foo():\n  y = x\nx + 1')
utest_seq(
  sorted(['x', 'x']),
  lambda m: sorted(r.ast_name.id for r in m.iter_refs() if isinstance(r, SemName)),
  _scope_mod)


# dependencies: from-import style.

_from_import_mod = parse('from pithy.fs import walk_files\nwalk_files(".")')
utest(
  frozenset({'pithy.fs.walk_files'}),
  dependencies,
  _from_import_mod, build_import_map(_from_import_mod))


# dependencies: bare import with attribute access; prefix-filtering collapses `os` and `os.path`.

_bare_import_mod = parse('import os\nos.path.join("a", "b")')
utest(
  frozenset({'os.path.join'}),
  dependencies,
  _bare_import_mod, build_import_map(_bare_import_mod))


# dependencies: two independent attribute chains from same import.

_multi_mod = parse('import os\nos.path.join("a", "b")\nos.getcwd()')
utest(
  frozenset({'os.path.join', 'os.getcwd'}),
  dependencies,
  _multi_mod, build_import_map(_multi_mod))


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
  utest_val('genexpr', gen.table.get_name(), desc='generator table name')
  utest_val('free', gen.free_kind('a'), desc='lambda param is free in generator scope')


# Match statement pattern captures are recorded as stores.

@utest_run
def _() -> None:
  info = scope_info_for('match cmd:\n  case [first, *rest]:\n    pass\n  case {"k": v, **extra}:\n    pass\n  case Point(x=0) as pt:\n    pass\n')
  pattern_names = {n for n, u in info.usages.items() if u.kind == 'pattern'}
  utest_val({'first', 'rest', 'v', 'extra', 'pt'}, pattern_names, desc='match pattern capture names')
  utest_val('global', info.free_kind('Point'), desc='`Point` is an unresolved load')
