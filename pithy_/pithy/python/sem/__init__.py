# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ast import (Add, alias, And, AnnAssign, arg, arguments, Assert, Assign, AST, AsyncFor, AsyncFunctionDef, AsyncWith,
  Attribute, AugAssign, Await, BinOp, BitAnd, BitOr, BitXor, boolop, BoolOp, Break, Call, ClassDef, cmpop, Compare,
  comprehension, Constant, Continue, Del, Delete, Dict, DictComp, Div, Eq, ExceptHandler, excepthandler, expr, Expr,
  expr_context, Expression, FloorDiv, For, FormattedValue, FunctionDef, FunctionType, GeneratorExp, Global, Gt, GtE, If, IfExp,
  Import, ImportFrom, In, Interactive, Interpolation, Invert, Is, IsNot, JoinedStr, keyword, Lambda, List, ListComp, Load,
  LShift, Lt, LtE, Match, match_case, MatchAs, MatchClass, MatchMapping, MatchOr, MatchSequence, MatchSingleton, MatchStar,
  MatchValue, MatMult, mod, Mod, Module, Mult, Name, NamedExpr, Nonlocal, Not, NotEq, NotIn, operator, Or, ParamSpec,
  parse as parse_ast, Pass, pattern, Pow, Raise, Return, RShift, Set, SetComp, Slice, Starred, stmt, Store, Sub, Subscript,
  TemplateStr, Try, TryStar, Tuple, type_ignore, type_param, TypeAlias, TypeIgnore, TypeVar, TypeVarTuple, UAdd, UnaryOp,
  unaryop, USub, While, With, withitem, Yield, YieldFrom)
from functools import cached_property
from inspect import get_annotations
from typing import cast, ClassVar, Iterable, Iterator, Literal

from tolkien import Source

from ...type_utils import req_type


'''
`pithy.python.sem` defines the `Sem` class family that mirrors the stdlib `ast.AST` family.
'''

def sem_for_source(source:Source) -> SemModule:
  # parse_ast defaults to mode='exec', which always produces a Module node.
  # SemExpression, SemInteractive, and SemFunctionType are unreachable here;
  # they require mode='eval', 'single', or 'func_type' respectively.
  sem = Sem(parse_ast(source.text, filename=source.name, type_comments=True))
  if not isinstance(sem, SemModule): raise TypeError(sem)
  return sem


_setattr = object.__setattr__


type RefCtx = Literal['load', 'store', 'del']
_ctx_map:dict[type,RefCtx] = {Load: 'load', Store: 'store', Del: 'del'}
#^ These three AST subtypes are essentially an enum so we convert them to string literals.


ast_field_simple_types = {
  int,
  str,
  object,
  int | None,
  str | None,
  arg | None,
  expr | None,
  pattern | None,
  list[str],
}

ast_field_node_types = {
  arguments,
  boolop,
  expr,
  expr_context,
  operator,
  pattern,
  unaryop,
  list[alias],
  list[arg],
  list[cmpop],
  list[comprehension],
  list[excepthandler],
  list[expr],
  list[keyword],
  list[match_case],
  list[pattern],
  list[stmt],
  list[type_ignore],
  list[type_param],
  list[withitem],
}

ast_field_types = ast_field_simple_types | ast_field_node_types


type AstField = None|int|str|object|AST|list[str]|list[AST]
type SemField = None|int|str|object|Sem|list[str]|list[Sem]

def _sem_field(field:AstField, els:list[Sem]|None=None) -> SemField:
  '''
  Transform an AST field value into a corresponding Sem field.
  Also append non-None results to the `els` list to build a generic list of children.
  '''
  if isinstance(field, AST):
    try: return _ctx_map[type(field)]
    except KeyError: pass
    el:SemField = Sem(field)
    if els is not None:
      els.append(el) # type: ignore[arg-type]
    return el
  elif isinstance(field, list):
    return [_sem_field(field_el, els) for field_el in field]
  else:
    return field


