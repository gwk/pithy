# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Scope construction and name-usage analysis for `pithy.python.sem` trees.

`build_scope_info` builds a `ScopeInfo` tree by traversing a `SemModule`,
recording the first occurrence of each kind of use (declare/store/load/delete) of every name in each scope.
When given the module source it also attaches the stdlib `symtable` tables,
which serve as the authoritative classification of name bindings (local/free/global/builtin).

TODO: names referenced only inside annotations, `type` alias values, or type parameter bounds/defaults
reside in implicit `annotation`/`type alias`/`type parameters` symbol tables (PEP 649 / PEP 695).
`ScopeInfo.symbol` does not search these, so such names classify as `unknown`; model these implicit scopes.
'''

import builtins as _builtins
from collections import deque
from dataclasses import dataclass, field
from functools import singledispatch
from symtable import Symbol, SymbolTable, symtable as build_symtable
from typing import Iterator, Literal

from tolkien import Source

from . import (Sem, SemAlias, SemAnnAssign, SemArg, SemArguments, SemAsyncFunctionDef, SemAttribute, SemAugAssign, SemClassDef,
  SemComprehension, SemDictComp, SemExceptHandler, SemFunctionDef, SemGeneratorExp, SemGlobal, SemImport, SemImportFrom,
  SemLambda, SemListComp, SemMatchAs, SemMatchMapping, SemMatchStar, SemModule, SemName, SemNamedExpr, SemNode, SemNonlocal,
  SemRef, SemScope, SemSetComp)


type ScopeKind = Literal['module', 'class', 'def', 'async def', 'lambda', 'comprehension', 'generator']
type UsageKind = Literal['annotation', 'async def', 'class', 'def', 'exception', 'global', 'import', 'nonlocal', 'parameter',
  'pattern', 'variable']
type FreeKind = Literal['builtin', 'free', 'global', 'unknown']

builtin_names = frozenset(_builtins.__dict__)


@dataclass
class Usage:
  '''
  Tracks the first occurrence of each kind of use of a name within a scope.
  `decl` covers annotation-only AnnAssign (no value), Global, and Nonlocal.
  '''

  kind: UsageKind|None = None
  decl: Sem|None = None   # First AnnAssign (no value), SemGlobal, or SemNonlocal.
  store: Sem|None = None  # First assignment / import / def / class / param.
  load: Sem|None = None   # First load reference.
  delete: Sem|None = None # First del reference.


  @property
  def primary_node(self) -> Sem:
    first = self.decl or self.store or self.load or self.delete
    assert first is not None
    return first


  @property
  def is_local(self) -> bool:
    'True if the name is defined (stored or declared) in this scope.'
    return self.store is not None or self.decl is not None


@dataclass
class ScopeInfo:
  '''
  The collected symbol-table information for one explicit Python scope.
  `usages` maps each name to its first occurrence of each kind.
  `imports` maps local name to qualified name (with leading dots for relative imports).
  `table` is the corresponding stdlib `symtable.SymbolTable`, attached when `build_scope_info` is given the source;
  it serves as the authoritative classifier of name bindings (local/free/global).
  Comprehension scopes have no table of their own because the compiler inlines them (PEP 709);
  their names live in the nearest enclosing real scope's table.
  '''
  name: str
  kind: ScopeKind
  node: SemScope
  parent: ScopeInfo|None = field(default=None, repr=False)
  table: SymbolTable|None = field(default=None, repr=False)
  has_star_import: bool = False # True if the scope contains a `from ... import *`.
  usages: dict[str,Usage] = field(default_factory=dict)
  imports: dict[str,str] = field(default_factory=dict) # local -> qualified.
  children: list[ScopeInfo] = field(default_factory=list)


  def add_child(self, child:ScopeInfo) -> ScopeInfo:
    child.parent = self
    self.children.append(child)
    return child


  def binding_scope(self) -> ScopeInfo:
    'The scope where assignments bind. Comprehension/generator scopes do not own walrus bindings.'
    scope = self
    while scope.kind in ('comprehension', 'generator') and scope.parent is not None:
      scope = scope.parent
    return scope


  def symbol(self, name:str) -> Symbol|None:
    '''
    Look up the symtable Symbol for `name` in this scope; returns None if no table is attached or the name is absent.
    Comprehension scopes delegate to the parent scope, where the compiler places their inlined symbols.
    Note: names referenced only in annotations or type alias values reside in implicit `annotation`/`type alias` tables
    (PEP 649 / PEP 695) and are not found by this lookup.
    '''
    if self.table is not None:
      try: return self.table.lookup(name)
      except KeyError: return None
    if self.kind in ('comprehension', 'generator') and self.parent is not None:
      return self.parent.symbol(name)
    return None


  def free_kind(self, name:str) -> FreeKind:
    'Classify a free (not locally bound) name, using the symtable Symbol when available.'
    sym = self.symbol(name)
    if sym is not None:
      if sym.is_free(): return 'free'
      if sym.is_global(): return 'builtin' if name in builtin_names else 'global'
    return 'builtin' if name in builtin_names else 'unknown'


  def get_or_add_usage(self, name:str) -> Usage:
    try: return self.usages[name]
    except KeyError:
      u = self.usages[name] = Usage()
      return u


  def add_decl(self, name:str, node:Sem, *, kind:UsageKind|None=None) -> None:
    u = self.get_or_add_usage(name)
    if u.decl is None: u.decl = node
    if u.kind is None and kind is not None: u.kind = kind


  def add_store(self, name:str, node:Sem, *, kind:UsageKind) -> None:
    u = self.get_or_add_usage(name)
    if u.store is None: u.store = node
    if u.kind is None: u.kind = kind


  def add_load(self, name:str, node:Sem) -> None:
    u = self.get_or_add_usage(name)
    if u.load is None: u.load = node


  def add_delete(self, name:str, node:Sem) -> None:
    u = self.get_or_add_usage(name)
    if u.delete is None: u.delete = node


  def add_import(self, local:str, qualified:str, node:Sem) -> None:
    self.add_store(local, node, kind='import')
    if local not in self.imports:
      self.imports[local] = qualified


  def free_names(self) -> dict[str,Usage]:
    'Names that are only loaded/deleted -- not locally defined.'
    return {n: u for n, u in self.usages.items() if not u.is_local}


  def local_names(self) -> dict[str,Usage]:
    'Names that are stored or declared in this scope.'
    return {n: u for n, u in self.usages.items() if u.is_local}



  def render(self, source:Source, indent:str='') -> Iterator[str]:
    prefix = f'{source.name}:{self.node.line_num}:{self.node.col_num}:{indent}'
    yield f'{prefix} {self.kind} {self.name!r}'

    if self.imports:
      for local, qualified in sorted(self.imports.items()):
        yield f'{prefix}  import: {local} = {qualified}'

    locals_ = {n: u for n, u in self.usages.items() if u.is_local and n not in self.imports}
    if locals_:
      for name, usage in sorted(locals_.items()):
        node = usage.store or usage.decl
        assert node is not None
        assert usage.kind is not None
        yield f'{prefix}  local {usage.kind}: {name} [:{node.line_num}]'

    free = self.free_names()
    if free:
      groups:dict[FreeKind,list[str]] = {}
      for name in sorted(free):
        groups.setdefault(self.free_kind(name), []).append(name)
      for free_kind in ('builtin', 'global', 'free', 'unknown'):
        if names := groups.get(free_kind):
          yield f'{prefix}  {free_kind}: {" ".join(names)}'

    sub_indent = indent + '  '

    for child in self.children:
      yield from child.render(source, sub_indent)



def build_scope_info(module:SemModule, name:str='<module>', source:Source|None=None) -> ScopeInfo:
  '''
  Build a ScopeInfo tree for a module, performing a single top-down traversal.
  If `source` is provided (it must be the same text that `module` was parsed from),
  the stdlib `symtable` tables are computed and attached to the corresponding scopes.
  '''
  scope = ScopeInfo(name=name, kind='module', node=module)
  for el in module.body:
    _visit(el, scope)
  if source is not None:
    table = build_symtable(source.text, source.name, 'exec')
    scope.table = table
    index:_TableIndex = {}
    _index_tables(table, index)
    _attach_tables(scope, index)
  return scope


# Symtable attachment.
# The symtable tree does not align one-to-one with the ScopeInfo tree:
# comprehensions are inlined into their enclosing table (PEP 709),
# while type parameter lists, type alias values, and annotations get implicit wrapper tables (PEP 695 / PEP 649).
# We therefore match tables to scopes by (type, name, lineno) over a flattened index,
# using per-key FIFO order to disambiguate collisions (e.g. two lambdas on one line);
# both trees enumerate in source order under depth-first traversal.

type _TableIndex = dict[tuple[str,str,int],deque[SymbolTable]]

_scope_table_names:dict[ScopeKind,tuple[str,str|None]] = { # ScopeKind -> (table type, fixed table name or None for scope name).
  'class': ('class', None),
  'def': ('function', None),
  'async def': ('function', None),
  'lambda': ('function', 'lambda'),
  'generator': ('function', 'genexpr'),
}


def _index_tables(table:SymbolTable, index:_TableIndex) -> None:
  for child in table.get_children():
    key = (str(child.get_type()), child.get_name(), child.get_lineno())
    index.setdefault(key, deque()).append(child)
    _index_tables(child, index)


def _attach_tables(scope:ScopeInfo, index:_TableIndex) -> None:
  if entry := _scope_table_names.get(scope.kind):
    type_str, fixed_name = entry
    key = (type_str, fixed_name or scope.name, scope.node.line_num)
    try: scope.table = index[key].popleft()
    except (KeyError, IndexError) as e:
      raise LookupError(f'No symtable found for scope {scope.kind} {scope.name!r} at line {scope.node.line_num}.') from e
  for child in scope.children:
    _attach_tables(child, index)


@singledispatch
def _visit(node:Sem, scope:ScopeInfo) -> None:
  if isinstance(node, SemModule):
    raise TypeError(f'Cannot visit SemModule: {node}')
  # Leaf Sem types with no children (SemPass, SemBreak, SemContinue, etc.) get skipped.


@_visit.register
def _(node:SemNode, scope:ScopeInfo) -> None:
  for el in node.els:
    _visit(el, scope)


@_visit.register
def _(node:SemFunctionDef, scope:ScopeInfo) -> None:
  _visit_fn_node(node, 'def', scope)


@_visit.register
def _(node:SemAsyncFunctionDef, scope:ScopeInfo) -> None:
  _visit_fn_node(node, 'async def', scope)


@_visit.register
def _(node:SemClassDef, scope:ScopeInfo) -> None:
  scope.add_store(node.name, node, kind='class')
  el:Sem
  for el in node.decorator_list: _visit(el, scope)
  for el in node.type_params: _visit(el, scope)
  for el in node.bases: _visit(el, scope)
  for el in node.keywords: _visit(el, scope)
  child = scope.add_child(ScopeInfo(name=node.name, kind='class', node=node))
  for el in node.body: _visit(el, child)


@_visit.register
def _(node:SemLambda, scope:ScopeInfo) -> None:
  _visit_fn_outer(node.args, None, scope)
  child = scope.add_child(ScopeInfo(name='<lambda>', kind='lambda', node=node))
  _add_fn_params(node.args, child)
  _visit(node.body, child)


def _visit_comp_node(node:SemListComp|SemSetComp|SemDictComp, scope:ScopeInfo) -> None:
  child = scope.add_child(ScopeInfo(name='<comprehension>', kind='comprehension', node=node))
  _visit_comp(node, scope, child)

_visit.register(SemListComp)(_visit_comp_node)
_visit.register(SemSetComp)(_visit_comp_node)
_visit.register(SemDictComp)(_visit_comp_node)


@_visit.register
def _(node:SemGeneratorExp, scope:ScopeInfo) -> None:
  child = scope.add_child(ScopeInfo(name='<generator>', kind='generator', node=node))
  _visit_comp(node, scope, child)


@_visit.register
def _(node:SemImport, scope:ScopeInfo) -> None:
  for alias in node.names:
    if isinstance(alias, SemAlias):
      root_name = alias.name.split('.')[0]
      local = alias.asname if alias.asname else root_name
      qualified = alias.name if alias.asname else root_name
      scope.add_import(local, qualified, alias)


@_visit.register
def _(node:SemImportFrom, scope:ScopeInfo) -> None:
  dot_prefix = '.' * (node.level or 0)
  mod = node.module or ''
  for alias in node.names:
    if isinstance(alias, SemAlias):
      if alias.name == '*':
        scope.has_star_import = True
        continue
      local = alias.asname if alias.asname else alias.name
      qualified = f'{dot_prefix}{mod}.{alias.name}' if mod else f'{dot_prefix}{alias.name}'
      scope.add_import(local, qualified, alias)


@_visit.register
def _(node:SemAugAssign, scope:ScopeInfo) -> None:
  # An augmented assignment both loads and stores its target, although the AST gives the target a plain store context.
  _visit(node.value, scope)
  if isinstance(node.target, SemName):
    scope.add_load(node.target.id, node.target)
    scope.add_store(node.target.id, node.target, kind='variable')
  else:
    _visit(node.target, scope)


@_visit.register
def _(node:SemAnnAssign, scope:ScopeInfo) -> None:
  _visit(node.annotation, scope)
  if node.value is not None:
    _visit(node.target, scope)
    _visit(node.value, scope)
  else:
    if isinstance(node.target, SemName):
      scope.add_decl(node.target.id, node, kind='annotation')


@_visit.register
def _(node:SemGlobal, scope:ScopeInfo) -> None:
  for name in node.names:
    scope.add_decl(name, node, kind='global')


@_visit.register
def _(node:SemNonlocal, scope:ScopeInfo) -> None:
  for name in node.names:
    scope.add_decl(name, node, kind='nonlocal')


@_visit.register
def _(node:SemExceptHandler, scope:ScopeInfo) -> None:
  if node.name:
    scope.add_store(node.name, node, kind='exception')
  if node.type: _visit(node.type, scope)
  for el in node.body: _visit(el, scope)


@_visit.register
def _(node:SemMatchAs, scope:ScopeInfo) -> None:
  # MatchAs covers bare capture patterns, wildcards, and `<pattern> as <name>`.
  for el in node.els: _visit(el, scope) # The optional sub-pattern.
  if node.name: scope.add_store(node.name, node, kind='pattern')


@_visit.register
def _(node:SemMatchStar, scope:ScopeInfo) -> None:
  if node.name: scope.add_store(node.name, node, kind='pattern')


@_visit.register
def _(node:SemMatchMapping, scope:ScopeInfo) -> None:
  for el in node.els: _visit(el, scope) # The keys and patterns.
  if node.rest: scope.add_store(node.rest, node, kind='pattern')


@_visit.register
def _(node:SemNamedExpr, scope:ScopeInfo) -> None:
  # A walrus assignment inside a comprehension or generator binds in the nearest enclosing real scope.
  _visit(node.value, scope)
  if isinstance(node.target, SemName):
    scope.binding_scope().add_store(node.target.id, node.target, kind='variable')


@_visit.register
def _(node:SemName, scope:ScopeInfo) -> None:
  match node.ctx:
    case 'load': scope.add_load(node.id, node)
    case 'store': scope.add_store(node.id, node, kind='variable')
    case 'del': scope.add_delete(node.id, node)


def _visit_fn_node(node:SemFunctionDef|SemAsyncFunctionDef, kind:Literal['def', 'async def'], scope:ScopeInfo) -> None:
  scope.add_store(node.name, node, kind=kind)
  el:Sem
  for el in node.decorator_list: _visit(el, scope)
  for el in node.type_params: _visit(el, scope)
  _visit_fn_outer(node.args, node.returns, scope)
  child = scope.add_child(ScopeInfo(name=node.name, kind=kind, node=node))
  _add_fn_params(node.args, child)
  for el in node.body: _visit(el, child)


def _visit_fn_outer(sem_args:SemArguments, returns:Sem|None, scope:ScopeInfo) -> None:
  'Visit the parts of a function/lambda that are evaluated in the outer scope: arg annotations and defaults.'
  all_args = [*sem_args.posonlyargs, *sem_args.args]
  if sem_args.vararg: all_args.append(sem_args.vararg)
  all_args.extend(sem_args.kwonlyargs)
  if sem_args.kwarg: all_args.append(sem_args.kwarg)
  for a in all_args:
    if isinstance(a, SemArg) and a.annotation:
      _visit(a.annotation, scope)
  for d in sem_args.defaults: _visit(d, scope)
  for kd in sem_args.kw_defaults:
    if kd is not None: _visit(kd, scope)
  if returns: _visit(returns, scope)


def _add_fn_params(sem_args:SemArguments, scope:ScopeInfo) -> None:
  'Register all parameters as stores in the function/lambda scope.'
  all_args = [*sem_args.posonlyargs, *sem_args.args]
  if sem_args.vararg: all_args.append(sem_args.vararg)
  all_args.extend(sem_args.kwonlyargs)
  if sem_args.kwarg: all_args.append(sem_args.kwarg)
  for a in all_args:
    if isinstance(a, SemArg):
      scope.add_store(a.arg, a, kind='parameter')


def _visit_comp(node:SemListComp|SemSetComp|SemDictComp|SemGeneratorExp, outer:ScopeInfo, inner:ScopeInfo) -> None:
  'Visit a comprehension: first generator iter goes to outer scope, rest to inner.'
  first = True
  for comp in node.generators:
    if isinstance(comp, SemComprehension):
      if first:
        _visit(comp.iter, outer)  # First iter is in outer scope.
        first = False
        _visit(comp.target, inner)
        for cond in comp.ifs: _visit(cond, inner)
      else:
        _visit(comp, inner)
  # The elt/key/value expressions belong in the inner scope.
  if isinstance(node, SemDictComp):
    _visit(node.key, inner)
    _visit(node.value, inner)
  else:
    _visit(node.elt, inner)


# -- iter_scope_tree --

def iter_scope_tree(root:ScopeInfo, *, kinds:set[ScopeKind]|None=None) -> Iterator[ScopeInfo]:
  'Yield all scopes in the tree, depth-first. If `kinds` is given, yield only matching kinds.'
  if kinds is None or root.kind in kinds:
    yield root
  for child in root.children:
    yield from iter_scope_tree(child, kinds=kinds)


# -- Legacy helpers (kept for backward compatibility with existing tests) --

def dotted_name(ref:SemRef) -> str|None:
  'Return the dotted name for a simple name or attribute-chain ref, or None if the chain is not simple.'
  if isinstance(ref, SemName):
    return ref.id
  if isinstance(ref, SemAttribute):
    if isinstance(ref.value, SemRef):
      prefix = dotted_name(ref.value)
      if prefix is not None:
        return f'{prefix}.{ref.attr}'
  return None


def build_import_map(module:SemModule) -> dict[str,str]:
  '''
  Return a mapping of local alias to fully-qualified name for all imports in `module`.
  Relative imports are represented with leading dots, e.g. `from ..sem import Foo` -> `{'Foo': '..sem.Foo'}`.
  '''
  result:dict[str,str] = {}
  for el in module.body:
    if isinstance(el, SemImport):
      for alias in el.names:
        if isinstance(alias, SemAlias):
          root = alias.name.split('.')[0]
          local = alias.asname if alias.asname else root
          qualified = alias.name if alias.asname else root
          result[local] = qualified
    elif isinstance(el, SemImportFrom):
      dot_prefix = '.' * (el.level or 0)
      mod = el.module or ''
      for alias in el.names:
        if isinstance(alias, SemAlias):
          if alias.name == '*': continue
          local = alias.asname if alias.asname else alias.name
          qualified = f'{dot_prefix}{mod}.{alias.name}' if mod else f'{dot_prefix}{alias.name}'
          result[local] = qualified
  return result


def dependencies(node:SemNode, import_map:dict[str,str]) -> frozenset[str]:
  'Return fully-qualified names that `node` depends on, resolved via `import_map`.'
  deps:set[str] = set()
  for ref in node.iter_refs():
    if ref.ctx != 'load':
      continue
    name = dotted_name(ref)
    if name is None:
      continue
    root = name.split('.')[0]
    qualified_root = import_map.get(root)
    if qualified_root is None:
      continue
    deps.add(qualified_root + name[len(root):])
  return frozenset(d for d in deps if not any(other.startswith(d + '.') for other in deps))
