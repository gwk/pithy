# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-py-ext` is an experimental tool for generating the boilerplate to build simple CPython extensions.
It should be considered a work in progress.

To use it, you write a `.pyi` type declaration file, and then generate the boilerplate from that.
The boilerplate comes in two layers.
An outer function provides the C extension interface (e.g. PyObject* types),
and does a certain amount of error checking and unwrapping to native C types.
Then, a corresponding inner function is called, which is where the actual implementation goes.
The idea is to let the implementor fill out the inner funcntion, and keep most of the generated boilerplate separate.
'''


import re
from argparse import ArgumentParser
from ast import (AST, AnnAssign, Assign, AsyncFunctionDef, ClassDef, Expr as ExprStmt, FunctionDef, Import, ImportFrom, Module,
  Name, Str, parse, stmt as Stmt)
from dataclasses import dataclass
from enum import Enum
from functools import singledispatch
from inspect import Parameter, Signature, signature
from typing import Any, ByteString, Callable, Dict, Iterator, List, NoReturn, Optional, TextIO, Tuple, Type, Union

from mypy_extensions import VarArg
from pithy.io import errL, errSL, read_from_path, read_line_from_path
from pithy.path import path_name, path_stem


KEYWORD_ONLY = Parameter.KEYWORD_ONLY
POSITIONAL_ONLY = Parameter.POSITIONAL_ONLY
POSITIONAL_OR_KEYWORD = Parameter.POSITIONAL_OR_KEYWORD
VAR_KEYWORD = Parameter.VAR_KEYWORD
empty = Parameter.empty


def main() -> None:
  arg_parser = ArgumentParser(description='Generate CPython extension stubs from .pyi files.')
  arg_parser.add_argument('paths', nargs='+', default=[])
  arg_parser.add_argument('-dbg', action='store_true')

  args = arg_parser.parse_args()

  if not args.paths: exit('No paths specified.')

  for path in args.paths:
    if not path.endswith('.pyi'): exit(f'interface path does not end with `.pyi`: {path}')
    generate_ext(path=path)


# Python type mapppings.

@dataclass
class TypeInfo:
  'Maps Python types, as parsed from .pyi files, to C extension types and associated metadata.'
  type:Any
  c_type:str
  c_init:str
  c_arg_parser_fmt:str
  return_conv:Optional[str]

type_info_any = TypeInfo(Any,
    c_type='PyObject *', c_init='NULL', c_arg_parser_fmt='o', return_conv='(PyObject*)')

type_infos = { t.type : t for t in [
  type_info_any,
  TypeInfo(None,
    c_type='void ', c_init='', c_arg_parser_fmt='', return_conv=None),
  TypeInfo(bytes,
    c_type='PyBytesObject *', c_init='NULL', c_arg_parser_fmt='S', return_conv='(PyObject *)'),
  TypeInfo(Union[str,ByteString],
    c_type='Py_buffer ', c_init='{.buf=NULL, .obj=NULL, .len=0}', c_arg_parser_fmt='s*', return_conv=None),
]}


TypeAnn = Union[None,str,Type[Any]]

@dataclass
class Par:
  'Function parameter info, as parsed from Python annotations.'
  name:str
  type:TypeAnn
  dflt:Any

  @property
  def c_arg_cleanup(self) -> Optional[str]:
    'Optional C argument cleanup code.'
    if self.ti.c_type == 'Py_buffer ': return f'if ({self.name}.obj) PyBuffer_Release(&{self.name})'
    return None

  @property
  def ti(self) -> TypeInfo: return type_infos.get(self.type, type_info_any)


class FuncKind(Enum):
  Plain = 0
  Method = 1
  Class = 2
  Static = 3


@dataclass
class Func:
  'Function info, as parsed from Python annotations.'
  name:str
  type_name:str
  sig:Signature
  pars:List[Par]
  ret:TypeAnn
  doc:str
  kind:FuncKind


@dataclass
class Var:
  name:str
  type:Type[Any]


Decl = Union['Class',Func,Var]


class SourceReporter:
  'Base class that can report source diagnostics from an AST node.'
  path:str

  def warn(self, node:AST, msg:str) -> None:
    errSL('warning:', node_diagnostic(path=self.path, node=node, msg=msg))

  def error(self, node:AST, msg:str) -> NoReturn:
    exit('error: ' + node_diagnostic(path=self.path, node=node, msg=msg))


class Scope(SourceReporter):
  'Scope base class is either a ExtMod (whole module being generated) or a Class.'

  def __init__(self, path:str, name:str, doc:str) -> None:
    self.path = path
    self.name = name
    self.doc:str = doc
    self.decls:List[Decl] = []


class ExtMod(Scope):
  'The parsed/generated extension module.'


class Class(Scope):
  'Class scope; both a Scope and a Decl, which is what makes the whole thing compicated.'


def generate_ext(path:str) -> None:
  'Top level parsing and code generation for a path.'

  errL('\n', path)
  stem = path_stem(path)
  name = path_name(stem)

  mod_source = parse_pyi_module(path=path) # Input.
  mod = ExtMod(path=path, name=name, doc=mod_source.doc)
  for name, syntax, obj in mod_source:
    parse_decl(syntax, name=name, obj=obj, scope=mod, global_vals=mod_source.vals)

  dst_c = stem + '.gen.cpp'
  dst_h = stem + '.gen.h'
  with open(dst_c, 'w') as c, open(dst_h, 'w') as h:
    write_module(mod, c=c, h=h)



ScopeNode = Union[ClassDef,Module]

@dataclass
class ScopeSource(SourceReporter):
  'The source of a module or class scope. Contains both the syntactic and dynamic representations.'
  path:str
  node:ScopeNode
  vals:Dict[str,Any]

  @property
  def body(self) -> List[Stmt]: return self.node.body

  @property
  def doc(self) -> str:
    body = self.body
    if not (body and isinstance(body[0], ExprStmt) and isinstance(body[0].value, Str)):
      self.error(self.node, 'missing docstring')
    doc_expr = body[0].value
    doc = doc_expr.s
    assert isinstance(doc, str)
    m = invalid_doc_re.search(doc)
    if m:
      s, e = m.span()
      self.error(doc_expr, f'invalid docstring: {m[0]!r}')
    return doc


  def __iter__(self) -> Iterator[Tuple[str,AST,Any]]:
    'Iterate over a source and return (name, AST statement, runtime value) triples.'

    for stmt in self.body:
      name:str
      if isinstance(stmt, AnnAssign) and isinstance(stmt.target, Name):
        name = stmt.target.id
      elif isinstance(stmt, (AsyncFunctionDef, ClassDef, FunctionDef)):
        name = stmt.name
      elif isinstance(stmt, (Assign, Import, ImportFrom)):
        continue
      elif isinstance(stmt, ExprStmt) and isinstance(stmt.value, Str):
        continue # Docstring.
      else:
        type_name = type(stmt).__name__
        self.warn(stmt, msg=f'unexpected interface statement: {type_name}')
        continue
      yield (name, stmt, self.vals[name])


def parse_pyi_module(path:str) -> ScopeSource:
  '''
  Parse .pyi declarations by both execing the source, and also parsing it into an AST.
  The former lets us inspect the dynamic objects;
  the latter lets us distinguish between declarations and imports.
  '''

  src = read_from_path(path)

  # Parse src into an AST Module.
  module = parse(src, filename=path)

  # Compile.
  try: code = compile(module, filename=path, mode='exec', optimize=1)
  except SyntaxError as e:
    line1 = e.lineno or 0 # If lineno is None, then line0 in our diagnostic becomes -1, which will print as '0'.
    exit(src_diagnostic(path, line0=line1-1, col0=(e.offset or 0), msg=str(e)))
  except ValueError as e: exit(src_diagnostic(path, line0=0, col0=0, msg=str(e)))

  # Exec.
  globals:Dict[str,Any] = {'__builtins__': __builtins__}
  exec(code, globals) # As of python3.7, passing separate locals does not work because type annotation lookup is broken.

  return ScopeSource(path=path, node=module, vals=globals)


# Parsing is dispatched over syntax type.

@singledispatch
def parse_decl(syntax:AST, name:str, obj:Any, scope:Scope, global_vals:Dict[str,Any]) -> None:
  'Default implementation raises.'
  raise Exception(f'unknown syntax type: {name}; type: {syntax}')


@parse_decl.register
def _(syntax:AnnAssign, name:str, obj:Any, scope:Scope, global_vals:Dict[str,Any]) -> None:
  'Parse an annotated variable declaration.'
  scope.warn(syntax, f'assignment not implemented')


@parse_decl.register # type: ignore
def _(syntax:AsyncFunctionDef, name:str, obj:Any, scope:Scope, global_vals:Dict[str,Any]) -> None:
  'Async function.'
  scope.warn(syntax, f'async function def is not implemented')


@parse_decl.register # type: ignore
def _(syntax:FunctionDef, name:str, obj:Any, scope:Scope, global_vals:Dict[str,Any]) -> None:
  'Function declaration.'

  is_method = isinstance(scope, Class)
  if is_method:
    if isinstance(obj, classmethod):
      kind = FuncKind.Class
    elif isinstance(obj, staticmethod):
      kind = FuncKind.Static
    else: # Instance method.
      kind = FuncKind.Method
  else: # Plain module function.
    kind = FuncKind.Plain


  is_class_method = isinstance(obj, (classmethod, staticmethod)) # Not sure if it is correct to handle both kinds the same way.

  if is_class_method:
    func = obj.__func__
  else:
    func = obj
  doc = func.__doc__ or ''
  sig = signature(func)

  pars:List[Par] = []
  for i, p in enumerate(sig.parameters.values()):
    n = p.name
    t = p.annotation
    d = p.default
    #k = p.kind # POSITIONAL_ONLY, POSITIONAL_OR_KEYWORD, KEYWORD_ONLY, VAR_KEYWORD.
    if isinstance(t, str):
      try: t = global_vals[t]
      except KeyError: scope.error(syntax, f'parameter {n!r} has invalid string annotation: {t!r}')
    if i == 0 and is_method:
      expected_name = 'cls' if is_class_method else 'self'
      if n != expected_name: scope.warning(syntax, f'parameter {n!r} has unexpected name; expected {expected_name!r}')
    elif t == empty: scope.error(syntax, f'parameter {n!r} has no type annotation')
    pars.append(Par(name=n, type=t, dflt=d))

  ret = sig.return_annotation
  if isinstance(ret, str):
    try: ret = global_vals[ret]
    except KeyError: scope.error(syntax, f'return type has invalid string annotation: {ret!r}')
  ret_ti = type_infos.get(ret, type_info_any)
  if ret is not None and ret_ti.return_conv is None:
    scope.error(syntax, f'return type is mapped to a C type that cannot be converted to a return value: {ret!r}')

  type_name = scope.name if is_method else None
  scope.decls.append(Func(name=name, type_name=type_name, sig=sig, pars=pars, ret=ret, doc=doc, kind=kind))


@parse_decl.register # type: ignore
def _(syntax:ClassDef, name:str, obj:Any, scope:Scope, global_vals:Dict[str,Any]) -> None:
  'Class declaration.'

  class_source = ScopeSource(path=scope.path, node=syntax, vals=vars(obj))
  c = Class(path=scope.path, name=name, doc=class_source.doc)

  for member_name, syntax, member in class_source:
    parse_decl(syntax, name=member_name, obj=member, scope=c, global_vals=global_vals)

  # Register this custom type in our global dictionary.
  type_infos[obj] = TypeInfo(obj,
    c_type=f'{name} *', c_init='NULL', c_arg_parser_fmt='o', return_conv='(PyObject*)')

  scope.decls.append(c)


# Code generation.

_Writers = Tuple[Callable[[VarArg(str)],None],...] # Cheap hack to provied convenience writer functions.

def write_module(mod:ExtMod, c:TextIO, h:TextIO) -> None:
  'Generate code for a module.'

  def bZ(*strings:str) -> None:
    'Both.'
    for s in strings:
      c.write(s)
      h.write(s)

  def bL(*strings:str) -> None:
    bZ(*strings, '\n')

  def cZ(*strings:str) -> None:
    'C only.'
    for s in strings: c.write(s)

  def cL(*strings:str) -> None:
    cZ(*strings, '\n')

  def hZ(*strings:str) -> None:
    'Header only.'
    for s in strings: h.write(s)

  def hL(*strings:str) -> None:
    hZ(*strings, '\n')

  writers = (bZ, bL, cZ, cL, hZ, hL)

  bL('// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.') # TODO: license config.
  bL()

  hL('#define PY_SSIZE_T_CLEAN')
  hL('#include "Python.h"')

  cL(f'#include "{mod.name}.h"')

  write_scope(scope=mod, prefix='', writers=writers)

  cL()
  cL()
  cL( 'static struct PyModuleDef module_def = {')
  cL( '  PyModuleDef_HEAD_INIT,')
  cL(f'  .m_name = "{mod.name}",')
  cL(f'  .m_doc = {mod.name}_doc,')
  cL( '  .m_size = 0,')
  cL(f'  .m_methods = {mod.name}_methods,')
  cL( '  .m_slots = NULL, // Single-phase initialization.')
  cL( '};')

  cL()
  cL()
  cL('PyMODINIT_FUNC')
  cL('PyInit_hashing_cpy(void) {')
  cL()
  cL('  PyObject *module = PyModule_Create(&module_def);')
  cL('  if (!module) return NULL;')

  for decl in mod.decls:
    if not isinstance(decl, Class):continue
    type_obj = decl.name + '_type'
    cL()
    cL(f'  if (PyType_Ready(&{type_obj}) < 0) return NULL;')
    cL(f'  Py_INCREF(&Aquahash_type);')
    cL(f'  PyModule_AddObject(module, {type_obj}.tp_name, (PyObject *)&{type_obj});')

  cL()
  cL('  return module;')
  cL('}')


def write_doc(name:str, doc:str, writers:_Writers) -> None:
  (bZ, bL, cZ, cL, hZ, hL) = writers

  cL()
  cL(f'PyDoc_STRVAR({name}_doc,')
  for line in doc.strip().split('\n'):
    cL(c_quote(line))
  cL(');')


def write_scope(scope:Scope, prefix:str, writers:_Writers) -> None:
  (bZ, bL, cZ, cL, hZ, hL) = writers

  cL()
  write_doc(name=scope.name, doc=scope.doc, writers=writers)
  methods:List[str] = []
  for decl in scope.decls:
    if isinstance(decl, Var):
      write_var(decl, writers=writers)
    elif isinstance(decl, Func):
      method = write_func(decl, prefix=prefix, writers=writers)
      if method: methods.append(method)
    elif isinstance(decl, Class):
      write_class(decl, writers=writers)
    else: raise NotImplementedError

  cL()
  cL()
  cL(f'static struct PyMethodDef {scope.name}_methods[] = {{')
  for method in methods:
    cL('  ', method, ',')
  cL('  {NULL, NULL}')
  cL('};')


invalid_doc_re = re.compile(r'[^\n -~]+')

def c_quote(s:str) -> str:
  q = s # TODO
  return f'"{q}"'

c_chars = {
  '\n' : '\\n',
  '\\' : '\\\\',
  '"' : '\\"',
}


def write_var(var:Var, writers:_Writers) -> None:
  (bZ, bL, cZ, cL, hZ, hL) = writers
  bL()
  bL()
  bL(f'// `{var.name}:{var.type}`.')


def write_func(func:Func, prefix:str, writers:_Writers) -> str:

  (bZ, bL, cZ, cL, hZ, hL) = writers

  name = prefix + func.name

  bL()
  bL()
  bL(f'// `def {func.name}{func.sig}`.')

  write_doc(name=name, doc=func.doc, writers=writers)

  if func.kind == FuncKind.Plain:
    lead_c_par = 'PyObject *module'
    lead_h_par:List[str] = []
  elif func.kind == FuncKind.Method:
    lead_c_par = f'{func.type_name} *{func.pars[0].name}'
    lead_h_par = [lead_c_par]
  else:
    lead_c_par = f'PyTypeObject *{func.pars[0].name}'
    lead_h_par = [lead_c_par]

  pars = func.pars
  if func.kind != FuncKind.Plain: pars = pars[1:] # Drop the leading variable, which is handled above.
  has_pars = bool(pars)

  h_pars = ', '.join(lead_h_par + [f'{p.ti.c_type}{p.name}' for p in pars])
  ret_ti = type_infos.get(func.ret, type_info_any)
  h_ret_type = ret_ti.c_type

  hL(f'inline static {h_ret_type}{name}({h_pars}) {{')
  hL('}')

  cL()
  cL()
  c_args = 'PyObject *args, PyObject *kwargs' if has_pars else 'PyObject *noargs'
  cL(f'static PyObject *_{name}({lead_c_par}, {c_args}) {{')

  if ret_ti.c_type != 'void ':
    cL(f'  {ret_ti.c_type}_ret = {ret_ti.c_init};')
  cL('  PyObject *ret = NULL;')
  # Generate argument local variables.
  for par in pars:
    cL(f'  {par.ti.c_type}{par.name} = {par.ti.c_init};')

  if has_pars:
    cL()

    c_arg_strs = ', '.join(f'"{p.name}"' for p in pars)
    cL(f'  static const char * const _keywords[] = {{{c_arg_strs}, NULL}};')

    parser_fmts:List[str] = []
    fmt_dflt = False
    for p in pars:
      if not fmt_dflt and p.dflt is not empty: # TODO: this would be better determined by value of Parameter.kind.
        fmt_dflt = True
        parser_fmts.append('|$')
      parser_fmts.append(p.ti.c_arg_parser_fmt)
    parser_fmt = ''.join(parser_fmts)
    fmt_name = func.type_name if (func.type_name and func.name == '__new__') else func.name
    cL(f'  static _PyArg_Parser _parser = {{"{parser_fmt}:{fmt_name}", _keywords, 0}};')

    c_arg_addrs = ', '.join(f'&{p.name}' for p in pars)
    cL(f'  if (!_PyArg_ParseTupleAndKeywordsFast(args, kwargs, &_parser, {c_arg_addrs})) goto cleanup;')
    cL()

  h_args = ', '.join(p.name for p in func.pars) # Note: original list includes the first argument.
  if ret_ti.type is None:
    cL(f'  {name}({h_args});')
    cL( '  ret = Py_None;')
    cL(f'  Py_INCREF(ret);')
  else:
    cL(f'  _ret = {name}({h_args});')
    cL(f'  ret = {ret_ti.return_conv}(_ret);')

  if has_pars:
    cL('\n  cleanup:')
    for par in pars:
      cleanup = par.c_arg_cleanup
      if cleanup: cL(f'  {cleanup};')

  cL('  return ret;')
  cL('}')

  if func.type_name and func.name == '__new__': return '' # Not a member of the method table.
  method_kind = 'METH_VARARGS|METH_KEYWORDS' if has_pars else 'METH_NOARGS'
  return f'{{"{func.name}", (PyCFunction)_{name}, {method_kind}, {name}_doc}}'



def write_class(class_:Class, writers:_Writers) -> None:
  (bZ, bL, cZ, cL, hZ, hL) = writers

  name = class_.name
  bL()
  bL()
  bL(f'// `class {name}`.')

  bL()
  hL(f'inline static void {name}_dealloc({name} *self) {{')
  hL('}')

  cL(f'static void _{name}_dealloc({name} *self) {{')
  cL(f'  {name}_dealloc(self);')
  cL( '  PyObject_Del(self);')
  cL( '}')

  prefix = name + '_'
  write_scope(class_, prefix=prefix, writers=writers)
  bL()

  cL(f'static PyTypeObject {name}_type = {{')
  cL('    PyVarObject_HEAD_INIT(NULL, 0)')
  cL(f'    .tp_name = "{name}",')
  cL(f'    .tp_basicsize = sizeof({name}),')
  cL(f'    .tp_doc = {name}_doc,')
  cL(f'    .tp_dealloc = (destructor)_{name}_dealloc,')
  cL( '    .tp_flags = Py_TPFLAGS_DEFAULT,')
  cL(f'    .tp_methods = {name}_methods,')
  cL(f'    .tp_new = _{name}___new__,')
  cL( '};')


def src_diagnostic(path:str, line0:int, col0:int, msg:str, text:str=None) -> str:
  pad = ' ' * col0
  if text is None:
    text = read_line_from_path(path, line_index=line0, default='<MISSING>')
  return f'{path}:{line0+1}:{col0+1}: {msg}.\n  {text}\n  {pad}^'


def node_diagnostic(path:str, node:AST, msg:str) -> str:
  line0 = getattr(node, 'lineno', 1) - 1 # `Module` has no lineno.
  col0 = getattr(node, 'col_offset', 0)
  return src_diagnostic(path=path, line0=line0, col0=col0, msg=msg)


if __name__ == '__main__': main()
