# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-py-rust-ext` generates the pyo3 boilerplate for Rust extension modules from Python `.pyi` interface files.

It is the Rust counterpart to `craft-py-ext`, which does the same thing for CPython C extensions.
The premise of both tools is that the `.pyi` file should be the source of truth.
The usual maturin/pyo3 arrangement is the reverse: the Rust source defines the interface,
and the `.pyi` is maintained by hand to match it, where it can silently drift.

The tool discovers extensions by walking the given directories (defaulting to the current directory) for `.pyi` files.
An extension root is a file named `_{dir}.pyi` inside a directory named `{dir}`,
per the convention that a package's extension is named `{package}._{package}`;
its interface is implemented in `crate::_{dir}`, and the module generates to the sibling `_{dir}.gen.rs`.
A `.pyi` that is not under an extension directory is an ordinary type stub, and is ignored.
A generated file that no discovered root produces is an error: its root was deleted or renamed,
and the crate would otherwise keep building the stale wrappers.

For each function declared in a `.pyi`, the generator emits a `#[pyfunction]` wrapper
whose Rust signature is derived from the Python annotations.
The wrapper does nothing but call an implementation function of the same name in a hand-written module,
so that generated code and written code never share a file.
pyo3 supplies the actual argument conversion, keyword handling and error propagation for the wrapper signature;
what the generator adds is the guarantee that the signature matches the declaration.

The generator also emits one compile-time assertion per function:

    const _: fn(&str, i64) -> PyResult<String> = crate::str_utils::repeat;

An implementation whose signature does not match its declaration fails to compile at the assertion,
which names the function, rather than somewhere inside the generated wrapper.

Implementations always return `PyResult`, so that any of them can raise a Python exception
without a change to the declaration or to the generated code.

A crate builds exactly one extension module, so a package with several native modules generates them together:
every other `.pyi` under the extension directory is merged into the root, and every function is exported flat.
A merged interface named `n` is assumed to be implemented in `crate::n`, and its functions are exported as `n__f`,
so that same-named declarations in different interfaces cannot collide in the flat namespace.
The mapping is by module name alone, however deeply the interface is nested, so that the crate stays flat;
two interfaces of the same name therefore collide, and are rejected before any interface is parsed.
Generated `.py` modules re-export each interface's functions at its declared import path under their declared names,
per the file layout described in the pyrrhus readme; the prefixed form appears only in the private module,
in tracebacks and in profiles, where it is unambiguous.

Each merged interface owns its sibling `.py` shim, including `__init__.py` for package interfaces.
Do not put hand-written Python code in these files. The extension root has no shim.
Missing implementations are scaffolded as sibling `.rs` files (`mod.rs` for `__init__.pyi`) with `todo!()` bodies.
These files are then hand-edited and never rewritten. Declare new implementation modules in the crate root.
For existing implementations, stdout reports missing or textually different function signatures with copyable skeletons.
This advisory scan handles ordinary top-level Rust functions, not macro expansion or type equivalence;
compilation remains authoritative. Removals are reported using the previous generated wrappers, without deleting Rust code.

Every run regenerates every extension; at this scale there is nothing worth skipping, and no staleness check to get wrong.
The output is never rewritten when its content is unchanged,
so that build systems keyed on modification times (uv, make) do not rebuild the crate for a no-op regeneration.
With `-check`, nothing is written, including missing implementations.
The tool reports each output that is out of date and exits with an error,
so that a check can fail on a stale committed file rather than quietly repair it.
The output does not depend on the directory that the tool is run from; it names its interfaces relative to itself.