class Sem:
  '''
  A semantic element corresponding to a parsed AST element.

  The purpose of this class family is to make working with source trees easier.

  Each Sem subtype corresponds to an AST subtype.
  The AST element property has a distinct name beginning with `ast_` for each Sem subtype, e.g. `ast_constant`.
  The same element can be accessed by loosely typed property `ast`.
  For each subclass the strict property name is defined as the class var `ast_key`.

  SemNode (non-leaf elements) have a generic `els`
  '''

  ast_key: ClassVar[str] # The name under which the strictly typed AST element is stored.


  def __new__(cls, ast:AST) -> Sem:
    'Dynamically select the matching `Sem` subclass.'
    sem_cls = ast_to_sem_types[type(ast)]
    instance = super(Sem, sem_cls).__new__(sem_cls)
    return instance


  def __init__(self, ast:AST):
    raise NotImplementedError('Sem is abstract; subclass  must implement __init__')


  def __setattr__(self, name:str, value:object) -> None:
    'Prevent naive mutation.'
    raise AttributeError(f'Cannot set attribute {name} on {self.__class__.__name__}')


  @classmethod
  def type_abbr(cls) -> str:
    'The abbreviated type name.'
    # Note: class-level caches use `cls.__dict__` lookups so that a subclass does not inherit its parent's cached value.
    try: return cast(str, cls.__dict__['type_abbr_cached'])
    except KeyError: pass

    abbr = cls.__name__.removeprefix('Sem')
    setattr(cls, 'type_abbr_cached', abbr)
    return abbr


  @classmethod
  def _field_inlines(cls) -> dict[str,bool]:

    try: return cast(dict[str,bool], cls.__dict__['_field_inlines_cached'])
    except KeyError: pass

    field_inlines:dict[str,bool] = {}
    setattr(cls, '_field_inlines_cached', field_inlines)

    if not hasattr(cls, 'ast_key'): return field_inlines # An abstract class; no fields.

    if issubclass(cls, SemRef):
      field_inlines['ctx'] = True

    anns = get_annotations(cls)
    inlining = True
    for name, field_type in anns.items():
      if name in ('ast_key', cls.ast_key): continue
      if field_type not in ast_field_simple_types:
        inlining = False # Stop inlining at the first Sem or list[Sem].
      field_inlines[name] = inlining # Stopped at the first Sem or typed collection.

    return field_inlines


  @classmethod
  def _inline_field_names(cls) -> list[str]:

    try: return cast(list[str], cls.__dict__['_inline_field_names_cached'])
    except KeyError: pass

    inline_fields = [k for k, v in cls._field_inlines().items() if v]
    setattr(cls, '_inline_field_names_cached', inline_fields)

    return inline_fields


  @classmethod
  def _multiline_field_names(cls) -> list[str]:

    try: return cast(list[str], cls.__dict__['_multiline_field_names_cached'])
    except KeyError: pass

    multiline_fields = [k for k, v in cls._field_inlines().items() if not v]
    setattr(cls, '_multiline_field_names_cached', multiline_fields)

    return multiline_fields


  @property
  def ast(self) -> AST:
    'The generally typed AST element corresponding to this semantic element.'
    return cast(AST, getattr(self, self.ast_key))


  def __repr__(self) -> str:
    attrs = ', '.join(f'{k}={v!r}' for k, v in self.inline_attrs())
    return f'{self.__class__.__name__}:{self.line_num}:{self.col_num}({attrs})'


  def render(self, *, source:Source, indent:str='', label:str='', line_width:int|None=None, col_width:int|None=None) -> Iterator[str]:

    if line_width is None: line_width = len(str(self.max_line_num))
    if col_width is None: col_width = len(str(self.max_col_num))

    prefix = f'{source.name}:{self.line_num:0{line_width}}:{self.col_num:0{col_width}}{indent}'

    if label: label = f'{label}: '
    attrs = ' '.join(f'{k}={v!r}' for k, v in self.inline_attrs())

    yield f'{prefix} {label}{self.type_abbr()} {attrs}'

    if ml_names := self._multiline_field_names():

      sub_indent = indent + '  '
      for n in ml_names:
        f = getattr(self, n)
        if isinstance(f, Sem):
          yield from f.render(source=source, indent=sub_indent, label=label, line_width=line_width, col_width=col_width)
        elif isinstance(f, list):
          one_line = '' if (f and isinstance(f[0], Sem)) else ' '+repr(f)
          yield f'{prefix}  .{n}:{one_line}'
          if not one_line:
            for el in f:
              yield from el.render(source=source, indent=sub_indent, label=label, line_width=line_width, col_width=col_width)
        else:
          yield f'{prefix}  .{n}:{f}'



  def render_str(self, *, source:Source) -> str:
    return '\n'.join(self.render(source=source))


  def inline_attrs(self) -> Iterable[tuple[str,object]]:
    return [(n, getattr(self, n)) for n in self._inline_field_names()]


  @cached_property
  def line_num(self) -> int:
    if lineno := getattr(self.ast, 'lineno', None): return req_type(lineno, int)
    if isinstance(self, SemNode) and self.els: return self.els[0].line_num
    return 0


  @cached_property
  def col_num(self) -> int:
    'Note: col_offset is a UTF-8 byte offset and is therefore not visually accurate.'
    try: return req_type(getattr(self.ast, 'col_offset'), int) + 1
    except AttributeError:
      if isinstance(self, SemNode) and self.els: return self.els[0].col_num
    return 0


  @cached_property
  def max_line_num(self) -> int:
    return self.line_num


  @cached_property
  def max_col_num(self) -> int:
    return self.col_num


  def walk(self) -> Iterator['Sem']:
    '''
    Yield self and all sub-elements in depth-first traversal order.
    '''
    yield self



