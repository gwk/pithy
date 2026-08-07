# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from inspect import Parameter
from io import StringIO
from os import utime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from typing import Any

from crafts.bin.craft_py_rust_ext import (discover_extensions, find_orphaned_outputs, find_orphaned_shims, Func, gen_extension,
  gen_func, gen_module, Interface, interface_name_errors, module_name_for_path, Par, parse_interface, rust_default,
  rust_function_signatures, rust_type, RustType, UnsupportedType)
from utest import utest, utest_exc, utest_run


empty = Parameter.empty


# Type mapping.

utest(RustType(par='i64', ret='i64'), rust_type, int)
utest(RustType(par='&str', ret='String'), rust_type, str)
utest(RustType(par='&[u8]', ret='Vec<u8>'), rust_type, bytes)
utest(RustType(par='()', ret='()'), rust_type, None)

utest(RustType(par='Option<&str>', ret='Option<String>'), rust_type, str|None)
utest(RustType(par='Vec<String>', ret='Vec<String>'), rust_type, list[str]) # Container elements are always owned.
utest(RustType(par='(i64,)', ret='(i64,)'), rust_type, tuple[int])
utest(RustType(par='((String,),)', ret='((String,),)'), rust_type, tuple[tuple[str]])
utest(RustType(par='(i64, String)', ret='(i64, String)'), rust_type, tuple[int,str])
utest(RustType(par='std::collections::HashMap<String, i64>', ret='std::collections::HashMap<String, i64>', is_hash=False),
  rust_type, dict[str,int])
utest(RustType(par='Vec<Option<i64>>', ret='Vec<Option<i64>>'), rust_type, list[int|None])

utest_exc(UnsupportedType, rust_type, complex)
utest_exc(UnsupportedType, rust_type, int|str) # Only unions with `None` are supported.
utest_exc(UnsupportedType, rust_type, tuple[int,...])
utest_exc(UnsupportedType, rust_type, tuple[()]) # Rust `()` is `None` to pyo3, not the empty tuple.
utest_exc(UnsupportedType, rust_type, 'int') # String annotations are not resolved.

# A `HashMap` key must implement `Hash`, which `f64` and `HashMap` do not; containers are hashable if their elements are.
utest(False, lambda: rust_type(float).is_hash)
utest(True, lambda: rust_type(tuple[int,str|None]).is_hash)
utest('std::collections::HashMap<(i64, Vec<String>), f64>', lambda: rust_type(dict[tuple[int,list[str]],float]).par)
utest_exc(UnsupportedType, rust_type, dict[float,int])
utest_exc(UnsupportedType, rust_type, dict[tuple[int,float],int])
utest_exc(UnsupportedType, rust_type, dict[float|None,int])
utest_exc(UnsupportedType, rust_type, dict[dict[str,int],int])


# Default values.

utest('true', rust_default, True, bool)
utest('3', rust_default, 3, int)
utest('1.5', rust_default, 1.5, float)
utest('1.0', rust_default, 1, float) # An int default for a float parameter renders as a float literal.
utest('"a\\"b\\n"', rust_default, 'a"b\n', str)
utest('"\\u{1}\\u{2014}"', rust_default, '\x01—', str) # Characters outside printable ASCII are escaped.
utest('Default::default()', rust_default, [], list[int])

utest('None', rust_default, None, int|None)
utest('Some("x")', rust_default, 'x', str|None) # An optional parameter wraps its default in `Some`.
utest('Some(1.0)', rust_default, 1, float|None)

utest_exc(UnsupportedType, rust_default, float('inf'), float)
utest_exc(UnsupportedType, rust_default, b'bytes', bytes)
utest_exc(UnsupportedType, rust_default, None, int) # A None default requires an optional parameter type.

# The rendering is directed by the parameter type, so a default that would not compile is rejected.
utest('false', rust_default, False, bool)
utest('-9223372036854775808', rust_default, -(1<<63), int)
utest('-1.5', rust_default, -1.5, float)
utest('Default::default()', rust_default, {}, dict[str,int])
utest_exc(UnsupportedType, rust_default, True, int) # `bool` is a subclass of `int`, but `true` is not an i64.
utest_exc(UnsupportedType, rust_default, 1, bool)
utest_exc(UnsupportedType, rust_default, True, float)
utest_exc(UnsupportedType, rust_default, 'a', int)
utest_exc(UnsupportedType, rust_default, 1.5, int)
utest_exc(UnsupportedType, rust_default, 3, str)
utest_exc(UnsupportedType, rust_default, 3, str|None)
utest_exc(UnsupportedType, rust_default, 1<<63, int) # Does not fit in i64.
utest_exc(UnsupportedType, rust_default, 1<<2000, float) # Does not fit in f64.
utest_exc(UnsupportedType, rust_default, float('nan'), float)
utest_exc(UnsupportedType, rust_default, {}, list[int])
utest_exc(UnsupportedType, rust_default, [1], list[int]) # Only an empty container default is supported.
utest_exc(UnsupportedType, rust_default, (1,), tuple[int])