Output is written to be stable under rustfmt, so that a generated file passes `cargo fmt --check` unchanged.
Pass `-indent` to match the `tab_spaces` setting of the project being generated into; it defaults to 2, as we do.
Declarations long enough to need wrapping are not handled; run `just fmt-rust` if `cargo fmt --check` complains.
'''

import builtins
import re
from argparse import ArgumentParser
from ast import (AnnAssign, Assign, AST, AsyncFunctionDef, ClassDef, Constant, Expr as ExprStmt, FunctionDef, If, Import,
  ImportFrom, Module, Name, parse, walk)
from dataclasses import dataclass
from inspect import Parameter, signature
from math import isfinite
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, get_args, get_origin, Iterator, NoReturn

from pithy.fs import walk_files
from pithy.io import read_from_path, read_line_from_path
from pithy.path import norm_path, path_dir, path_name, path_stem
from pithy.rust.keywords import rust_keywords


KEYWORD_ONLY = Parameter.KEYWORD_ONLY
POSITIONAL_ONLY = Parameter.POSITIONAL_ONLY
POSITIONAL_OR_KEYWORD = Parameter.POSITIONAL_OR_KEYWORD
empty = Parameter.empty


def main() -> None:
  arg_parser = ArgumentParser(description='Generate pyo3 extension modules from `.pyi` interface files.')
  arg_parser.add_argument('roots', nargs='*', default=['.'],
    help='Directories to search for extension interfaces; defaults to the current directory.')
  arg_parser.add_argument('-check', action='store_true',
    help='Write nothing; report each generated file that is out of date, and exit with an error if any are.')
  arg_parser.add_argument('-indent', type=int, default=2,
    help='Indentation width; should match the rustfmt `tab_spaces` setting.')

  args = arg_parser.parse_args()

  extensions = discover_extensions(args.roots)

  # Check for orphans first: when the only root was deleted, this is more informative than finding no extensions.
  orphans = find_orphaned_outputs(args.roots, root_paths=[root_path for root_path, _ in extensions])
  if orphans:
    exit('\n'.join(
      f'error: {path}: orphaned generated file: no extension root `{path.removesuffix(".gen.rs")}.pyi` was found; '
      'a root is named `_{dir}.pyi` for its directory. Restore the interface, or delete this file and its `#[path]` include.'
      for path in orphans))

  orphan_shims = find_orphaned_shims(extensions)
  if orphan_shims:
    exit('\n'.join(f'error: {path}: orphaned generated shim; restore its interface or delete the shim.'
      for path in orphan_shims))

  if not extensions: exit(f'error: no extension interfaces found in: {" ".join(args.roots)}')

  # Check every extension before generating any, so that a naming problem is reported before anything is parsed or written.
  name_errors = [e for root_path, merged_paths in extensions for e in interface_name_errors(root_path, merged_paths)]
  if name_errors: exit('\n'.join(name_errors))

  stale_paths:list[str] = []
  for root_path, merged_paths in extensions:
    stale = gen_extension(root_path=root_path, merged_paths=merged_paths, indent=(' ' * args.indent), check=args.check)
    stale_paths.extend(stale)
  if args.check and stale_paths:
    exit('\n'.join(f'error: {path}: generated file is out of date; run `craft-py-rust-ext`.' for path in stale_paths))


def discover_extensions(roots:list[str]) -> list[tuple[str,list[str]]]:
  '''
  Find the extensions under `roots` and return (root_path, merged_paths) pairs.
  An extension root is a `.pyi` named `_{dir}.pyi` inside a directory named `{dir}`;
  every other `.pyi` under that directory is an interface merged into the extension.
  A `.pyi` outside of any extension directory is an ordinary type stub, and is ignored.
  '''
  pyi_paths = sorted(norm_path(p) for p in walk_files(*roots, file_exts=['.pyi']))
  root_paths = [p for p in pyi_paths if path_name(p) == f'_{path_name(path_dir(p))}.pyi']

  dirs = [path_dir(p) + '/' for p in root_paths]
  for d in dirs:
    for other in dirs:
      if other != d and other.startswith(d):
        exit(f'error: extension directory `{d}` contains another extension directory: `{other}`')

  return [(root, [p for p in pyi_paths if p != root and p.startswith(path_dir(root) + '/')]) for root in root_paths]


def interface_name_errors(root_path:str, merged_paths:list[str]) -> list[str]:
  '''
  Check the module names of the interfaces of one extension, and return a diagnostic for each problem.
  Every interface named `n` maps to the Rust module `crate::n` and the wrapper prefix `n__`, however deeply it is nested,
  so each name must be a legal Rust identifier, and must be unique within the extension.
  '''
  errors:list[str] = []
  named:dict[str,str] = {} # Module name to the first path that claimed it.
  for path in [root_path, *merged_paths]:
    name = module_name_for_path(path)
    if not (name.isascii() and name.isidentifier()):
      errors.append(f'error: {path}: interface name {name!r} is not a legal Rust identifier; rename it.')
    elif name in rust_keywords:
      errors.append(f'error: {path}: interface name {name!r} is a Rust keyword; rename it.')
    try: other = named[name]
    except KeyError: named[name] = path
    else:
      errors.append(f'error: {path}: interface name {name!r} collides with `{other}`; '
        f'both map to the Rust module `crate::{name}`, because the crate is flat. Rename one of them.')
  return errors


def output_path_for_root(root_path:str) -> str:
  'The generated module is the sibling of the root interface.'
  return root_path.removesuffix('.pyi') + '.gen.rs'


def find_orphaned_outputs(roots:list[str], root_paths:list[str]) -> list[str]:
  '''
  Find the generated files under `roots` that no discovered extension produces.
  This happens when a root interface is deleted or renamed, or its directory is renamed so that the two no longer match.
  The crate would otherwise keep building the stale wrappers via the `#[path]` include in the implementation module.
  Only files carrying our header are considered, so that the output of other generators is left alone.
  '''
  output_paths = {output_path_for_root(p) for p in root_paths}
  gen_paths = sorted(norm_path(p) for p in walk_files(*roots, file_exts=['.gen.rs']))
  return [p for p in gen_paths if p not in output_paths and generated_marker in read_from_path(p).splitlines()]


def find_orphaned_shims(extensions:list[tuple[str,list[str]]]) -> list[str]:
  expected = {p.removesuffix('.pyi') + '.py' for _, merged in extensions for p in merged}
  dirs = [path_dir(root) for root, _ in extensions]
  if not dirs: return []
  return [p for p in sorted(norm_path(p) for p in walk_files(*dirs, file_exts=['.py']))
    if p not in expected and shim_marker in read_from_path(p).splitlines()]


def gen_extension(root_path:str, merged_paths:list[str], indent:str, check:bool=False) -> list[str]:
  '''
  Generate the module for one extension. The output is left untouched if its content would not change.
  Return the paths of stale generated outputs and missing implementations. Check mode writes nothing.
  '''
  output_path = output_path_for_root(root_path)

  root_name = module_name_for_path(root_path)
  root = parse_interface(path=root_path, name=root_name, impl_mod=f'crate::{root_name}')

  merged:list[Interface] = []
  for merged_path in merged_paths:
    name = module_name_for_path(merged_path)
    merged.append(parse_interface(path=merged_path, name=name, impl_mod=f'crate::{name}', wrapper_prefix=f'{name}__'))

  declared:dict[str,str] = {} # Exported wrapper name to declaring path; the extension module is a single flat namespace.
  for interface in [root, *merged]:
    for func in interface.funcs:
      ext_name = interface.wrapper_prefix + func.name
      if ext_name in declared:
        exit(f'error: {interface.path}: function {func.name!r} is exported as {ext_name!r}, '
          f'which collides with a declaration in `{declared[ext_name]}`')
      declared[ext_name] = interface.path

  previous = read_from_path(output_path, default='')
  outputs = {output_path: gen_module(root, merged=merged, indent=indent)}
  for interface in merged:
    outputs[interface.path.removesuffix('.pyi') + '.py'] = gen_shim(root, interface)

  # Implementations become user-owned as soon as they exist. Never rewrite them.
  new_impl_paths:set[str] = set()
  for interface in [root, *merged]:
    impl_path = implementation_path(interface)
    if not Path(impl_path).exists():
      new_impl_paths.add(impl_path)
      outputs[impl_path] = gen_implementation(interface, indent=indent, is_root=(interface is root))
      if not check:
        print(f'{impl_path}: fill in the function bodies; ensure `{interface.impl_mod}` is declared in the crate root.')
    else:
      report_implementation_changes(interface, previous=previous, indent=indent)

  stale_paths:list[str] = []
  for path, text in outputs.items():
    if text == read_from_path(path, default=''): continue
    stale_paths.append(path)
    if not check:
      with open(path, 'x' if path in new_impl_paths else 'w') as f:
        f.write(text)
      print(f'craft-py-rust-ext: generated {path}')
  return stale_paths


license_text = 'Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.'
shim_marker = '# Generated by craft-py-rust-ext. Do not edit.'


def gen_shim(root:Interface, interface:Interface) -> str:
  'Generate relative imports so nested interfaces do not depend on the invoking directory or installation path.'
  relative = Path(interface.path).relative_to(Path(root.path).parent)
  depth = len(relative.parts) - 1
  # A package __init__ imports relative to itself; a module imports relative to its containing package.
  extension = '.' * (depth + 1) + root.name
  lines = [f'# {license_text}', shim_marker, '']
  names = [f'{interface.wrapper_prefix}{f.name} as {f.name}' for f in sorted(interface.funcs, key=lambda f: f.name)]
  if names:
    prefix = f'from {extension} import '
    if len(prefix + ', '.join(names)) <= 128:
      lines.append(prefix + ', '.join(names))
    else:
      line = prefix + '('
      for idx, name in enumerate(names):
        item = name + (',' if idx + 1 < len(names) else ')')
        if len(line) + len(item) + 1 > 128:
          lines.append(line.rstrip())
          line = '  '
        line += item + (' ' if idx + 1 < len(names) else '')
      lines.append(line)
  if names:
    lines.extend(['', '', '__all__ = ['])
    lines.extend(f'  {f.name!r},' for f in sorted(interface.funcs, key=lambda f: f.name))
    lines.append(']')
  return '\n'.join(lines) + '\n'


def implementation_path(interface:Interface) -> str:
  path = Path(interface.path)
  return str(path.with_name('mod.rs') if path.name == '__init__.pyi' else path.with_suffix('.rs'))


def implementation_signature(func:Func) -> str:
  pars = ', '.join(f'{p.name}: {p.rust.par}' for p in func.pars)
  return f'fn {func.name}({pars}) -> PyResult<{func.rust_ret}>'


def implementation_skeleton(func:Func, indent:str) -> str:
  return f'pub {implementation_signature(func)} {{\n{indent}todo!()\n}}'


def gen_implementation(interface:Interface, indent:str, is_root:bool=False) -> str:
  lines = [f'// {license_text}', '', 'use pyo3::prelude::*;']
  if is_root:
    lines.extend(['', f'#[path = "{interface.name}.gen.rs"]', 'pub mod generated;'])
  for func in interface.funcs:
    lines.extend(['', '', implementation_skeleton(func, indent)])
  return '\n'.join(lines) + '\n'


# This scanner is advisory, not a Rust parser. It recognizes ordinary top-level function headers,
# ignoring bodies, nested items, comments and literals. Rust compilation remains authoritative.
rust_token_re = re.compile(r'''//[^\n]*|/\*|\*/|(?:br|cr|r)(?P<hashes>\#{0,255})"[\s\S]*?"(?P=hashes)
  |"(?:\\[\s\S]|[^"\\])*"|'(?:\\[^\n]|[^'\\\n])'|[A-Za-z_]\w*|->|[^\s]''', re.X)


