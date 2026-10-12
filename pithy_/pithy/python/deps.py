# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Module and symbol dependency analysis for Python code.

`DepGraph` builds a two-layer dependency graph over a set of target modules:
* The module import layer: which modules each module imports.
* The symbol layer: which top-level symbols (functions and classes) reference which symbols across modules.

Modules are parsed lazily, driven by the query:
* `-dependencies X` parses only the module of X.
* `-dependents X` parses all targets to obtain the import layer,
  then performs symbol analysis only on the modules whose imports relate to X.
* The default summary prints the full import graph over the targets, followed by the dependency/dependent tips.

Symbol dependencies are inferred by straightforward static lexical interpretation, not type inference:
each name or attribute chain loaded within a definition is resolved through the enclosing scopes built by
`pithy.python.sem.scopes` to a scope-local import, a module-level import or a module-level binding.
Attribute chains through module imports resolve to the accessed symbol, e.g. `import pkg.mod; pkg.mod.f()` records `pkg.mod.f`.
Methods and nested classes are separate symbols such as `Cls.method`; each reference keeps its source position.
Module-level statements outside any definition belong to the pseudo-symbol `<module>`.
Names in string annotations are not analyzed.
Dotted targets resolve statically through the running Python environment; see `pithy.python.package.resolve_module_installed`.
The import and symbol layers resolve against the target roots only.
'''

from sys import stdlib_module_names
from typing import Callable, Iterable, NamedTuple

from tolkien import Source

from ..ansi import BOLD_OUT, RST_OUT, TXT_B_OUT, TXT_G_OUT, TXT_Y_OUT
from ..cmdparse import Cmd, flag, opt, pos
from ..dict import dict_dag_inverse_with_all_keys
from ..filestatus import is_dir
from ..fs import abs_path, path_rel_to_current_or_abs
from ..io import outL
from ..path import path_join
from .ast_utils import fmt_syntax_error
from .package import (module_name_for_path, qualname_rel_to, resolve_module_in_dirs, resolve_module_installed,
  resolve_spec_paths, safe_path_help, SpecResolutionError, target_resolution_help)
from .sem import (Sem, sem_for_source, SemArguments, SemAsyncFunctionDef, SemAttribute, SemClassDef, SemDictComp,
  SemFunctionDef, SemGeneratorExp, SemImport, SemImportFrom, SemLambda, SemListComp, SemModule, SemName, SemNode, SemScope,
  SemSetComp)
from .sem.scopes import build_scope_info, iter_scope_tree, ScopeInfo


_context_keywords_ = ['call graph', 'callers', 'dependencies', 'dependents', 'import graph', 'imports', 'references',
  'symbols', 'usages', 'who calls']


class DepsCmd(Cmd):
  '''
  Analyze Python module and symbol dependencies.
  The targets form the universe for the summary and for dependents queries; a dependencies query parses only the named module.
  Without targets, a query's universe defaults to the top-level package containing the queried module,
  resolved through the Python environment; uses in other packages, test trees or dependent projects need explicit targets.
  Directory and package targets omit `.ut.py` unit test files unless `-include-utests` is given.
  '''

  help_addenda = (target_resolution_help, safe_path_help)

  targets:list[str] = pos(default_factory=list,
    doc='File paths, directories, and/or dotted module names to analyze; a query defaults to the package of the queried module.')
  safe_path:bool = flag('-P', doc='Use safe-path target resolution.')
  include_utests:bool = flag(doc='Include `.ut.py` unit test files when walking directories and packages.')
  sites:bool = flag(default=True, doc='For a symbol dependents query, show each referencing source line; `-no-sites` omits them.')
  dependencies:str|None = opt(default=None, metavar='NAME', doc='Show dependencies of a module or module.symbol.')
  dependents:str|None = opt(default=None, metavar='NAME', doc='Show dependents of a module or module.symbol.')


  def run(self) -> None:
    graph = DepGraph(safe_path=self.safe_path, include_utests=self.include_utests)
    try:
      targets = self.targets
      if not targets:
        spec = self.dependencies or self.dependents
        if not spec: raise DepsError('a summary requires targets.')
        targets = [default_universe(spec, safe_path=self.safe_path)]
      for target in targets:
        graph.add_target(target)
      if self.dependencies: print_dependencies(graph, self.dependencies)
      elif self.dependents: print_dependents(graph, self.dependents, sites=self.sites)
      else: print_summary(graph)
    except DepsError as e:
      exit(f'pithy.python.deps error: {e}')


def main() -> None: DepsCmd.main()


def default_universe(spec:str, *, safe_path:bool=False, resolve_module:Callable[[str],str|None]|None=None) -> str:
  '''
  The default target universe for a query: the top-level package directory containing the module of `spec`,
  or the module file itself when it is not in a package.
  The module is the longest dotted prefix of `spec` that resolves, through the Python environment by default.
  '''
  if resolve_module is None: resolve_module = lambda name: resolve_module_installed(name, safe_path=safe_path)
  parts = spec.split('.')
  for i in range(len(parts), 0, -1):
    path = resolve_module('.'.join(parts[:i]))
    if path is None: continue
    name, search_dir = module_name_for_path(path)
    top_dir = path_join(search_dir, name.partition('.')[0])
    return top_dir if is_dir(top_dir, follow=True) else path
  raise DepsError(f'cannot resolve module for {spec!r}; give targets explicitly.')


DEP_RANK_COLORS = (TXT_B_OUT, TXT_Y_OUT, TXT_G_OUT) # Stdlib, third-party, first-party.


def fmt_deps(graph:'DepGraph', base:str, deps:Iterable[str]) -> str:
  '''
  Format dependency names sorted by rank then name: stdlib first, then third-party, then first-party (the target packages).
  Each rank is colored: stdlib blue, third-party yellow, first-party green.
  First-party names are shortened to their possibly-relative form with respect to the `base` module.
  '''
  ranked = sorted((graph.dep_rank(dep), dep) for dep in deps)
  parts = []
  for rank, dep in ranked:
    text = qualname_rel_to(base, dep) if rank == 2 else dep
    parts.append(f'{DEP_RANK_COLORS[rank]}{text}{RST_OUT}')
  return '  '.join(parts)


def print_summary(graph:'DepGraph') -> None:
  'Print the module import graph over all target modules, followed by the dependency/dependent tips.'
  module_deps = {name: graph.module_deps(name) for name in sorted(graph.targets)}
  internal_deps = {name: {d for d in deps if d in module_deps} for name, deps in module_deps.items()}
  dependents = dict_dag_inverse_with_all_keys(internal_deps)

  outL(BOLD_OUT, 'Modules with dependencies:', RST_OUT)
  for name, deps in module_deps.items():
    if deps: outL(BOLD_OUT, name, RST_OUT, ': ', fmt_deps(graph, name, deps))

  outL('\n', BOLD_OUT, 'Modules without internal dependencies:', RST_OUT)
  no_deps = [name for name, deps in internal_deps.items() if not deps]
  outL('  '.join(no_deps) if no_deps else '*none*')

  outL('\n', BOLD_OUT, 'Modules without dependents:', RST_OUT)
  no_dpdts = sorted(name for name, dpdts in dependents.items() if not dpdts)
  outL('  '.join(no_dpdts) if no_dpdts else '*none*')


def print_dependencies(graph:'DepGraph', spec:str) -> None:
  mod, sym = graph.split_spec(spec)
  if graph.resolve_module(mod) is None:
    raise DepsError(f'cannot resolve module for {spec!r}.')

  if sym is None:
    outL(BOLD_OUT, f'Module dependencies of {mod}:', RST_OUT)
    deps = graph.module_deps(mod)
    outL(fmt_deps(graph, mod, deps) if deps else '*none*')

  symbol_deps = graph.symbol_deps(mod)
  if sym is not None: # A symbol query includes its members, e.g. the methods of a class.
    selected = {s: deps for s, deps in symbol_deps.items() if s == sym or s.startswith(sym + '.')}
    if not selected: raise DepsError(f'module {mod!r} has no analyzed symbol {sym!r}.')
    outL(BOLD_OUT, f'Symbol dependencies of {mod}.{sym}:', RST_OUT)
  else:
    selected = symbol_deps
    outL('\n', BOLD_OUT, f'Symbol dependencies within {mod}:', RST_OUT)
  found = False
  for s, sym_deps in sorted(selected.items()):
    if sym_deps:
      outL(BOLD_OUT, f'{mod}.{s}', RST_OUT, ': ', fmt_deps(graph, mod, sym_deps))
      found = True
  if not found: outL('*none*')


def print_dependents(graph:'DepGraph', spec:str, *, sites:bool=True) -> None:
  '''
  Print the modules importing the target module, then the symbols that reference the target.
  For a symbol target, each referencing symbol is followed by its reference sites as `path:line: source` lines when `sites` is set.
  '''
  mod, sym = graph.split_spec(spec)
  target = f'{mod}.{sym}' if sym else mod
  module_deps = {name: graph.module_deps(name) for name in sorted(graph.targets)} # The import layer requires parsing all targets.

  importers = [name for name, deps in module_deps.items()
    if name != mod and any(d == mod or d.startswith(mod + '.') for d in deps)]
  outL(BOLD_OUT, f'Modules importing {mod}:', RST_OUT)
  outL('  '.join(importers) if importers else '*none*')

  # The symbol layer analyzes the target module itself, for same-module references,
  # plus the candidate modules whose imports relate to the target module.
  candidates = [name for name, deps in module_deps.items()
    if name == mod or any(d == mod or d.startswith(mod + '.') or mod.startswith(d + '.') for d in deps)]
  outL('\n', BOLD_OUT, f'Symbol dependents of {target}:', RST_OUT)
  found = False
  for name in candidates:
    for s, refs in sorted(graph.symbol_refs(name).items()):
      matching = [ref for ref in refs if ref.qual == target or ref.qual.startswith(target + '.')]
      if not matching: continue
      outL(BOLD_OUT, f'{name}.{s}', RST_OUT, ': ', fmt_deps(graph, name, {ref.qual for ref in matching}))
      found = True
      if sym and sites:
        rel_path = path_rel_to_current_or_abs(graph.paths[name])
        for line in sorted({ref.line for ref in matching}):
          outL(f'  {rel_path}:{line}: {graph.source_line(name, line)}')
  if not found: outL('*none*')


class DepsError(Exception):
  'An error in dependency analysis: unresolvable targets or syntax errors in analyzed modules.'


class DepGraph:
  '''
  A lazy, two-layer dependency graph over a set of target modules.
  Targets establish the universe for summary and dependents queries;
  modules are parsed and analyzed on demand and cached.
  '''

  def __init__(self, *, safe_path:bool=False, include_utests:bool=False) -> None:
    self.safe_path = safe_path
    self.include_utests = include_utests
    self.search_dirs:list[str] = [] # Explicit target roots used for dependency analysis.
    self.targets:dict[str,str] = {} # Target module name -> file path.
    self.paths:dict[str,str] = {} # Resolved module name -> file path; superset of `targets`.
    self._scopes:dict[str,ScopeInfo] = {}
    self._lines:dict[str,list[str]] = {} # Module name -> source lines, for reference sites.
    self._module_deps:dict[str,frozenset[str]] = {}
    self._symbol_refs:dict[str,dict[str,list[Ref]]] = {}
    self._symbol_deps:dict[str,dict[str,frozenset[str]]] = {}


  def add_target(self, spec:str) -> None:
    'Add a target: a file path, a directory of Python files, or a dotted module name.'
    try: paths = resolve_spec_paths(spec, self.resolve_target_module, safe_path=self.safe_path, include_utests=self.include_utests)
    except SpecResolutionError as e: raise DepsError(str(e)) from None
    for path in paths:
      self.add_file(path)


  def add_file(self, path:str) -> None:
    path = abs_path(path)
    name, search_dir = module_name_for_path(path)
    if search_dir not in self.search_dirs: self.search_dirs.append(search_dir)
    self.paths.setdefault(name, path)
    self.targets.setdefault(name, path)


  def resolve_target_module(self, name:str) -> str|None:
    '''
    Resolve a dotted target module name through the Python environment, independent of earlier targets.
    Installed packages are only consulted for targets, so that the dependency layers resolve against the target roots alone.
    '''
    return resolve_module_installed(name, safe_path=self.safe_path)


  def resolve_module(self, name:str) -> str|None:
    'Resolve a dotted module name to a file path by searching the known roots; returns None if not found.'
    try: return self.paths[name]
    except KeyError: pass
    path = resolve_module_in_dirs(name, self.search_dirs)
    if path is not None: self.paths[name] = path
    return path


  def dep_rank(self, dep:str) -> int:
    '''
    Rank a dependency name for display: 0 for stdlib, 2 for first-party (within the target packages), 1 for all others.
    Only the top-level name is considered.
    '''
    top = dep.partition('.')[0]
    if top in stdlib_module_names: return 0
    if any(target.partition('.')[0] == top for target in self.targets): return 2
    return 1


  def is_package(self, name:str) -> bool:
    path = self.resolve_module(name)
    return path is not None and path.endswith('__init__.py')


  def split_spec(self, spec:str) -> tuple[str,str|None]:
    '''
    Interpret a query spec as a module name or a (module, symbol) pair.
    An unresolvable spec is treated as an external module name.
    '''
    if self.resolve_module(spec) is not None: return spec, None
    parts = spec.split('.')
    for i in range(len(parts) - 1, 0, -1): # The longest resolvable prefix is the module; the rest is a dotted symbol.
      mod = '.'.join(parts[:i])
      if self.resolve_module(mod) is not None: return mod, '.'.join(parts[i:])
    return spec, None


  def scope(self, name:str) -> ScopeInfo:
    'Parse the module and build its ScopeInfo tree; lazy and cached.'
    try: return self._scopes[name]
    except KeyError: pass
    path = self.resolve_module(name)
    if path is None: raise DepsError(f'cannot resolve module {name!r}.')
    source = Source.from_path(path)
    try:
      module = sem_for_source(source)
      root = build_scope_info(module, name=name, source=source)
    except SyntaxError as e:
      raise DepsError(fmt_syntax_error(path, e)) from e
    self._scopes[name] = root
    self._lines[name] = source.text.split('\n')
    return root


  def source_line(self, name:str, line:int) -> str:
    'The text of a 1-based source line of an analyzed module.'
    return self._lines[name][line-1]


  def resolve_relative(self, importer:str, module:str|None, level:int) -> str:
    'Resolve a possibly-relative import to an absolute dotted module name, relative to the `importer` module.'
    if not level: return module or ''
    parts = importer.split('.')
    if not self.is_package(importer): parts.pop()
    if level > 1: parts = parts[:-(level-1)]
    base = '.'.join(parts)
    if base and module: return f'{base}.{module}'
    return module or base


  def resolve_qual(self, importer:str, qual:str) -> str:
    'Resolve a qualified name that may have leading relative-import dots to an absolute dotted name.'
    if not qual.startswith('.'): return qual
    stripped = qual.lstrip('.')
    level = len(qual) - len(stripped)
    base = self.resolve_relative(importer, None, level)
    if base and stripped: return f'{base}.{stripped}'
    return stripped or base


  def module_deps(self, name:str) -> frozenset[str]:
    '''
    The import-layer dependencies of a module: the absolute dotted names of all modules it imports, in any scope.
    For `from x import y`, the dependency is `x.y` when that resolves to a module file, else `x`.
    '''
    try: return self._module_deps[name]
    except KeyError: pass
    root = self.scope(name)
    deps:set[str] = set()
    for node in root.node.walk():
      if isinstance(node, SemImport):
        for alias in node.names:
          deps.add(alias.name)
      elif isinstance(node, SemImportFrom):
        mod = self.resolve_relative(name, node.module, node.level or 0)
        for alias in node.names:
          dep = mod
          if alias.name != '*':
            qual = f'{mod}.{alias.name}' if mod else alias.name
            if self.resolve_module(qual) is not None: dep = qual
          if dep: deps.add(dep)
    result = frozenset(deps)
    self._module_deps[name] = result
    return result


  def symbol_refs(self, name:str) -> dict[str,list[Ref]]:
    '''
    The symbol-layer references of a module: maps each definition qualname to the references it makes, in source order.
    Methods and nested classes are separate symbols, e.g. `Cls.method`; definitions inside functions belong to the function.
    Module-level statements outside any definition belong to the pseudo-symbol `<module>`.
    Each reference names an absolute module or `module.symbol`, both intra-module and through imports.
    '''
    try: return self._symbol_refs[name]
    except KeyError: pass
    root = self.scope(name)
    collector = _RefCollector(self, name, root)
    assert isinstance(root.node, SemModule)
    for stmt in root.node.body:
      collector.walk(stmt, root, module_symbol, top=module_symbol)
    self._symbol_refs[name] = collector.refs
    return collector.refs


  def symbol_deps(self, name:str) -> dict[str,frozenset[str]]:
    'The symbol-layer dependencies of a module: each definition qualname mapped to the set of qualified names it references.'
    try: return self._symbol_deps[name]
    except KeyError: pass
    result = {sym: frozenset(ref.qual for ref in refs) for sym, refs in self.symbol_refs(name).items()}
    self._symbol_deps[name] = result
    return result


  def resolve_import(self, importer:str, qual:str) -> tuple[str,bool]:
    '''
    Resolve an imported qualified name to an absolute name and whether it denotes a module.
    A name is a module if it resolves within the target roots or is a top-level name; otherwise it is taken to be a symbol.
    '''
    abs_qual = self.resolve_qual(importer, qual)
    return abs_qual, '.' not in abs_qual or self.resolve_module(abs_qual) is not None


module_symbol = '<module>' # The pseudo-symbol for module-level statements outside any definition.


class Ref(NamedTuple):
  'A reference from a symbol to an absolute module or symbol name, at a 1-based source position.'
  qual:str
  line:int
  col:int


class _RefCollector:
  '''
  Walk the semantic tree of a module's definitions, mirroring the scope structure of `pithy.python.sem.scopes`,
  and resolve each loaded name or attribute chain against the scopes that enclose it.
  A name resolves through the enclosing scopes, skipping class scopes as Python does, to a scope-local import,
  a module-level import, or a module-level binding; names bound locally along the way, and builtins, are not dependencies.
  An attribute chain rooted at a module extends while each prefix resolves to a module within the target roots,
  then takes one more attribute as the symbol; so `import os; os.path.join` records `os.path` and `pkg.mod.f()` records `pkg.mod.f`.
  '''

  def __init__(self, graph:DepGraph, module:str, root:ScopeInfo) -> None:
    self.graph = graph
    self.module = module
    self.root = root
    self.refs:dict[str,list[Ref]] = {}
    self.scopes = {id(s.node): s for s in iter_scope_tree(root)}


  def child_scope(self, node:SemScope) -> ScopeInfo:
    return self.scopes[id(node)]


  def walk(self, node:Sem, scope:ScopeInfo, sym:str, *, top:str) -> None:
    '''
    Walk `node` within `scope`, attributing references to symbol `sym`; `top` is the top-level symbol name,
    whose own references to itself are not recorded as dependencies.
    '''
    if isinstance(node, SemName):
      if node.ctx == 'load': self.record(scope, sym, [node.id], node, top=top)
    elif isinstance(node, SemAttribute):
      chain = _attr_chain(node)
      if chain is None: self.walk(node.value, scope, sym, top=top)
      else: self.record(scope, sym, chain, node, top=top)
    elif isinstance(node, (SemFunctionDef, SemAsyncFunctionDef)):
      # The signature evaluates in the enclosing scope, but its references belong to the definition's own symbol.
      sym, top = self.def_symbol(node, scope, sym, top)
      for el in (*node.decorator_list, *node.type_params): self.walk(el, scope, sym, top=top)
      self.walk_args_outer(node.args, scope, sym, top=top)
      if node.returns is not None: self.walk(node.returns, scope, sym, top=top)
      child = self.child_scope(node)
      for el in node.body: self.walk(el, child, sym, top=top)
    elif isinstance(node, SemClassDef):
      sym, top = self.def_symbol(node, scope, sym, top)
      for el in (*node.decorator_list, *node.type_params, *node.bases, *node.keywords): self.walk(el, scope, sym, top=top)
      child = self.child_scope(node)
      for el in node.body: self.walk(el, child, sym, top=top)
    elif isinstance(node, SemLambda):
      self.walk_args_outer(node.args, scope, sym, top=top)
      self.walk(node.body, self.child_scope(node), sym, top=top)
    elif isinstance(node, (SemListComp, SemSetComp, SemDictComp, SemGeneratorExp)):
      child = self.child_scope(node)
      for i, comp in enumerate(node.generators):
        self.walk(comp.iter, scope if i == 0 else child, sym, top=top) # Only the first iterable evaluates in the outer scope.
        self.walk(comp.target, child, sym, top=top)
        for cond in comp.ifs: self.walk(cond, child, sym, top=top)
      if isinstance(node, SemDictComp):
        self.walk(node.key, child, sym, top=top)
        if node.value is not None: self.walk(node.value, child, sym, top=top)
      else:
        self.walk(node.elt, child, sym, top=top)
    elif isinstance(node, SemNode):
      for el in node.els: self.walk(el, scope, sym, top=top)


  def def_symbol(self, node:SemFunctionDef|SemAsyncFunctionDef|SemClassDef, scope:ScopeInfo, sym:str, top:str
   ) -> tuple[str,str]:
    '''
    The (symbol, top) pair for a definition encountered in `scope`.
    A module-level definition, even inside a conditional block, starts its own top-level symbol;
    a class member is a sub-symbol of the class; a definition inside a function belongs to the function.
    '''
    if scope is self.root: return node.name, node.name
    if scope.kind == 'class': return f'{sym}.{node.name}', top
    return sym, top


  def walk_args_outer(self, args:SemArguments, scope:ScopeInfo, sym:str, *, top:str) -> None:
    'Walk the parts of a parameter list that evaluate in the enclosing scope: annotations and defaults.'
    for arg in (*args.posonlyargs, *args.args, args.vararg, *args.kwonlyargs, args.kwarg):
      if arg is not None and arg.annotation is not None: self.walk(arg.annotation, scope, sym, top=top)
    for default in (*args.defaults, *args.kw_defaults):
      if default is not None: self.walk(default, scope, sym, top=top)


  def record(self, scope:ScopeInfo, sym:str, chain:list[str], node:Sem, *, top:str) -> None:
    'Resolve a name or attribute chain loaded in `scope` and record the reference for `sym`, if it is a dependency.'
    resolved = self.resolve_root(scope, chain[0])
    if resolved is None: return
    qual, is_module = resolved
    if qual == f'{self.module}.{top}': return # A symbol's references to itself are not dependencies.
    if is_module:
      for attr in chain[1:]:
        qual = f'{qual}.{attr}'
        if self.graph.resolve_module(qual) is None: break # The first non-module attribute is the symbol.
    self.refs.setdefault(sym, []).append(Ref(qual, node.line_num, node.col_num))


  def resolve_root(self, scope:ScopeInfo, name:str) -> tuple[str,bool]|None:
    '''
    Resolve a name loaded in `scope` through its enclosing scopes to an absolute qualified name and whether it is a module.
    Returns None for names bound locally in an enclosing function, builtins and unknown names.
    '''
    s:ScopeInfo|None = scope
    while s is not None and s is not self.root:
      usage = s.usages.get(name)
      if usage is not None and usage.kind == 'global': break
      if usage is not None and usage.is_local:
        if qual := s.imports.get(name): return self.graph.resolve_import(self.module, qual)
        if usage.kind != 'nonlocal': return None
      s = s.parent
      while s is not None and s is not self.root and s.kind == 'class': s = s.parent # Class scopes do not enclose names.
    if qual := self.root.imports.get(name): return self.graph.resolve_import(self.module, qual)
    usage = self.root.usages.get(name)
    if usage is not None and usage.is_local: return f'{self.module}.{name}', False
    return None


def _attr_chain(node:SemAttribute) -> list[str]|None:
  'The dotted names of an attribute chain rooted at a loaded name, e.g. `[os, path, join]`; None for other chains.'
  attrs = [node.attr]
  value = node.value
  while isinstance(value, SemAttribute):
    attrs.append(value.attr)
    value = value.value
  if not isinstance(value, SemName) or value.ctx != 'load': return None
  attrs.append(value.id)
  attrs.reverse()
  return attrs


if __name__ == '__main__': main()