# Signatures and code generation.

def par(name:str, type:Any, dflt:Any=empty, kind:Any=Parameter.POSITIONAL_OR_KEYWORD) -> Par:
  return Par(name=name, kind=kind, dflt=(None if dflt is empty else rust_default(dflt, type)), rust=rust_type(type))


def func(name:str, pars:list[Par], ret:Any, doc:str='') -> Func:
  return Func(name=name, doc=doc, pars=pars, rust_ret=rust_type(ret).ret)


utest('fn(&str, i64) -> PyResult<String>',
  lambda: func('f', [par('s', str), par('n', int)], str).fn_type)

utest('fn() -> PyResult<()>', lambda: func('f', [], None).fn_type)

utest('s, n=1, /',
  lambda: func('f', [par('s', str, kind=Parameter.POSITIONAL_ONLY), par('n', int, 1, Parameter.POSITIONAL_ONLY)], str
    ).py_signature)

utest('s, *, n=None',
  lambda: func('f', [par('s', str), par('n', int|None, None, Parameter.KEYWORD_ONLY)], str).py_signature)

utest([
  '  /// Doc.',
  '  #[pyfunction]',
  '  #[pyo3(signature = (s, n=1))]',
  '  fn f(s: &str, n: i64) -> PyResult<String> {',
  '    m::f(s, n)',
  '  }'],
  gen_func, func('f', [par('s', str), par('n', int, 1)], str, doc='Doc.'), impl_mod='m', indent='  ')


# Module naming.

utest('byte_utils', module_name_for_path, 'pkg/byte_utils.pyi')
utest('str_utils', module_name_for_path, 'pkg/str_utils/__init__.pyi') # A package is named for its directory.
utest('_pkg', module_name_for_path, '_pkg.pyi')

# Interface names are checked before anything is parsed. The crate is flat, so a name must be unique however it is nested.
utest([], interface_name_errors, 'pkg/_pkg.pyi', ['pkg/a.pyi', 'pkg/sub/__init__.pyi', 'pkg/sub/b.pyi'])

utest(["error: pkg/y/util.pyi: interface name 'util' collides with `pkg/x/util.pyi`; "
  'both map to the Rust module `crate::util`, because the crate is flat. Rename one of them.'],
  interface_name_errors, 'pkg/_pkg.pyi', ['pkg/x/util.pyi', 'pkg/y/util.pyi'])

utest(["error: pkg/util/__init__.pyi: interface name 'util' collides with `pkg/util.pyi`; "
  'both map to the Rust module `crate::util`, because the crate is flat. Rename one of them.'],
  interface_name_errors, 'pkg/_pkg.pyi', ['pkg/util.pyi', 'pkg/util/__init__.pyi'])

utest(["error: pkg/sub/_pkg.pyi: interface name '_pkg' collides with `pkg/_pkg.pyi`; "
  'both map to the Rust module `crate::_pkg`, because the crate is flat. Rename one of them.'],
  interface_name_errors, 'pkg/_pkg.pyi', ['pkg/sub/_pkg.pyi']) # A merged interface cannot take the name of the root.

utest(["error: pkg/type.pyi: interface name 'type' is a Rust keyword; rename it.",
  "error: pkg/gen/__init__.pyi: interface name 'gen' is a Rust keyword; rename it."],
  interface_name_errors, 'pkg/_pkg.pyi', ['pkg/type.pyi', 'pkg/gen/__init__.pyi'])

utest(["error: pkg/a-b.pyi: interface name 'a-b' is not a legal Rust identifier; rename it."],
  interface_name_errors, 'pkg/_pkg.pyi', ['pkg/a-b.pyi'])


# Merged interfaces.

utest('''\
// Generated by `craft-py-rust-ext` from:
//   `m.pyi`
//   `sub/a.pyi`
// Do not edit. Each wrapper below converts its arguments/result and calls its hand-written implementation.

use pyo3::prelude::*;

// Assert that each implementation matches its declaration.
const _: fn(i64) -> PyResult<i64> = crate::a::inc;

/// Doc.
#[allow(non_snake_case)]
#[pymodule]
pub mod m {
  use pyo3::prelude::*;

  // Declared in `sub/a.pyi`.

  /// Inc doc.
  #[pyfunction]
  #[pyo3(signature = (n))]
  fn a__inc(n: i64) -> PyResult<i64> {
    crate::a::inc(n)
  }
}
''',
  gen_module, Interface(path='pkg/m.pyi', name='m', impl_mod='crate::m', doc='Doc.', header=[], funcs=[]),
  merged=[Interface(path='pkg/sub/a.pyi', name='a', impl_mod='crate::a', doc='', header=[],
    funcs=[func('inc', [par('n', int)], int, doc='Inc doc.')], wrapper_prefix='a__')])