def rust_function_signatures(src:str) -> dict[str,str]:
  tokens:list[str] = []
  comment_depth = 0
  for match in rust_token_re.finditer(src):
    token = match[0]
    if token == '/*': comment_depth += 1
    elif token == '*/' and comment_depth: comment_depth -= 1
    elif not comment_depth and not token.startswith('//'):
      # Keep literals as opaque tokens so their contents cannot look like declarations or braces.
      tokens.append(token)

  signatures:dict[str,str] = {}
  depth = 0
  idx = 0
  while idx < len(tokens):
    token = tokens[idx]
    if token == 'fn' and depth == 0 and idx + 1 < len(tokens):
      end = idx + 2
      while end < len(tokens) and tokens[end] not in ('{', ';'): end += 1
      signatures[tokens[idx + 1]] = ''.join(tokens[idx:end]).replace(',)', ')')
      idx = end
      if idx == len(tokens): break
      token = tokens[idx]
    if token == '{': depth += 1
    elif token == '}': depth -= 1
    idx += 1
  return signatures


def report_implementation_changes(interface:Interface, previous:str, indent:str) -> None:
  path = implementation_path(interface)
  signatures = rust_function_signatures(Path(path).read_text())
  for func in interface.funcs:
    expected = re.sub(r'\s+', '', implementation_signature(func))
    actual = signatures.get(func.name)
    if actual == expected: continue
    action = 'Add or expose' if actual is None else 'Review the signature of'
    print(f'{path}: {action} `{func.name}` to match {interface.path}; expected skeleton:')
    print(implementation_skeleton(func, indent))
    print()

  # Only flag removals known to have been exported. Other Rust functions may be intentional helpers.
  old_names = set(re.findall(r'^const _: .* = ' + re.escape(interface.impl_mod) + r'::(\w+);$', previous, re.M))
  for name in sorted(old_names - {f.name for f in interface.funcs}):
    print(f'{path}: `{name}` is no longer declared in {interface.path}; remove it if no longer needed.')