class SemLeaf(Sem):
  '''
  A semantic leaf element; does not have sub-elements.
  '''

  def __init__(self, ast:AST):
    _setattr(self, self.ast_key, ast)
    for field_name in ast._fields:
      _setattr(self, field_name, _sem_field(getattr(ast, field_name)))




class SemNode(Sem):
  '''
  A semantic tree element that has sub-elements; not a leaf.
  '''

  els: list[Sem]


  def __init__(self, ast:AST):
    _setattr(self, self.ast_key, ast)
    els:list[Sem] = []
    _setattr(self, 'els', els)
    for field_name in ast._fields:
      _setattr(self, field_name, _sem_field(getattr(ast, field_name), els))


  @cached_property
  def max_line_num(self) -> int:
    if self.els: return max(self.line_num, *[el.max_line_num for el in self.els])
    else: return self.line_num


  @cached_property
  def max_col_num(self) -> int:
    if self.els: return max(self.col_num, *[el.max_col_num for el in self.els])
    else: return self.col_num


  def iter_refs(self) -> Iterator[SemRef]:
    for el in self.els:
      if isinstance(el, SemRef): yield el
      if isinstance(el, SemNode) and not (isinstance(el, SemScope) and el.explicit):
        yield from el.iter_refs()


  def walk(self) -> Iterator['Sem']:
    yield self
    for el in self.els: yield from el.walk()


class SemScope(SemNode):
  '''
  A semantic tree node that represents a scope.
  `explicit` indicates whether it corresponds to a true python scope.
  Modules, classes, and functions, and comprehensions all have explicit scopes.
  Conditional statements, loops, and try/except/finally blocks do not.
  `Sem` models the implicit scopes of local variables defined inside of such code blocks.
  '''
  explicit: ClassVar[bool]



class SemRef(SemNode):
  '''
  A semantic node for `ast.expr` types that carry an `expr_context` (Load, Store, Del).
  Covers: SemName, SemAttribute, SemSubscript, SemStarred, SemList, SemTuple.
  '''

  ctx: RefCtx


class Sem_mod(Sem):
  'Corresponds to `ast.mod`.'


class SemModule(SemScope, Sem_mod):
  '''
  `Module` represents a Python module; generated by `ast.parse(..., mode='exec')`.
  '''
  explicit = True
  ast_key = 'ast_module'
  ast_module: Module

  body: list[Sem_stmt]
  type_ignores: list[SemTypeIgnore]


class SemExpression(SemNode, Sem_mod):
  '''
  `Expression` is a single Python expression; generated by `ast.parse(..., mode='eval')`.
  '''
  ast_key = 'ast_expression'
  ast_expression: Expression

  body: SemExpr


class SemInteractive(SemNode, Sem_mod):
  '''
  `Interactive` is a single Python statement; generated by `ast.parse(..., mode='single')`.
  '''
  explicit = True
  ast_key = 'ast_interactive'
  ast_interactive: Interactive

  body: list[Sem_stmt]


class SemFunctionType(SemNode, Sem_mod):
  '''
  Representation of old-style type comments used prior to Python 3.5 / PEP 484.
  '''
  ast_key = 'ast_function_type'
  ast_function_type: FunctionType

  argtypes: list[SemExpr]
  returns: SemExpr


class Sem_stmt(Sem):
  'Corresponds to `ast.stmt`.'


class SemFunctionDef(SemScope, Sem_stmt):
  explicit = True
  ast_key = 'ast_function_def'
  ast_function_def: FunctionDef

  name: str
  args: SemArguments
  body: list[Sem_stmt]
  decorator_list: list[SemExpr]
  returns: SemExpr|None
  type_comment: str|None
  type_params: list[Sem_type_param]


class SemAsyncFunctionDef(SemScope, Sem_stmt):
  explicit = True
  ast_key = 'ast_async_function_def'
  ast_async_function_def: AsyncFunctionDef

  name: str
  args: SemArguments
  body: list[Sem_stmt]
  decorator_list: list[SemExpr]
  returns: SemExpr|None
  type_comment: str|None
  type_params: list[Sem_type_param]