# Interface diagnostics.

def interface_error(*lines:str) -> list[str]:
  'Parse `lines` as an interface and return the lines of the diagnostic that it exits with, with the temporary path elided.'
  with TemporaryDirectory() as temp:
    path = str(Path(temp) / 'm.pyi')
    Path(path).write_text(''.join(f'{line}\n' for line in lines))
    try: parse_interface(path=path, name='m', impl_mod='crate::m')
    except SystemExit as e: return str(e.code).replace(path, 'm.pyi').split('\n')
  return []


name_error_fmt = ("error: m.pyi:{}: name '{}' is not defined when the interface is executed; "
  'names imported under `TYPE_CHECKING` are not available to the generator.')

utest([], interface_error, 'def f(a:int) -> int: ...')

# Annotations are evaluated lazily, so a name that is only imported for type checkers is undefined at generation time.
utest([name_error_fmt.format('4:9', 'Sequence'), '  def f(a:Sequence[int]) -> int: ...', '          ^'],
  interface_error,
  'from typing import TYPE_CHECKING',
  'if TYPE_CHECKING:',
  '  from collections.abc import Sequence',
  'def f(a:Sequence[int]) -> int: ...')

utest([name_error_fmt.format('1:22', 'Missing'), '  def f(a:int) -> list[Missing]: ...', '                       ^'],
  interface_error, 'def f(a:int) -> list[Missing]: ...')

utest([
  "error: m.pyi:2:1: annotations raised TypeError: type 'int' is not subscriptable.", '  def f(a:int[str]) -> int: ...', '  ^'],
  interface_error, 'def ok() -> int: ...', 'def f(a:int[str]) -> int: ...')

# A default value is evaluated when the interface is executed, rather than lazily.
utest([
  "error: m.pyi:2:1: interface raised NameError: name 'MISSING' is not defined.", '  def f(a:int=MISSING) -> int: ...', '  ^'],
  interface_error, 'def ok() -> int: ...', 'def f(a:int=MISSING) -> int: ...')


# Regeneration.

@utest_run
def regeneration() -> None:
  with TemporaryDirectory() as temp, redirect_stdout(StringIO()):
    package = Path(temp) / 'pkg'
    package.mkdir()
    root = package / '_pkg.pyi'
    extra = package / 'extra.pyi'
    root.write_text('def root() -> int: ...\n')
    extra.write_text('def extra() -> int: ...\n')
    output = root.with_suffix('.gen.rs')

    def generate(check:bool=False) -> list[list[str]]:
      return [gen_extension(root_path=root_path, merged_paths=merged_paths, indent='  ', check=check)
        for root_path, merged_paths in discover_extensions([str(package)])]

    # Check mode reports an output that is out of date, here because it does not exist yet, and writes nothing.
    utest([[str(output), str(extra.with_suffix('.py')), str(root.with_suffix('.rs')), str(extra.with_suffix('.rs'))]],
      generate, check=True)
    utest(False, output.exists)

    generate()
    utest(True, lambda: 'extra__extra' in output.read_text())

    # A no-op regeneration must not touch the output, or build systems keyed on modification times rebuild the crate.
    utime(output, (1, 1))
    utest([[]], generate)
    utest([[]], generate, check=True)
    utest(1, lambda: int(output.stat().st_mtime))

    # A deleted interface must not leave stale wrappers behind, even when the output is newer than every remaining input.
    utime(root, (1, 1))
    utime(output, (time() + 60, time() + 60))
    extra.unlink()
    utest([[str(output)]], generate, check=True)
    utest(True, lambda: 'extra' in output.read_text()) # Check mode left the stale output alone.
    utest([[str(output)]], generate)
    utest(False, lambda: 'extra' in output.read_text())


# Orphaned outputs.