# The first line of the generated header, which `find_orphaned_outputs` uses to recognize our output.
generated_marker = '// Generated by `craft-py-rust-ext` from:'


def module_name_for_path(path:str) -> str:
  'Derive the module name from the interface path. A package interface is named for its directory, as in Python.'
  stem = path_name(path_stem(path))
  return path_name(path_dir(path)) if stem == '__init__' else stem


# Type mapping.

@dataclass(frozen=True)
class RustType:
  'The Rust spelling of a Python type, which differs between parameter and return position.'
  par:str
  ret:str
  is_hash:bool = True # Whether the Rust type implements `Hash`, which a `HashMap` key must.


scalar_rust_types = {
  bool: RustType(par='bool', ret='bool'),
  int: RustType(par='i64', ret='i64'),
  float: RustType(par='f64', ret='f64', is_hash=False),
  str: RustType(par='&str', ret='String'),
  bytes: RustType(par='&[u8]', ret='Vec<u8>'),
}


class UnsupportedType(Exception):
  'Raised for a Python type annotation that has no Rust mapping.'


def rust_type(t:Any) -> RustType:
  '''
  Map a Python type annotation to its Rust equivalent.
  Container element types always use the owned (return position) spelling, because pyo3 extracts owned containers.
  '''
  if t is None or t is NoneType: return RustType(par='()', ret='()')
  if isinstance(t, str): raise UnsupportedType(f'{t!r}; string annotations are not resolved, declare the type directly')

  try: return scalar_rust_types[t]
  except (KeyError, TypeError): pass

  origin = get_origin(t)
  args = get_args(t)

  if origin is UnionType:
    non_none = [a for a in args if a is not NoneType]
    if len(non_none) != 1 or len(non_none) == len(args):
      raise UnsupportedType(f'{type_str(t)}; only unions of a single type with `None` are supported')
    el = rust_type(non_none[0])
    return RustType(par=f'Option<{el.par}>', ret=f'Option<{el.ret}>', is_hash=el.is_hash)

  if origin is list:
    el = rust_type(args[0])
    return RustType(par=f'Vec<{el.ret}>', ret=f'Vec<{el.ret}>', is_hash=el.is_hash)

  if origin is tuple:
    if Ellipsis in args: raise UnsupportedType(f'{type_str(t)}; variadic tuples are not supported, use `list`')
    # The Rust spelling would be `()`, which pyo3 returns as `None` and cannot extract as a parameter.
    if not args: raise UnsupportedType(f'{type_str(t)}; empty tuples are not supported, use `None` to return nothing')
    el_types = [rust_type(a) for a in args]
    els = ', '.join(el.ret for el in el_types)
    if len(args) == 1: els += ',' # Rust requires a trailing comma for a single-element tuple.
    return RustType(par=f'({els})', ret=f'({els})', is_hash=all(el.is_hash for el in el_types))

  if origin is dict:
    key = rust_type(args[0])
    if not key.is_hash: raise UnsupportedType(f'{type_str(t)}; the key type has no hashable Rust equivalent')
    k = key.ret
    v = rust_type(args[1]).ret
    return RustType(par=f'std::collections::HashMap<{k}, {v}>', ret=f'std::collections::HashMap<{k}, {v}>', is_hash=False)

  raise UnsupportedType(type_str(t))