class SemClassDef(SemScope, Sem_stmt):
  explicit = True
  ast_key = 'ast_class_def'
  ast_class_def: ClassDef

  name: str
  bases: list[SemExpr]
  keywords: list[SemKeyword]
  body: list[Sem_stmt]
  decorator_list: list[SemExpr]
  type_params: list[Sem_type_param]


class SemReturn(SemNode, Sem_stmt):
  ast_key = 'ast_return'
  ast_return: Return

  value: SemExpr|None


class SemDelete(SemNode, Sem_stmt):
  ast_key = 'ast_delete'
  ast_delete: Delete

  targets: list[SemExpr]


class SemAssign(SemNode, Sem_stmt):
  ast_key = 'ast_assign'
  ast_assign: Assign

  targets: list[SemExpr]
  value: SemExpr
  type_comment: str|None


class SemTypeAlias(SemNode, Sem_stmt):
  ast_key = 'ast_type_alias'
  ast_type_alias: TypeAlias

  name: SemExpr
  type_params: list[Sem_type_param]
  value: SemExpr


class SemAugAssign(SemNode, Sem_stmt):
  ast_key = 'ast_aug_assign'
  ast_aug_assign: AugAssign

  target: SemExpr
  op: Sem_operator
  value: SemExpr


class SemAnnAssign(SemNode, Sem_stmt):
  ast_key = 'ast_ann_assign'
  ast_ann_assign: AnnAssign

  target: SemExpr
  annotation: SemExpr
  value: SemExpr|None
  simple: int


class SemFor(SemScope, Sem_stmt):
  explicit = False
  ast_key = 'ast_for'
  ast_for: For

  target: SemExpr
  iter: SemExpr
  body: list[Sem_stmt]
  orelse: list[Sem_stmt]
  type_comment: str|None


class SemAsyncFor(SemScope, Sem_stmt):
  explicit = False
  ast_key = 'ast_async_for'
  ast_async_for: AsyncFor

  target: SemExpr
  iter: SemExpr
  body: list[Sem_stmt]
  orelse: list[Sem_stmt]
  type_comment: str|None


class SemWhile(SemScope, Sem_stmt):
  explicit = False
  ast_key = 'ast_while'
  ast_while: While

  test: SemExpr
  body: list[Sem_stmt]
  orelse: list[Sem_stmt]


class SemIf(SemScope, Sem_stmt):
  explicit = False
  ast_key = 'ast_if'
  ast_if: If

  test: SemExpr
  body: list[Sem_stmt]
  orelse: list[Sem_stmt]


class SemWith(SemScope, Sem_stmt):
  explicit = False
  ast_key = 'ast_with'
  ast_with: With

  items: list[SemWithItem]
  body: list[Sem_stmt]
  type_comment: str|None


class SemAsyncWith(SemScope, Sem_stmt):
  explicit = False
  ast_key = 'ast_async_with'
  ast_async_with: AsyncWith

  items: list[SemWithItem]
  body: list[Sem_stmt]
  type_comment: str|None


class SemMatch(SemScope, Sem_stmt):
  explicit = False
  ast_key = 'ast_match'
  ast_match: Match

  subject: SemExpr
  cases: list[SemMatchCase]


class SemRaise(SemNode, Sem_stmt):
  ast_key = 'ast_raise'
  ast_raise: Raise

  exc: SemExpr|None
  cause: SemExpr|None


class SemTry(SemScope, Sem_stmt):
  explicit = False
  ast_key = 'ast_try'
  ast_try: Try

  body: list[Sem_stmt]
  handlers: list[SemExceptHandler]
  orelse: list[Sem_stmt]
  finalbody: list[Sem_stmt]


class SemTryStar(SemScope, Sem_stmt):
  explicit = False
  ast_key = 'ast_try_star'
  ast_try_star: TryStar

  body: list[Sem_stmt]
  handlers: list[SemExceptHandler]
  orelse: list[Sem_stmt]
  finalbody: list[Sem_stmt]


class SemAssert(SemNode, Sem_stmt):
  ast_key = 'ast_assert'
  ast_assert: Assert

  test: SemExpr
  msg: SemExpr|None


class SemImport(SemNode, Sem_stmt):
  ast_key = 'ast_import'
  ast_import: Import

  names: list[SemAlias]


class SemImportFrom(SemNode, Sem_stmt):
  ast_key = 'ast_import_from'
  ast_import_from: ImportFrom

  module: str|None
  names: list[SemAlias]
  level: int|None


class SemGlobal(SemLeaf, Sem_stmt):
  ast_key = 'ast_global'
  ast_global: Global

  names: list[str]


class SemNonlocal(SemLeaf, Sem_stmt):
  ast_key = 'ast_nonlocal'
  ast_nonlocal: Nonlocal

  names: list[str]


