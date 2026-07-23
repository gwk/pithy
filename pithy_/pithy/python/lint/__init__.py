# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
A simple Python linter meant to work in conjunction with mypy.

The linter is built on the `pithy.python.sem` scope analysis, which is in turn backed by the stdlib `symtable`.
It checks name usages within each scope:
* private module variables that are never used;
* function locals that are never used;
* references to names that are never defined;
* pointless or unused `global`/`nonlocal` declarations.

Class scopes get no unused checks because class names have attribute semantics:
they may be used via attribute access, which is not tracked here.
'''

from tolkien import Source

from ..ast_utils import fmt_syntax_error
from ..sem import Sem, sem_for_source
from ..sem.scopes import build_scope_info, ScopeInfo, Usage


module_implicit_names = frozenset((
  '__annotations__', '__builtins__', '__cached__', '__doc__', '__file__', '__loader__', '__name__', '__package__',
  '__path__', '__spec__'))
#^ Names implicitly defined in module namespaces; not all of them are attributes of the builtins module.


def lint_path(path:str) -> None:
  with open(path) as f:
    for msg in lint_source(name=path, text=f.read()):
      print(msg)


def lint_source(name:str, text:str) -> list[str]:
  source = Source(name=name, text=text)
  try:
    module = sem_for_source(source)
    root = build_scope_info(module, source=source)
  except SyntaxError as e:
    return [fmt_syntax_error(source.name, e)]
  linter = Linter(root=root)
  linter.lint()
  return [f'{source.name}:{node.line_num}: {msg}' for node, msg in linter.issues]


def lint_text(text:str) -> str:
  return '\n'.join(lint_source(name='<str>', text=text))


def is_private(name:str) -> bool:
  'True for single-underscore-prefixed names; bare `_` and dunder names are not considered private.'
  return name != '_' and name.startswith('_') and not name.startswith('__')


class Linter:
  '''
  Checks name usages over a ScopeInfo tree.
  A credit pre-pass marks loads and stores of names in the outer scopes where they bind
  (free variables, inlined comprehension locals, and global/nonlocal declarations);
  the check pass then examines each scope's usages.
  '''

  def __init__(self, root:ScopeInfo) -> None:
    self.root = root
    self.issues:list[tuple[Sem,str]] = []
    self.credited_loads:set[tuple[int,str]] = set() # (id(scope), name).
    self.credited_stores:set[tuple[int,str]] = set() # (id(scope), name).


  def warn(self, node:Sem, msg:str) -> None:
    self.issues.append((node, msg))


  def lint(self) -> None:
    self._credit_outer_uses(self.root)
    self._check_scope(self.root)
    self.issues.sort(key=lambda issue: (issue[0].line_num, issue[0].col_num, issue[1]))


  def _credit_outer_uses(self, scope:ScopeInfo) -> None:
    for name, usage in scope.usages.items():
      if usage.decl is not None and usage.kind in ('global', 'nonlocal'):
        if scope is not self.root and (usage.load is not None or usage.store is not None):
          target = self.root if usage.kind == 'global' else self._free_binding_scope(scope, name)
          if target is not None:
            self.credited_loads.add((id(target), name)) # Any use through the declaration marks the outer binding as used.
            if usage.store is not None: self.credited_stores.add((id(target), name))
      elif usage.load is not None and not usage.is_local:
        load_scope:ScopeInfo|None = None
        match scope.free_kind(name):
          case 'global': load_scope = self.root
          case 'builtin': pass
          case _: load_scope = self._free_binding_scope(scope, name) # 'free', or 'unknown' e.g. inlined comprehension loads.
        if load_scope is not None:
          self.credited_loads.add((id(load_scope), name))
    for child in scope.children:
      self._credit_outer_uses(child)


  def _free_binding_scope(self, scope:ScopeInfo, name:str) -> ScopeInfo|None:
    'The nearest enclosing scope where `name` is locally bound. Class scopes do not provide bindings to nested scopes.'
    s = scope.parent
    while s is not None:
      if s.kind != 'class':
        u = s.usages.get(name)
        if u is not None and u.is_local: return s
      s = s.parent
    return None


  def _is_defined_at_module(self, name:str) -> bool:
    u = self.root.usages.get(name)
    if u is not None and u.is_local: return True
    if (id(self.root), name) in self.credited_stores: return True # Stored via a `global` declaration in some function.
    return name in module_implicit_names


  def _check_scope(self, scope:ScopeInfo) -> None:
    for name, usage in scope.usages.items():
      self._check_usage(scope, name, usage)
    for child in scope.children:
      self._check_scope(child)


  def _check_usage(self, scope:ScopeInfo, name:str, usage:Usage) -> None:
    if usage.decl is not None and usage.kind in ('global', 'nonlocal'):
      self._check_decl_usage(scope, name, usage)
    elif usage.is_local:
      self._check_unused(scope, name, usage)
    elif usage.load is None and usage.delete is not None:
      self.warn(usage.delete, f'deleted variable `{name}` never defined.')
    elif (usage.load is not None and not self.root.has_star_import
      and scope.free_kind(name) == 'global' and not self._is_defined_at_module(name)):
      self.warn(usage.load, f'variable `{name}` never defined.')


  def _check_decl_usage(self, scope:ScopeInfo, name:str, usage:Usage) -> None:
    decl = usage.decl
    assert decl is not None
    if scope.kind == 'module':
      self.warn(decl, f'{usage.kind} declaration `{name}` in module scope.')
      #^ Note: `nonlocal` at module scope is a SyntaxError reported at parse/compile time; only `global` reaches here.
    elif usage.load is None and usage.store is None:
      self.warn(decl, f'{usage.kind} variable `{name}` never used.')


  def _check_unused(self, scope:ScopeInfo, name:str, usage:Usage) -> None:
    if usage.load is not None or (id(scope), name) in self.credited_loads: return
    match scope.kind:
      case 'module':
        if usage.kind == 'variable' and is_private(name):
          self.warn(usage.primary_node, f'private variable `{name}` in module scope never used.')
      case 'def' | 'async def' | 'lambda':
        if usage.kind != 'parameter' and not name.startswith('_'):
          self.warn(usage.primary_node, f'local {usage.kind} `{name}` never used.')
      case _: pass
      #^ Class scopes are exempt per the module docstring. Comprehension targets are structural and often unused.