def type_str(t:Any) -> str:
  'Render a type annotation for diagnostics.'
  return t.__name__ if isinstance(t, type) else str(t)


def rust_default(val:Any, t:Any) -> str:
  '''
  Render a Python default value as the Rust expression for a parameter of type `t`.
  The rendering is directed by the type rather than by the value, so that every default it accepts compiles:
  an optional parameter wraps its default in `Some`, a float parameter renders an int default as a float literal,
  and a value that does not fit the Rust type is rejected here, rather than by rustc in the generated code.
  '''
  origin = get_origin(t)
  if origin is UnionType: # Optional; `rust_type` has already validated the union shape.
    if val is None: return 'None'
    el_type = next(a for a in get_args(t) if a is not NoneType)
    return f'Some({rust_default(val, el_type)})'
  if val is None: raise UnsupportedType('default value: None; the parameter type is not optional')

  mismatch = UnsupportedType(f'default value: {val!r}; does not match the parameter type `{type_str(t)}`')
  is_bool = isinstance(val, bool) # `bool` is a subclass of `int`, but Rust does not convert between them.

  if t is bool:
    if not is_bool: raise mismatch
    return 'true' if val else 'false'

  if t is int:
    if is_bool or not isinstance(val, int): raise mismatch
    if not (-(1<<63) <= val < (1<<63)): raise UnsupportedType(f'default value: {val!r}; does not fit in i64')
    return repr(val)

  if t is float:
    if is_bool or not isinstance(val, (int, float)): raise mismatch
    try: float_val = float(val)
    except OverflowError: float_val = float('inf')
    if not isfinite(float_val): raise UnsupportedType(f'default value: {val!r}; not a finite f64')
    return repr(float_val)

  if t is str:
    if not isinstance(val, str): raise mismatch
    return rust_str_literal(val)

  if origin in (list, dict):
    if not isinstance(val, origin): raise mismatch
    if val: raise UnsupportedType(f'default value: {val!r}; only an empty {origin.__name__} default is supported')
    return 'Default::default()'

  raise UnsupportedType(f'default value: {val!r}; defaults are not supported for parameters of type `{type_str(t)}`')