class SemExpr(SemNode, Sem_stmt):
  ast_key = 'ast_expr'
  ast_expr: Expr

  value: SemExpr


class SemPass(SemLeaf, Sem_stmt):
  ast_key = 'ast_pass'
  ast_pass: Pass


class SemBreak(SemLeaf, Sem_stmt):
  ast_key = 'ast_break'
  ast_break: Break


class SemContinue(SemLeaf, Sem_stmt):
  ast_key = 'ast_continue'
  ast_continue: Continue


class Sem_expr(Sem):
  'Corresponds to `ast.expr`.'


class SemBoolOp(SemNode, Sem_expr):
  ast_key = 'ast_bool_op'
  ast_bool_op: BoolOp

  op: Sem_boolop
  values: list[SemExpr]


class SemNamedExpr(SemNode, Sem_expr):
  ast_key = 'ast_named_expr'
  ast_named_expr: NamedExpr

  target: SemExpr
  value: SemExpr


class SemBinOp(SemNode, Sem_expr):
  ast_key = 'ast_bin_op'
  ast_bin_op: BinOp

  left: SemExpr
  op: Sem_operator
  right: SemExpr


class SemUnaryOp(SemNode, Sem_expr):
  ast_key = 'ast_unary_op'
  ast_unary_op: UnaryOp

  op: Sem_unaryop
  operand: SemExpr


class SemLambda(SemScope, Sem_expr):
  explicit = True
  ast_key = 'ast_lambda'
  ast_lambda: Lambda

  args: SemArguments
  body: SemExpr


class SemIfExp(SemNode, Sem_expr):
  ast_key = 'ast_if_exp'
  ast_if_exp: IfExp

  test: SemExpr
  body: SemExpr
  orelse: SemExpr


class SemDict(SemNode, Sem_expr):
  ast_key = 'ast_dict'
  ast_dict: Dict

  keys: list[SemExpr]
  values: list[SemExpr]


class SemSet(SemNode, Sem_expr):
  ast_key = 'ast_set'
  ast_set: Set

  elts: list[SemExpr]


class SemListComp(SemScope, Sem_expr):
  explicit = True
  ast_key = 'ast_list_comp'
  ast_list_comp: ListComp

  elt: SemExpr
  generators: list[SemComprehension]


class SemSetComp(SemScope, Sem_expr):
  explicit = True
  ast_key = 'ast_set_comp'
  ast_set_comp: SetComp

  elt: SemExpr
  generators: list[SemComprehension]


class SemDictComp(SemScope, Sem_expr):
  explicit = True
  ast_key = 'ast_dict_comp'
  ast_dict_comp: DictComp

  key: SemExpr
  value: SemExpr
  generators: list[SemComprehension]


class SemGeneratorExp(SemScope, Sem_expr):
  explicit = True
  ast_key = 'ast_generator_exp'
  ast_generator_exp: GeneratorExp

  elt: SemExpr
  generators: list[SemComprehension]


class SemAwait(SemNode, Sem_expr):
  ast_key = 'ast_await'
  ast_await: Await

  value: SemExpr


class SemYield(SemNode, Sem_expr):
  ast_key = 'ast_yield'
  ast_yield: Yield

  value: SemExpr|None


class SemYieldFrom(SemNode, Sem_expr):
  ast_key = 'ast_yield_from'
  ast_yield_from: YieldFrom

  value: SemExpr


class SemCompare(SemNode, Sem_expr):
  ast_key = 'ast_compare'
  ast_compare: Compare

  left: SemExpr
  ops: list[Sem_cmpop]
  comparators: list[SemExpr]


class SemCall(SemNode, Sem_expr):
  ast_key = 'ast_call'
  ast_call: Call

  func: SemExpr
  args: list[SemExpr]
  keywords: list[SemKeyword]


class SemFormattedValue(SemNode, Sem_expr):
  ast_key = 'ast_formatted_value'
  ast_formatted_value: FormattedValue

  value: SemExpr
  conversion: int
  format_spec: SemExpr|None


class SemJoinedStr(SemNode, Sem_expr):
  'JoinedStr is "An f-string, comprising a series of FormattedValue and Constant nodes."'

  ast_key = 'ast_joined_str'
  ast_joined_str: JoinedStr

  values: list[SemExpr]


class SemTemplateStr(SemNode, Sem_expr):
  ast_key = 'ast_template_str'
  ast_template_str: TemplateStr

  values: list[SemExpr]


class SemInterpolation(SemNode, Sem_expr):
  ast_key = 'ast_interpolation'
  ast_interpolation: Interpolation

  value: SemExpr
  str: object
  conversion: int
  format_spec: SemExpr|None


