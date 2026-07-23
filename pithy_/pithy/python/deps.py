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
each name loaded within a symbol's scope subtree is classified using the scope analysis in `pithy.python.sem.scopes`,
then resolved against the module's imports and module-level bindings.

TODO: attribute chains through plain module imports (e.g. `import os; os.path.join`)
are recorded as a dependency on the module only, not on the accessed attribute.
TODO: module-level statements (assignments and expressions) are not attributed to symbols;
only top-level `def`, `async def`, and `class` symbols are analyzed.
TODO: dotted module name targets resolve against the current directory and roots discovered from path targets;
installed packages are not searched.
'''

from sys import stdlib_module_names
from typing import Iterable

from tolkien import Source

from ..ansi import BOLD_OUT, RST_OUT, TXT_B_OUT, TXT_G_OUT, TXT_Y_OUT
from ..argparser import ArgParser
from ..dict import dict_dag_inverse_with_all_keys
from ..fs import abs_path, path_exists, path_join
from ..io import outL
from ..path import path_dir, path_name
from .ast_utils import fmt_syntax_error
from .package import qualname_rel_to, resolve_module_in_dirs, resolve_spec_paths, SpecResolutionError
from .sem import (Sem, sem_for_source, SemAsyncFunctionDef, SemClassDef, SemFunctionDef, SemImport, SemImportFrom, SemName,
  SemScope)
from .sem.scopes import build_scope_info, ScopeInfo


def main() -> None:
  parser = ArgParser(description='Analyze Python module and symbol dependencies.')
  parser.add_argument('targets', nargs='+', help='File paths, directories, and/or dotted module names to analyze.')
  parser.add_argument('-dependencies', metavar='NAME', help='Show dependencies of a module or module.symbol.')
  parser.add_argument('-dependents', metavar='NAME', help='Show dependents of a module or module.symbol.')
  args = parser.parse_args()

  graph = DepGraph()
  try:
    for target in args.targets:
      graph.add_target(target)
    if args.dependencies: print_dependencies(graph, args.dependencies)
    elif args.dependents: print_dependents(graph, args.dependents)
    else: print_summary(graph)
  except DepsError as e:
    exit(f'pithy.python.deps error: {e}')


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
  if sym is not None:
    try: sym_deps = symbol_deps[sym]
    except KeyError: raise DepsError(f'module {mod!r} has no analyzed symbol {sym!r}.') from None
    outL(BOLD_OUT, f'Symbol dependencies of {mod}.{sym}:', RST_OUT)
    outL(fmt_deps(graph, mod, sym_deps) if sym_deps else '*none*')
  else:
    outL('\n', BOLD_OUT, f'Symbol dependencies within {mod}:', RST_OUT)
    for s, sym_deps in sorted(symbol_deps.items()):
      if sym_deps: outL(BOLD_OUT, f'{mod}.{s}', RST_OUT, ': ', fmt_deps(graph, mod, sym_deps))


def print_dependents(graph:'DepGraph', spec:str) -> None:
  mod, sym = graph.split_spec(spec)
  target = f'{mod}.{sym}' if sym else mod
  module_deps = {name: graph.module_deps(name) for name in sorted(graph.targets)} # The import layer requires parsing all targets.

  importers = [name for name, deps in module_deps.items()
    if name != mod and any(d == mod or d.startswith(mod + '.') for d in deps)]
  outL(BOLD_OUT, f'Modules importing {mod}:', RST_OUT)
  outL('  '.join(importers) if importers else '*none*')

  # The symbol layer analyzes only the candidate modules whose imports relate to the target module.
  candidates = [name for name, deps in module_deps.items()
    if name != mod and any(d == mod or d.startswith(mod + '.') or mod.startswith(d + '.') for d in deps)]
  outL('\n', BOLD_OUT, f'Symbol dependents of {target}:', RST_OUT)
  found = False
  for name in candidates:
    for s, deps in sorted(graph.symbol_deps(name).items()):
      matches = [d for d in deps if d == target or d.startswith(target + '.')]
      if matches:
        outL(BOLD_OUT, f'{name}.{s}', RST_OUT, ': ', fmt_deps(graph, name, matches))
        found = True
  if not found: outL('*none*')


class DepsError(Exception):
  'An error in dependency analysis: unresolvable targets or syntax errors in analyzed modules.'


class DepGraph:
  '''
  A lazy, two-layer dependency graph over a set of target modules.
  Targets establish the universe for summary and dependents queries;
  modules are parsed and analyzed on demand and cached.
  '''

  def __init__(self) -> None:
    self.search_dirs:list[str] = [abs_path('.')] # Dirs against which dotted module names are resolved.
    self.targets:dict[str,str] = {} # Target module name -> file path.
    self.paths:dict[str,str] = {} # Resolved module name -> file path; superset of `targets`.
    self._scopes:dict[str,ScopeInfo] = {}
    self._module_deps:dict[str,frozenset[str]] = {}
    self._symbol_deps:dict[str,dict[str,frozenset[str]]] = {}


  def add_target(self, spec:str) -> None:
    'Add a target: a file path, a directory of Python files, or a dotted module name.'
    try: paths = resolve_spec_paths(spec, self.resolve_module)
    except SpecResolutionError as e: raise DepsError(str(e)) from None
    for path in paths:
      self.add_file(path)


  def add_file(self, path:str) -> None:
    path = abs_path(path)
    name, search_dir = module_name_for_path(path)
    if search_dir not in self.search_dirs: self.search_dirs.append(search_dir)
    self.paths.setdefault(name, path)
    self.targets.setdefault(name, path)


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
    mod, _, sym = spec.rpartition('.')
    if mod and self.resolve_module(mod) is not None: return mod, sym
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
    return root


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


  def symbol_deps(self, name:str) -> dict[str,frozenset[str]]:
    '''
    The symbol-layer dependencies of a module: maps each top-level def/class symbol
    to the absolute qualified names it references, both intra-module (`this_module.symbol`)
    and inter-module (via imports).
    '''
    try: return self._symbol_deps[name]
    except KeyError: pass
    root = self.scope(name)
    import_locals = {local: self.resolve_qual(name, qual) for local, qual in root.imports.items()}
    module_locals = frozenset(n for n, u in root.usages.items() if u.is_local)
    symbols:dict[str,set[str]] = {}
    for child in root.children:
      if child.kind not in ('def', 'async def', 'class'): continue
      names:set[str] = set()
      deps:set[str] = set()
      assert isinstance(child.node, SemScope)
      _collect_outer_refs(child.node, names)
      self._collect_scope_refs(child, name, names, deps)
      for n in names:
        if qual := import_locals.get(n): deps.add(qual)
        elif n in module_locals and n != child.name: deps.add(f'{name}.{n}')
      symbols.setdefault(child.name, set()).update(deps)
    result = {s: frozenset(deps) for s, deps in symbols.items()}
    self._symbol_deps[name] = result
    return result


  def _collect_scope_refs(self, scope:ScopeInfo, importer:str, names:set[str], deps:set[str]) -> None:
    '''
    Collect from a symbol's scope subtree: names that refer outside the subtree (module-level or unknown),
    plus direct dependencies from scope-local import statements.
    '''
    for n, u in scope.usages.items():
      if u.load is not None and not u.is_local and scope.free_kind(n) in ('global', 'unknown'):
        names.add(n)
    for qual in scope.imports.values():
      deps.add(self.resolve_qual(importer, qual))
    for child in scope.children:
      self._collect_scope_refs(child, importer, names, deps)


def _collect_outer_refs(node:SemScope, names:set[str]) -> None:
  '''
  Collect names loaded by the parts of a def/class that evaluate in the enclosing scope:
  decorators, base classes, class keywords, type parameters, parameter annotations and defaults, and return annotations.
  The scope visitor attributes these loads to the enclosing scope, so they must be gathered separately per symbol.
  '''
  outer_els:list[Sem] = []
  if isinstance(node, (SemFunctionDef, SemAsyncFunctionDef)):
    outer_els.extend(node.decorator_list)
    outer_els.extend(node.type_params)
    outer_els.append(node.args)
    if node.returns is not None: outer_els.append(node.returns)
  elif isinstance(node, SemClassDef):
    outer_els.extend(node.decorator_list)
    outer_els.extend(node.type_params)
    outer_els.extend(node.bases)
    outer_els.extend(node.keywords)
  for el in outer_els:
    for sub in el.walk():
      if isinstance(sub, SemName) and sub.ctx == 'load': names.add(sub.id)


def module_name_for_path(path:str) -> tuple[str,str]:
  '''
  Derive the dotted module name for a Python file by walking up through package directories (those containing __init__.py).
  Returns (module name, search dir), where the search dir is the parent of the topmost package directory.
  '''
  path = abs_path(path)
  dir = path_dir(path)
  parts = [path_name(path).removesuffix('.py')]
  while path_exists(path_join(dir, '__init__.py'), follow=True):
    parts.append(path_name(dir))
    parent = path_dir(dir)
    if parent == dir: break
    dir = parent
  parts.reverse()
  if len(parts) > 1 and parts[-1] == '__init__': parts.pop()
  return '.'.join(parts), dir


if __name__ == '__main__': main()