rust_str_escapes = {'\\': '\\\\', '"': '\\"', '\n': '\\n', '\r': '\\r', '\t': '\\t', '\0': '\\0'}

def rust_str_literal(s:str) -> str:
  'Render a Python string as a Rust string literal. Characters outside printable ASCII are escaped.'
  chars:list[str] = []
  for c in s:
    try: chars.append(rust_str_escapes[c])
    except KeyError: chars.append(c if ' ' <= c <= '~' else f'\\u{{{ord(c):x}}}')
  return '"' + ''.join(chars) + '"'


# Interface model.

@dataclass
class Par:
  'A function parameter, as declared in the interface.'
  name:str
  kind:Any
  dflt:str|None # The Rust rendering of the default value, or None if the parameter has no default.
  rust:RustType


@dataclass
class Func:
  'A function, as declared in the interface.'
  name:str
  doc:str
  pars:list[Par]
  rust_ret:str

  @property
  def fn_type(self) -> str:
    'The Rust function pointer type that the implementation must match.'
    pars = ', '.join(p.rust.par for p in self.pars)
    return f'fn({pars}) -> PyResult<{self.rust_ret}>'

  @property
  def py_signature(self) -> str:
    '''
    The pyo3 signature, which mirrors the Python calling convention, including defaults and the `/` and `*` markers.
    It is emitted for every function with parameters; pyo3 otherwise infers defaults for trailing `Option` parameters.
    '''
    parts:list[str] = []
    prev = None
    for par in self.pars:
      if prev is POSITIONAL_ONLY and par.kind is not POSITIONAL_ONLY: parts.append('/')
      if par.kind is KEYWORD_ONLY and prev is not KEYWORD_ONLY: parts.append('*')
      parts.append(par.name if par.dflt is None else f'{par.name}={par.dflt}')
      prev = par.kind
    if prev is POSITIONAL_ONLY: parts.append('/')
    return ', '.join(parts)


@dataclass
class Interface:
  'A parsed `.pyi` interface file.'
  path:str
  name:str
  impl_mod:str # Rust path of the module holding the implementations.
  doc:str
  header:list[str]
  funcs:list[Func]
  wrapper_prefix:str = '' # Prefix distinguishing this interface's wrappers in the flat namespace; empty for the root.


# Parsing.

def parse_interface(path:str, name:str, impl_mod:str, wrapper_prefix:str='') -> Interface:
  '''
  Parse the interface by both execing the source and parsing it into an AST.
  The former gives us the annotation objects and defaults; the latter lets us distinguish declarations from imports,
  and report diagnostics against the source.
  '''
  src = read_from_path(path)
  try:
    module = parse(src, filename=path)
    code = compile(module, filename=path, mode='exec', optimize=0) # optimize=0 preserves docstrings.
  except SyntaxError as e:
    line1 = e.lineno or 1
    exit(src_diagnostic(path, line0=line1-1, col0=(e.offset or 1)-1, msg=(e.msg or str(e))))

  vals:dict[str,Any] = {'__builtins__':__builtins__}
  try: exec(code, vals)
  except Exception as e: # For example, a default value or a base class that names something undefined.
    exit('error: ' + src_diagnostic(path, line0=exc_line0(e, path), col0=0, msg=f'interface raised {type(e).__name__}: {e}'))

  funcs = [parse_func(path=path, syntax=syntax, obj=vals[decl_name]) for decl_name, syntax in iter_decls(path, module)]

  return Interface(path=path, name=name, impl_mod=impl_mod, doc=(vals.get('__doc__') or ''), header=parse_header(src),
    funcs=funcs, wrapper_prefix=wrapper_prefix)


def exc_line0(exc:BaseException, path:str) -> int:
  'Return the zero-based line of the innermost traceback frame that is in the file at `path`, or else zero.'
  line0 = 0
  tb = exc.__traceback__
  while tb:
    if tb.tb_frame.f_code.co_filename == path: line0 = tb.tb_lineno - 1
    tb = tb.tb_next
  return line0