class SemConstant(SemLeaf, Sem_expr):
  ast_key = 'ast_constant'
  ast_constant: Constant

  value: object
  kind: str|None


class SemAttribute(SemRef, Sem_expr):
  ast_key = 'ast_attribute'
  ast_attribute: Attribute

  value: SemExpr
  attr: str


class SemSubscript(SemRef, Sem_expr):
  ast_key = 'ast_subscript'
  ast_subscript: Subscript

  value: SemExpr
  slice: SemExpr


class SemStarred(SemRef, Sem_expr):
  ast_key = 'ast_starred'
  ast_starred: Starred

  value: SemExpr


class SemName(SemRef, Sem_expr):
  ast_key = 'ast_name'
  ast_name: Name

  id: str


class SemList(SemRef, Sem_expr):
  ast_key = 'ast_list'
  ast_list: List

  elts: list[SemExpr]


class SemTuple(SemRef, Sem_expr):
  ast_key = 'ast_tuple'
  ast_tuple: Tuple

  elts: list[SemExpr]


class SemSlice(SemNode, Sem_expr):
  ast_key = 'ast_slice'
  ast_slice: Slice

  lower: SemExpr|None
  upper: SemExpr|None
  step: SemExpr|None


class Sem_boolop(Sem):
  'Corresponds to `ast.boolop`.'


class SemAnd(SemLeaf, Sem_boolop):
  ast_key = 'ast_and'
  ast_and: And


class SemOr(SemLeaf, Sem_boolop):
  ast_key = 'ast_or'
  ast_or: Or


class Sem_operator(Sem):
  'Corresponds to `ast.operator`.'


class SemAdd(SemLeaf, Sem_operator):
  ast_key = 'ast_add'
  ast_add: Add


class SemSub(SemLeaf, Sem_operator):
  ast_key = 'ast_sub'
  ast_sub: Sub


class SemMult(SemLeaf, Sem_operator):
  ast_key = 'ast_mult'
  ast_mult: Mult


class SemMatMult(SemLeaf, Sem_operator):
  ast_key = 'ast_mat_mult'
  ast_mat_mult: MatMult


class SemDiv(SemLeaf, Sem_operator):
  ast_key = 'ast_div'
  ast_div: Div


class SemMod(SemLeaf, Sem_operator):
  ast_key = 'ast_mod'
  ast_mod: Mod


class SemPow(SemLeaf, Sem_operator):
  ast_key = 'ast_pow'
  ast_pow: Pow


class SemLShift(SemLeaf, Sem_operator):
  ast_key = 'ast_l_shift'
  ast_l_shift: LShift


class SemRShift(SemLeaf, Sem_operator):
  ast_key = 'ast_r_shift'
  ast_r_shift: RShift


class SemBitOr(SemLeaf, Sem_operator):
  ast_key = 'ast_bit_or'
  ast_bit_or: BitOr


class SemBitXor(SemLeaf, Sem_operator):
  ast_key = 'ast_bit_xor'
  ast_bit_xor: BitXor


class SemBitAnd(SemLeaf, Sem_operator):
  ast_key = 'ast_bit_and'
  ast_bit_and: BitAnd


class SemFloorDiv(SemLeaf, Sem_operator):
  ast_key = 'ast_floor_div'
  ast_floor_div: FloorDiv


class Sem_unaryop(Sem):
  'Corresponds to `ast.unaryop`.'


class SemInvert(SemLeaf, Sem_unaryop):
  ast_key = 'ast_invert'
  ast_invert: Invert


class SemNot(SemLeaf, Sem_unaryop):
  ast_key = 'ast_not'
  ast_not: Not


class SemUAdd(SemLeaf, Sem_unaryop):
  ast_key = 'ast_u_add'
  ast_u_add: UAdd


class SemUSub(SemLeaf, Sem_unaryop):
  ast_key = 'ast_u_sub'
  ast_u_sub: USub


class Sem_cmpop(Sem):
  'Corresponds to `ast.cmpop`.'


class SemEq(SemLeaf, Sem_cmpop):
  ast_key = 'ast_eq'
  ast_eq: Eq


class SemNotEq(SemLeaf, Sem_cmpop):
  ast_key = 'ast_not_eq'
  ast_not_eq: NotEq


class SemLt(SemLeaf, Sem_cmpop):
  ast_key = 'ast_lt'
  ast_lt: Lt


class SemLtE(SemLeaf, Sem_cmpop):
  ast_key = 'ast_lt_e'
  ast_lt_e: LtE


class SemGt(SemLeaf, Sem_cmpop):
  ast_key = 'ast_gt'
  ast_gt: Gt