@utest_run
def orphaned_outputs() -> None:
  for change in ('unchanged', 'delete-root', 'rename-root', 'rename-dir'):
    with TemporaryDirectory() as temp, redirect_stdout(StringIO()):
      package = Path(temp) / 'pkg'
      package.mkdir()
      root = package / '_pkg.pyi'
      root.write_text('def root() -> int: ...\n')
      (package / 'other.gen.rs').write_text('// The output of some other generator.\n') # Never reported.
      for root_path, merged_paths in discover_extensions([temp]):
        gen_extension(root_path=root_path, merged_paths=merged_paths, indent='  ')

      expected = [str(package / '_pkg.gen.rs')]
      if change == 'unchanged': expected = []
      elif change == 'delete-root': root.unlink()
      elif change == 'rename-root': root.rename(package / '_renamed.pyi')
      elif change == 'rename-dir': # The root no longer matches its directory, so the whole extension goes undiscovered.
        package.rename(Path(temp) / 'renamed')
        expected = [str(Path(temp) / 'renamed' / '_pkg.gen.rs')]

      utest(expected, lambda: find_orphaned_outputs([temp], root_paths=[r for r, _ in discover_extensions([temp])]),
        _utest_label=change)


# Shims and editable implementations.

@utest_run
def scaffolding() -> None:
  with TemporaryDirectory() as temp, redirect_stdout(StringIO()) as log:
    package = Path(temp) / 'pkg'
    package.mkdir()
    root = package / '_pkg.pyi'
    root.write_text('def root() -> int: ...\n')
    sub = package / 'sub'
    sub.mkdir()
    interface = sub / '__init__.pyi'
    interface.write_text('def f(data:bytes, n:int) -> int: ...\n')
    rust = sub / 'mod.rs'
    shim = sub / '__init__.py'

    def generate(check:bool=False) -> list[str]:
      return gen_extension(str(root), [str(interface)], indent='  ', check=check)

    utest(4, lambda: len(generate(check=True)))
    utest(False, rust.exists)
    utest(False, shim.exists)
    generate()
    utest(True, lambda: 'from .._pkg import sub__f as f' in shim.read_text())
    utest(True, lambda: 'pub fn f(data: &[u8], n: i64) -> PyResult<i64> {\n  todo!()\n}' in rust.read_text())
    utest(False, lambda: 'Generated' in rust.read_text())
    utest(True, lambda: '#[path = "_pkg.gen.rs"]' in root.with_suffix('.rs').read_text())

    rust.write_text('use pyo3::prelude::*;\npub fn f(data: &[u8], n: i64) -> PyResult<i64> { Ok(n) }\n')
    original = rust.read_bytes()
    utime(rust, (1, 1))
    utime(shim, (1, 1))
    log.seek(0)
    log.truncate()
    utest([], generate)
    utest('', log.getvalue)
    utest(1, lambda: int(shim.stat().st_mtime))

    interface.write_text('def f(data:bytes) -> str: ...\ndef g() -> int: ...\n')
    generate(check=True)
    utest(True, lambda: 'Review the signature of `f`' in log.getvalue())
    utest(True, lambda: 'pub fn f(data: &[u8]) -> PyResult<String>' in log.getvalue())
    utest(True, lambda: 'Add or expose `g`' in log.getvalue())
    utest(False, lambda: 'sub__g' in shim.read_text())
    generate()
    utest(True, lambda: 'sub__g as g' in shim.read_text())
    utest(original, rust.read_bytes)
    utest(1, lambda: int(rust.stat().st_mtime))

    interface.write_text('def g() -> int: ...\n')
    generate()
    utest(True, lambda: '`f` is no longer declared' in log.getvalue())
    utest(False, lambda: 'sub__f' in shim.read_text())
    utest(original, rust.read_bytes)


utest({'f': 'fnf(n:i64)->PyResult<(i64,i64)>'}, rust_function_signatures, '''// fn fake() -> PyResult<()> {}
/* Outer /* fn hidden() {} */ comment. */
const S: &str = r#"fn string() {}"#;
mod nested { pub fn hidden() {} }
impl Thing { pub fn method() {} }
pub fn f(
  n: i64,
) -> PyResult<(i64, i64)> {
  let s = "} fn nope() {";
  Ok((n, n))
}
''')


@utest_run
def orphaned_shims() -> None:
  with TemporaryDirectory() as temp, redirect_stdout(StringIO()):
    package = Path(temp) / 'pkg'
    package.mkdir()
    root = package / '_pkg.pyi'
    root.write_text('def root() -> int: ...\n')
    extra = package / 'extra.pyi'
    extra.write_text('def f() -> int: ...\n')
    gen_extension(str(root), [str(extra)], indent='  ')
    (package / 'ordinary.py').write_text('# Hand-written.\n')
    utest([], find_orphaned_shims, discover_extensions([temp]))
    extra.unlink()
    utest([str(extra.with_suffix('.py'))], find_orphaned_shims, discover_extensions([temp]))