def parse_header(src:str) -> list[str]:
  'Return the leading comment block of the source, without the comment markers. This carries the license into the output.'
  lines:list[str] = []
  for line in src.split('\n'):
    if not line.startswith('#'): break
    lines.append(line[1:].strip())
  return lines


def iter_decls(path:str, module:Module) -> Iterator[tuple[str,FunctionDef]]:
  'Yield the function declarations of the module, warning about statements that the generator does not handle.'
  for stmt in module.body:
    if isinstance(stmt, FunctionDef):
      if stmt.decorator_list: # The exec'd object would be whatever the decorator returned, not the declared function.
        error(path, stmt.decorator_list[0], 'function decorators are not supported')
      yield (stmt.name, stmt)
    elif isinstance(stmt, (Assign, Import, ImportFrom)):
      continue
    elif isinstance(stmt, ExprStmt) and isinstance(stmt.value, Constant):
      continue # Docstring.
    elif isinstance(stmt, If) and isinstance(stmt.test, Name) and stmt.test.id == 'TYPE_CHECKING':
      continue # Stub-only imports; the block does not execute at generation time and declares nothing to generate.
    elif isinstance(stmt, (AnnAssign, AsyncFunctionDef, ClassDef)):
      kind = {AnnAssign:'variable', AsyncFunctionDef:'async function', ClassDef:'class'}[type(stmt)]
      error(path, stmt, f'{kind} declarations are not implemented')
    else:
      error(path, stmt, f'unexpected interface statement: {type(stmt).__name__}')


def parse_func(path:str, syntax:FunctionDef, obj:Any) -> Func:
  'Convert a declared function into the interface model.'

  # Keywords that a raw identifier could escape are rejected anyway,
  # because pyo3 matches `#[pyo3(signature)]` entries against the literal Rust parameter names.
  if syntax.name in rust_keywords: error(path, syntax, f'function name {syntax.name!r} is a Rust keyword; rename it')

  # Annotations are evaluated lazily, by `signature` rather than during exec, so this is where a bad annotation raises.
  check_annotation_names(path, syntax, env=obj.__globals__)
  try: sig = signature(obj)
  except Exception as e: error(path, syntax, f'annotations raised {type(e).__name__}: {e}')
  pars:list[Par] = []
  for p in sig.parameters.values():
    if p.kind not in (POSITIONAL_ONLY, POSITIONAL_OR_KEYWORD, KEYWORD_ONLY):
      error(path, syntax, f'parameter {p.name!r} has unsupported kind: {p.kind}')
    if p.name in rust_keywords: error(path, syntax, f'parameter {p.name!r} is a Rust keyword; rename it')
    if p.annotation is empty: error(path, syntax, f'parameter {p.name!r} has no type annotation')
    if p.annotation is None or p.annotation is NoneType: error(path, syntax, f'parameter {p.name!r} cannot be `None`')
    try: rust = rust_type(p.annotation)
    except UnsupportedType as e: error(path, syntax, f'parameter {p.name!r} has unsupported type: {e}')
    dflt = None
    if p.default is not empty: # Render now, so that the diagnostic can name the parameter.
      try: dflt = rust_default(p.default, p.annotation)
      except UnsupportedType as e: error(path, syntax, f'parameter {p.name!r} has unsupported {e}')
    pars.append(Par(name=p.name, kind=p.kind, dflt=dflt, rust=rust))

  if sig.return_annotation is empty: error(path, syntax, 'function has no return annotation')
  try: ret = rust_type(sig.return_annotation)
  except UnsupportedType as e: error(path, syntax, f'unsupported return type: {e}')

  doc = obj.__doc__ or ''
  m = invalid_doc_re.search(doc)
  if m: error(path, syntax, f'docstring contains invalid characters: {m[0]!r}')

  return Func(name=syntax.name, doc=doc, pars=pars, rust_ret=ret.ret)


def check_annotation_names(path:str, syntax:FunctionDef, env:dict[str,Any]) -> None:
  '''
  Report an annotation that uses a name which is not defined in `env`, the globals of the executed interface.
  Evaluating it would raise NameError, which cannot say where the name is. The usual cause is an import under `TYPE_CHECKING`.
  '''
  args = syntax.args
  pars = [*args.posonlyargs, *args.args, args.vararg, *args.kwonlyargs, args.kwarg]
  for annotation in [*(p.annotation for p in pars if p), syntax.returns]:
    if annotation is None: continue
    for node in walk(annotation):
      if isinstance(node, Name) and node.id not in env and not hasattr(builtins, node.id):
        error(path, node, f'name {node.id!r} is not defined when the interface is executed; '
          'names imported under `TYPE_CHECKING` are not available to the generator')