class SemGtE(SemLeaf, Sem_cmpop):
  ast_key = 'ast_gt_e'
  ast_gt_e: GtE


class SemIs(SemLeaf, Sem_cmpop):
  ast_key = 'ast_is'
  ast_is: Is


class SemIsNot(SemLeaf, Sem_cmpop):
  ast_key = 'ast_is_not'
  ast_is_not: IsNot


class SemIn(SemLeaf, Sem_cmpop):
  ast_key = 'ast_in'
  ast_in: In


class SemNotIn(SemLeaf, Sem_cmpop):
  ast_key = 'ast_not_in'
  ast_not_in: NotIn


class SemComprehension(SemNode):
  ast_key = 'ast_comprehension'
  ast_comprehension: comprehension

  target: SemExpr
  iter: SemExpr
  ifs: list[SemExpr]
  is_async: int


class SemExceptHandler(SemNode):
  '''
  Note: `ast.ExceptHandler` is the sole subclass of `ast.excepthandler`.
  '''
  ast_key = 'ast_except_handler'
  ast_except_handler: ExceptHandler

  type: SemExpr|None
  name: str|None
  body: list[Sem_stmt]


class Sem_pattern(Sem):
  'Corresponds to `ast.pattern` types.'


class SemMatchCase(SemNode, Sem_pattern):
  ast_key = 'ast_match_case'
  ast_match_case: match_case

  pattern: Sem_pattern
  guard: SemExpr|None
  body: list[Sem_stmt]


class SemMatchValue(SemNode, Sem_pattern):
  ast_key = 'ast_match_value'
  ast_match_value: MatchValue

  value: SemExpr


class SemMatchSingleton(SemLeaf, Sem_pattern):
  ast_key = 'ast_match_singleton'
  ast_match_singleton: MatchSingleton

  value: object


class SemMatchSequence(SemNode, Sem_pattern):
  ast_key = 'ast_match_sequence'
  ast_match_sequence: MatchSequence

  patterns: list[Sem_pattern]


class SemMatchMapping(SemNode, Sem_pattern):
  ast_key = 'ast_match_mapping'
  ast_match_mapping: MatchMapping

  keys: list[SemExpr]
  patterns: list[Sem_pattern]
  rest: str|None


class SemMatchClass(SemNode, Sem_pattern):
  ast_key = 'ast_match_class'
  ast_match_class: MatchClass

  cls: SemExpr
  patterns: list[Sem_pattern]
  kwd_attrs: list[str]
  kwd_patterns: list[Sem_pattern]


class SemMatchStar(SemLeaf, Sem_pattern):
  ast_key = 'ast_match_star'
  ast_match_star: MatchStar

  name: str|None


class SemMatchAs(SemNode, Sem_pattern):
  ast_key = 'ast_match_as'
  ast_match_as: MatchAs

  pattern: Sem_pattern|None
  name: str|None


class SemMatchOr(SemNode, Sem_pattern):
  ast_key = 'ast_match_or'
  ast_match_or: MatchOr

  patterns: list[Sem_pattern]


class SemTypeIgnore(SemLeaf):
  'Note: `ast.TypeIgnore` is the sole concrete subclass of `ast.type_ignore`.'
  ast_key = 'ast_type_ignore'
  ast_type_ignore: TypeIgnore

  lineno: int
  tag: str


class Sem_type_param(Sem):
  'Corresponds to `ast.type_param` types.'


class SemTypeVar(SemNode, Sem_type_param):
  ast_key = 'ast_type_var'
  ast_type_var: TypeVar

  name: str
  bound: SemExpr|None
  default_value: SemExpr|None


class SemParamSpec(SemNode, Sem_type_param):
  ast_key = 'ast_param_spec'
  ast_param_spec: ParamSpec

  name: str
  default_value: SemExpr|None


class SemTypeVarTuple(SemNode, Sem_type_param):
  ast_key = 'ast_type_var_tuple'
  ast_type_var_tuple: TypeVarTuple

  name: str
  default_value: SemExpr|None


class SemArguments(SemNode):
  ast_key = 'ast_arguments'
  ast_arguments: arguments

  posonlyargs: list[SemArg]
  args: list[SemArg]
  vararg: SemArg|None
  kwonlyargs: list[SemArg]
  kw_defaults: list[SemExpr]
  kwarg: SemArg|None
  defaults: list[SemExpr]


class SemArg(SemNode):
  ast_key = 'ast_arg'
  ast_arg: arg

  arg: str
  annotation: SemExpr|None
  type_comment: str|None


class SemKeyword(SemNode):
  ast_key = 'ast_keyword'
  ast_keyword: keyword

  arg: str|None
  value: SemExpr


class SemAlias(SemLeaf):
  ast_key = 'ast_alias'
  ast_alias: alias

  name: str
  asname: str|None


class SemWithItem(SemNode):
  ast_key = 'ast_withitem'
  ast_withitem: withitem

  context_expr: SemExpr
  optional_vars: SemExpr|None



ast_to_sem_types:dict[type[AST],type[Sem]] = {
  mod : Sem_mod,
  Module : SemModule,
  Interactive : SemInteractive,
  Expression : SemExpression,
  FunctionType : SemFunctionType,
  stmt : Sem_stmt,
  FunctionDef : SemFunctionDef,
  AsyncFunctionDef : SemAsyncFunctionDef,
  ClassDef : SemClassDef,
  Return : SemReturn,
  Delete : SemDelete,
  Assign : SemAssign,
  TypeAlias : SemTypeAlias,
  AugAssign : SemAugAssign,
  AnnAssign : SemAnnAssign,
  For : SemFor,
  AsyncFor : SemAsyncFor,
  While : SemWhile,
  If : SemIf,
  With : SemWith,
  AsyncWith : SemAsyncWith,
  Match : SemMatch,
  Raise : SemRaise,
  Try : SemTry,
  TryStar : SemTryStar,
  Assert : SemAssert,
  Import : SemImport,
  ImportFrom : SemImportFrom,
  Global : SemGlobal,
  Nonlocal : SemNonlocal,
  Expr : SemExpr,
  Pass : SemPass,
  Break : SemBreak,
  Continue : SemContinue,
  expr : SemExpr,
  BoolOp : SemBoolOp,
  NamedExpr : SemNamedExpr,
  BinOp : SemBinOp,
  UnaryOp : SemUnaryOp,
  Lambda : SemLambda,
  IfExp : SemIfExp,
  Dict : SemDict,
  Set : SemSet,
  ListComp : SemListComp,
  SetComp : SemSetComp,
  DictComp : SemDictComp,
  GeneratorExp : SemGeneratorExp,
  Await : SemAwait,
  Yield : SemYield,
  YieldFrom : SemYieldFrom,
  Compare : SemCompare,
  Call : SemCall,
  FormattedValue : SemFormattedValue,
  JoinedStr : SemJoinedStr,
  TemplateStr : SemTemplateStr,
  Interpolation : SemInterpolation,
  Constant : SemConstant,
  Attribute : SemAttribute,
  Subscript : SemSubscript,
  Starred : SemStarred,
  Name : SemName,
  List : SemList,
  Tuple : SemTuple,
  Slice : SemSlice,
  boolop : Sem_boolop,
  And : SemAnd,
  Or : SemOr,
  operator: Sem_operator,
  Add : SemAdd,
  Sub : SemSub,
  Mult : SemMult,
  MatMult : SemMatMult,
  Div : SemDiv,
  Mod : SemMod,
  Pow : SemPow,
  LShift : SemLShift,
  RShift : SemRShift,
  BitOr : SemBitOr,
  BitXor : SemBitXor,
  BitAnd : SemBitAnd,
  FloorDiv : SemFloorDiv,
  unaryop : Sem_unaryop,
  Invert : SemInvert,
  Not : SemNot,
  UAdd : SemUAdd,
  USub : SemUSub,
  cmpop : Sem_cmpop,
  Eq : SemEq,
  NotEq : SemNotEq,
  Lt : SemLt,
  LtE : SemLtE,
  Gt : SemGt,
  GtE : SemGtE,
  Is : SemIs,
  IsNot : SemIsNot,
  In : SemIn,
  NotIn : SemNotIn,
  excepthandler: SemExceptHandler, # Sole child; we flatten it out for clarity.
  ExceptHandler : SemExceptHandler,
  MatchValue : SemMatchValue,
  MatchSingleton : SemMatchSingleton,
  MatchSequence : SemMatchSequence,
  MatchMapping : SemMatchMapping,
  MatchClass : SemMatchClass,
  MatchStar : SemMatchStar,
  MatchAs : SemMatchAs,
  MatchOr : SemMatchOr,
  TypeIgnore : SemTypeIgnore,
  type_param: Sem_type_param,
  TypeVar : SemTypeVar,
  ParamSpec : SemParamSpec,
  TypeVarTuple : SemTypeVarTuple,
  arguments : SemArguments,
  arg : SemArg,
  keyword: SemKeyword,
  alias: SemAlias,
  withitem: SemWithItem,
  comprehension: SemComprehension,
  pattern: Sem_pattern,
  match_case: SemMatchCase,
  type_ignore: SemTypeIgnore,
}