invalid_doc_re = re.compile(r'[^\n -~]+')


# Code generation.

def gen_module(root:Interface, merged:list[Interface]=[], indent:str='  ') -> str:
  '''
  Generate the Rust source for the extension module: the root interface, plus the merged interfaces of a multi-module
  package. `indent` is one level of indentation, and should match rustfmt `tab_spaces`.
  '''
  interfaces = [root, *merged]

  lines:list[str] = []
  for line in root.header:
    lines.append(f'// {line}'.rstrip())
  if root.header: lines.append('')

  # Name the interfaces relative to the output, which is beside the root, rather than to the current directory,
  # so that the output does not depend on where the tool is run from.
  dir_prefix = path_dir(root.path) + '/'

  lines.append(generated_marker)
  for interface in interfaces:
    lines.append(f'//   `{interface.path.removeprefix(dir_prefix)}`')
  lines.append('// Do not edit. Each wrapper below converts its arguments/result and calls its hand-written implementation.')
  lines.append('')
  lines.append('use pyo3::prelude::*;')

  if any(interface.funcs for interface in interfaces):
    lines.append('')
    lines.append('// Assert that each implementation matches its declaration.')
    for interface in interfaces:
      for func in interface.funcs:
        lines.append(f'const _: {func.fn_type} = {interface.impl_mod}::{func.name};')

  lines.append('')
  lines.extend(gen_doc_comment(root.doc, indent=''))
  if merged:
    lines.append('#[allow(non_snake_case)]')
  lines.append('#[pymodule]')
  lines.append(f'pub mod {root.name} {{')
  lines.append(f'{indent}use pyo3::prelude::*;')
  for func in root.funcs:
    lines.append('')
    lines.extend(gen_func(func, impl_mod=root.impl_mod, indent=indent, prefix=root.wrapper_prefix))
  for interface in merged:
    lines.append('')
    lines.append(f'{indent}// Declared in `{interface.path.removeprefix(dir_prefix)}`.')
    for func in interface.funcs:
      lines.append('')
      lines.extend(gen_func(func, impl_mod=interface.impl_mod, indent=indent, prefix=interface.wrapper_prefix))
  lines.append('}')

  return '\n'.join(lines) + '\n'


def gen_func(func:Func, impl_mod:str, indent:str, prefix:str='') -> list[str]:
  '''
  Generate the wrapper for a single function. The wrapper sits one level inside the module, so its body sits two.
  `prefix` distinguishes the wrappers of a merged interface, whose names share the module's flat namespace.
  '''
  lines = gen_doc_comment(func.doc, indent=indent)
  lines.append(f'{indent}#[pyfunction]')
  if func.pars: lines.append(f'{indent}#[pyo3(signature = ({func.py_signature}))]')
  pars = ', '.join(f'{p.name}: {p.rust.par}' for p in func.pars)
  lines.append(f'{indent}fn {prefix}{func.name}({pars}) -> PyResult<{func.rust_ret}> {{')
  args = ', '.join(p.name for p in func.pars)
  lines.append(f'{indent}{indent}{impl_mod}::{func.name}({args})')
  lines.append(f'{indent}}}')
  return lines


def gen_doc_comment(doc:str, indent:str) -> list[str]:
  'Render a Python docstring as a Rust doc comment, which pyo3 turns back into the Python `__doc__`.'
  return [f'{indent}/// {line}'.rstrip() for line in doc.strip().split('\n')] if doc.strip() else []


# Diagnostics.

def src_diagnostic(path:str, line0:int, col0:int, msg:str) -> str:
  text = read_line_from_path(path, line_index=line0, default='<MISSING>')
  pad = ' ' * col0
  return f'{path}:{line0+1}:{col0+1}: {msg}.\n  {text}\n  {pad}^'


def error(path:str, node:AST, msg:str) -> NoReturn:
  line0 = getattr(node, 'lineno', 1) - 1 # `Module` has no lineno.
  col0 = getattr(node, 'col_offset', 0)
  exit('error: ' + src_diagnostic(path=path, line0=line0, col0=col0, msg=msg))


if __name__ == '__main__': main()
