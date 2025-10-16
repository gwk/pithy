# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
A simple parser library based on recursive descent and operator precedence parsing.
Recursive decent is performed by looking at the next token,
and then dispatching through a table of token kinds to select the appropriate Rule.

Upon parsing, each type of rule produces a generic result object, the type of which is dependent on the rule type.
For example, a Struct rule returns a list of results, whereas a Choice rule returns the choice label and a single result.
The result is then passed to a user-provided (or default) transformer function, whose signature also depends on the rule type.
Transformer functions can return results of any type.

Several types of rules are available:
* Atom: a single token kind.
* Quantity: a body rule, optionally interleaved with a separator token, with optional `min` and `max` quantities.
* Choice: one of several rules, which must be distinguishable by the head token.
* Struct: a fixed-length sequence of heterogenous subrules.
* Precedence: a family of binary precedence operators.

The main design feature of Parser is that operators are not first-class rules:
instead they are parsed within the context of a Precedence rule.
This allows us to use the operator-precedence parsing algorithm,
while expressing other aspects of a grammar using straightforward recursive descent.
'''

from collections import namedtuple
from copy import deepcopy
from dataclasses import dataclass, fields as dc_fields, is_dataclass
from keyword import iskeyword, issoftkeyword
from typing import Any, Callable, cast, Iterable, Iterator, NoReturn, Protocol, TypeVar, Union

from tolkien import get_syntax_slc, Source, Syntax, SyntaxMsg, Token

from ..graph import visit_nodes
from ..io import errL
from ..lex import Lexer, reserved_names, valid_name_re
from ..meta import caller_module_name
from ..stack import Stack
from ..string import indent_lines, iter_str, pluralize, typecase_from_snakecase
from ..type_utils import is_namedtuple
from ..untyped import Immutable


TokenKind = str
RuleName = str
RuleRef = Union['Rule',RuleName]
_T = TypeVar('_T')


class GeneratedStruct(Protocol):
  _fields:tuple[str,...]
  def __init__(self, *args:Any): ...


class ParseError(Exception):
  error_prefix = 'parse'

  def __init__(self, source:Source, syntax:Syntax, msg:str, notes:Iterable[SyntaxMsg]=()):
    self.source = source
    self.notes:list[SyntaxMsg] = list(notes)
    self.syntax = syntax
    self.msg = msg
    super().__init__((self.syntax, self.msg))

  def fail(self) -> NoReturn:
    self.source.fail(*reversed(self.notes), (self.syntax, f'{self.error_prefix} error: {self.msg}'))

  def add_in_note(self, syntax:Syntax, context:Any) -> None:
    '''
    Add a note showing the position of an intermediate rule that is parsing at the moment of failure.
    '''
    # For repeated positions, keep only the innermost note.
    # Outer notes are for choice, quantity, and optional, which are not very informative for debugging parse errors.
    if not self.notes or self.notes[-1][0] != syntax:
      self.notes.append((syntax, f'note: in {context}:'))


class ExcessToken(ParseError):
  'Raised by Parser when expression parsing completes but does not exhaust the token stream.'


def append(list_:list[_T], el:_T) -> list[_T]:
  'Append an element to a list and return the list. Useful when writing transform lambdas.'
  list_.append(el)
  return list_



class Skeletonizable(Protocol):
  '''
  An object that implements `skeletonize` to produce a simplified version of itself.
  This is useful for writing test expectations; we can omit details like token/slice positions,
  but specify the structure of the syntax tree.
  '''
  def skeletonize(self) -> Any: ... # Return a simplified syntactic skeleton of the object.



def syn_skeleton(node:Any, *, source:Source|None=None, keep_lbls:Iterable[str]=frozenset()) -> Any:
  '''
  Produce a simplified skeleton of a syntax tree by recursively removing or simplifying Syn nodes.
  This is particularly useful for building test cases, where the `slc` position information creates visual clutter.

  If `source` is provided, then Tokens are replaced with their source text.
  Otherwise, Tokens are replaced with their kind or mode and kind.

  `keep_lbls` is an iterable of labels for which to preserve Syn nodes.
  All other Syn nodes are replaced with their recursively simplified values.

  This function operates by creating a recursive helper function.

  If a node implements the `skeletonize` method, it should have the following signature:
  `def skeletonize(self, skeletonize_sub:Callable) -> Self: ...`

  `skeletonize` is prefentially used to produce the skeleton; the recursive helper is passed as `skeletonize_sub`.
  '''

  if source is not None:
    def _skeleton_for_token(token:Token) -> Any:
      return source[token]
  else:
    def _skeleton_for_token(token:Token) -> Any:
      if token.mode == 'main': return token.kind
      else: return token.mode_kind

  if keep_lbls:
    if not isinstance(keep_lbls, frozenset): keep_lbls = frozenset(keep_lbls)
    def _skeleton_for_syn(syn:Syn) -> Any:
      return Syn(syn.slc, syn.lbl, _skeleton(syn.val)) if (syn.lbl in keep_lbls) else _skeleton(syn.val)
  else:
    def _skeleton_for_syn(syn:Syn) -> Any:
      return _skeleton(syn.val)

  def _skeleton(node:Any) -> Any:
    try: skeletonize = node.skeletonize
    except AttributeError: pass
    else: return skeletonize(_skeleton)
    match node:
      case Token(): return _skeleton_for_token(node)
      case Syn(): return _skeleton_for_syn(node)
      case list(): return [_skeleton(el) for el in node]
      case tuple():
        if is_namedtuple(node) and node and isinstance(node[0], slice):
          node = node[1:]
        return tuple(_skeleton(el) for el in node)
      case dict(): return {k: _skeleton(v) for k, v in node.items()}
      case _: pass
    if is_dataclass(node):
      dc = node.__class__
      return dc(**{f.name: _skeleton(getattr(node, f.name)) for f in dc_fields(node)})
    return node

  return _skeleton(node)


@dataclass(frozen=True)
class Syn:
  '''
  A Syn instance is a node in a syntax tree.
  It contains a slice `slc` representing the position in the source, a label string `lbl`, and a value `val`.
  This class implements the runtime protocol tolkien.HasSlc.
  '''
  slc:slice
  lbl:str = ''
  val:Any = None

  def __post_init__(self) -> None:
    assert isinstance(self.slc, slice)
    assert isinstance(self.lbl, str)

  def __repr__(self) -> str:
    slc = self.slc
    lbl = self.lbl
    val = self.val
    if lbl: return f'Syn({slc.start}:{slc.stop}, {lbl=!r}, {val=!r})'
    return f'Syn({slc.start}:{slc.stop}, {val=!r})'


AtomTransform = Callable[[Source,Token],Any]

def atom_token(source:Source, token:Token) -> Token:
  'Return the atom token.'
  return token

def atom_kind(source:Source, token:Token) -> str:
  'Return the atom token kind.'
  return token.kind

def atom_text(source:Source, token:Token) -> str:
  'Return the source text for the token.'
  return source[token]

def _atom_transform_placeholder(source:Source, token:Token) -> NoReturn:
  'This transform function is replaced by the parser `atom_transform` or `atom_token`.'
  raise Exception('_atom_transform_placeholder should have been replaced by a real transform')


UniTransform = Callable[[Source,slice,Any],Any] # Used by Opt, Precedence, and SubParser.

def uni_val(source:Source, slc:slice, val:Any) -> Any:
  'Return the value as is.'
  return val

def uni_bool(source:Source, slc:slice, val:Any) -> bool:
  'Return the value as a boolean.'
  return bool(val)

def uni_syn(source:Source, slc:slice, val:Any) -> Syn:
  'Return the value as an unlabeled Syn node.'
  return Syn(slc, '', val)

def uni_text(source:Source, slc:slice, val:Any) -> str:
  'Return the source text for the slice.'
  return source[slc]


UnaryTransform = Callable[[Source,slice,Token,Any],Any]

def unary_val(source:Source, slc:slice, token:Token, val:Any) -> Any:
  'Return the value as is.'
  return val

def unary_syn(source:Source, slc:slice, token:Token, val:Any) -> Syn:
  'Return a Syn node.'
  return Syn(slc, lbl=token.kind, val=val)


def unary_text_val_pair(source:Source, slc:slice, token:Token, val:Any) -> tuple[str,Any]:
  'Return a pair tuple of source text for the token and the value.'
  return (source[token], val)


BinaryTransform = Callable[[Source,slice,Token,Any,Any],Any]

def binary_text_vals_triple(source:Source, slc:slice, token:Token, left:Any, right:Any) -> tuple[str,Any,Any]:
  'Return a triple tuple of source text for the token, the left value, and the right value.'
  return (source[token], left, right)

def binary_vals_pair(source:Source, slc:slice, token:Token, left:Any, right:Any) -> tuple[Any,Any]:
  'Return a pair tuple of the left value and the right value.'
  return (left, right)

def left_binary_to_list(source:Source, slc:slice, token:Token, left:Any, right:Any) -> list[Any]:
  '''
  Return a List of the values parsed by a left-associative list rule.
  If `left` is already a list, append `right` to `left` and return `left`.
  If `left` is not a list, return a list of `left` and `right`.
  '''
  if isinstance(left, list):
    left.append(right)
    return left
  else:
    return [left, right]

def right_binary_to_stack(source:Source, slc:slice, token:Token, left:Any, right:Any) -> Stack[Any]:
  '''
  Return a Stack of the values parsed by a right-associative list rule.
  If `right` is already a Stack, push `left` onto `right` and return `right`.
  Otherwise, return a Stack of `left` and `right`.
  '''
  if isinstance(right, Stack):
    right.push(left)
    return right
  else:
    return Stack((left, right))


QuantityTransform = Callable[[Source,slice,list[Any]],Any]

def quantity_els(source:Source, slc:slice, elements:list[Any]) -> list[Any]:
  'Return the list of parsed elements from a quantity rule.'
  return elements

def quantity_syn(source:Source, slc:slice, elements:list[Any]) -> Syn:
  'Return a Syn node with the parsed elements from a quantity rule.'
  return Syn(slc, '', elements)

def quantity_text(source:Source, slc:slice, elements:list[Any]) -> str:
  'Return the source text for the slice from a quantity rule.'
  return source[slc]


StructTransform = Callable[[Source,slice,list[Any]],Any]

def struct_fields_tuple(source:Source, slc:slice, fields:list[Any]) -> tuple[Any,...]:
  'Return a tuple of the parsed fields from a struct rule.'
  return tuple(fields)

def struct_syn(source:Source, slc:slice, fields:list[Any]) -> Syn:
  'Return a Syn node with the parsed fields from a struct rule.'
  return Syn(slc, '', fields)

def struct_text(source:Source, slc:slice, fields:list[Any]) -> str:
  'Return the source text for the slice from a struct rule.'
  return source[slc]


def _struct_transform_placeholder(source:Source, slc:slice, fields:list[Any]) -> NoReturn:
  'This transform function is replaced by a dynamically generated transform for the struct rule.'
  raise Exception('_struct_transform_placeholder should have been replaced by a real transform')


ChoiceTransform = Callable[[Source,slice,RuleName,Any],Any]

def choice_val(source:Source, slc:slice, label:RuleName, val:Any) -> Any:
  'Return the choseen value without choice metadata.'
  return val

def choice_label(source:Source, slc:slice, label:RuleName, val:Any) -> str:
  'Return the choice label as is.'
  return label


def choice_labeled(source:Source, slc:slice, label:RuleName, val:Any) -> tuple[str,Any]:
  'Return a pair tuple of the choice label and the value.'
  return (label, val)

def choice_syn(source:Source, slc:slice, label:RuleName, val:Any) -> Syn:
  'Return a Syn node with the choice label and value.'
  return Syn(slc, label, val)

def choice_text(source:Source, slc:slice, label:RuleName, val:Any) -> str:
  'Return the source text for the slice from a choice rule.'
  return source[slc]


_sentinel_kind = '!SENTINEL'


@dataclass(frozen=True)
class ParseCtx:
  source:Source
  tokens:list[Token]



class Rule:
  '''
  A parser rule. A complete parser is created from a graph of rules.
  Parser graphs may have cycles, so rules can be constructed with named references to other rules.
  These references are resolved when the parser is compiled.
  '''

  name:str # Optional name, used to link the rule graph.
  field:str|None # Optional field name, used for generated structures.
  #^ A value of '' (the default) causes the rule name or else a default field name to be used.
  #^ An explicit value of None causes the field to be omitted.
  type_desc:str # type description for diagnostic descriptions.
  sub_refs:tuple[RuleRef,...] = () # The rules or references (name strings) that this rule refers to.
  subs:tuple['Rule',...] = () # Sub-rules, obtained by linking sub_refs.
  heads:tuple[TokenKind,...] # Set of leading token kinds for this rule.
  transform:Callable


  def __init__(self, *args:Any, **kwargs:Any): raise Exception(f'abstract base class: {self}')


  def __str__(self) -> str:
    if self.name: return f'{self.name!r} {self.type_desc}'
    else: return repr(self)


  def __repr__(self) -> str:
    parts = []
    if self.name: parts.append(f'name={self.name!r}')
    if self.field: parts.append(f'field={self.field!r}')
    parts.extend((repr(s) for s in self.sub_refs))
    parts.append(f'heads={self.heads!r}')
    parts.append(f'transform={self.transform!r}')
    s = ', '.join(parts)
    return f'{type(self).__name__}({s})'


  def __lt__(self, other:'Rule') -> bool:
    if not isinstance(other, Rule): raise ValueError(other)
    return str(self) < str(other)


  @property
  def subs_desc(self) -> str:
    return f'[{", ".join(str(s) for s in self.subs)}]'


  def token_kinds(self) -> Iterable[str]:
    'The token kinds directly referenced by this rule.'
    return ()


  def head_subs(self) -> Iterable['Rule']:
    'The sub-rules that determine the head of a match for this rule. Used by `compile_heads`.'
    raise NotImplementedError(self)


  def compile_heads(self) -> Iterator[TokenKind]:
    'Calculate the `heads` set for this rule. The parser uses this to build a dispatch table against token kinds.'
    if self.heads: # Prefilled for Atom base case. For recursive rules, the sentinel causes recursion to break here.
      yield from self.heads
      return
    # Otherwise, this rule does not yet know its own heads; discover them recursively.
    self.heads = (_sentinel_kind,) # Temporarily set to prevent recursion loops; use an impossible name.
    for sub in self.head_subs():
      yield from sub.compile_heads()
    # Now reset self.heads; it is up to Parser to call `compile_heads` for each node.
    # Otherwise, we would be relying on possibly incomplete sets that accumulate in intermediates during deep recursion.
    self.heads = ()


  def compile(self, parser:'Parser') -> None: pass


  def parse(self, ctx:ParseCtx, *, parent:'Rule', pos:int) -> tuple[int,slice,Any]:
    '''
    Parse the rule. This is implemented by subclasses.
    Returns:
    * The position of the next token to parse. This is used by the caller to resume parsing.
    * A slice indexing into the source text that was parsed.
    * The result value of the rule.
    '''
    raise NotImplementedError(self)


  def parse_sub(self, ctx:ParseCtx, *, sub:'Rule', pos:int, start_pos:int) -> tuple[int,slice,Any]:
    '''
    Invoke a sub-rule. This wrapper is used in a mutually recursive fashion instead of directly recursing into parse
    so that we can add parse error notes when an error occurs.
    `pos` is the token position for the subrule to parse from.
    `start_pos` is the token position that is the start of the current rule (for error reporting).
    '''
    try:
      return sub.parse(ctx=ctx, parent=self, pos=pos)
    except ParseError as e:
      e.add_in_note(ctx.tokens[start_pos], self)
      raise


  @property
  def field_name(self) -> str: return self.field or self.name



class Alias(Rule):
  '''
  A rule that is an alias for another named rule.
  This can be used as a placeholder during parser development, to add a transform to a rule, or to change the field name.
  '''

  type_desc = 'alias'

  def __init__(self, alias:str, field:str|None='', transform:UniTransform=uni_val):
    self.name = ''
    self.alias = alias
    self.field = field
    self.sub_refs = (alias,)
    self.heads = ()
    self.transform = transform

  def head_subs(self) -> Iterable['Rule']:
    return self.subs

  def parse(self, ctx:ParseCtx, *, parent:'Rule', pos:int) -> tuple[int,slice,Any]:
    pos, slc, res = self.parse_sub(ctx=ctx, sub=self.subs[0], pos=pos, start_pos=pos)
    return pos, slc, self.transform(ctx.source, slc, res)


  @property
  def field_name(self) -> str:
    'Alias overrides `field_name` to pass through the aliased field name if not otherwise specified.'
    return super().field_name or self.subs[0].field_name




class Atom(Rule):
  '''
  A rule that matches a single token.
  '''
  type_desc = 'atom'

  def __init__(self, kind:TokenKind, field:str|None='', transform:AtomTransform|None=None):
    self.name = ''
    self.field = field
    self.heads = (kind,) # Pre-fill heads; compile_heads will return without calling head_subs, which Atom does not implement.
    self.kind = validate_name(kind)
    self.transform = transform or _atom_transform_placeholder


  def token_kinds(self) -> Iterable[str]:
    yield self.kind


  def compile(self, parser:'Parser') -> None:
    if self.transform is _atom_transform_placeholder:
      self.transform = parser.atom_transform or atom_token


  def parse(self, ctx:ParseCtx, parent:'Rule', pos:int) -> tuple[int,slice,Any]:
    token = ctx.tokens[pos]
    if token.kind != self.kind: raise ParseError(ctx.source, token, f'{parent} expects {self.kind}; received {token.kind}.')
    #^ We use `parent` and not `self` to create a meaningful error message.
    #^ Using `self` we would get messages like "'newline' atom expects newline".
    return pos + 1, token.slc, self.transform(ctx.source, token)



class _DropRule(Rule):
  'A rule with a `drop` parameter that can be used to skip tokens.'

  drop:frozenset[str]

  def validate_drop(self) -> None:
    if drop_heads_intersect := self.drop.intersection(self.heads):
      raise Parser.DefinitionError(f'{self} drop kinds and head kinds intersect: {drop_heads_intersect}')



class _QuantityRule(_DropRule):
  'Base class for Opt and Quantity.'
  min:int
  body_heads:frozenset[str]
  drop:frozenset[str]

  @property
  def body(self) -> Rule:
    return self.subs[0]


  def head_subs(self) -> Iterable['Rule']:
    return self.subs


  def compile(self, parser:'Parser') -> None:
    self.body_heads = frozenset(self.body.heads)


class Opt(_QuantityRule):
  '''
  A rule that optionally matches another rule.
  If the subrule matches, then its result is passed into `transform`.
  If not, then `dflt` is passed into the transform.
  '''
  type_desc = 'optional'
  min = 0

  def __init__(self, body:RuleRef, field:str|None='', drop:Iterable[str]=(), dflt:Any=None, transform:UniTransform=uni_val):
    self.name = ''
    self.field = field
    self.sub_refs = (body,)
    self.heads = ()
    self.body_heads = frozenset() # Replaced by compile.
    self.drop = frozenset(iter_str(drop))
    self.dflt = dflt
    self.transform = transform


  def parse(self, ctx:ParseCtx, parent:'Rule', pos:int) -> tuple[int,slice,Any]:
    while ctx.tokens[pos].kind in self.drop: pos += 1
    token = ctx.tokens[pos]
    if token.kind in self.body_heads:
      pos, slc, res = self.parse_sub(ctx, sub=self.body, pos=pos, start_pos=pos)
    else:
      slc = slice(token.pos, token.pos)
      res = self.dflt
    return pos, slc, self.transform(ctx.source, slc, res)


  @property
  def field_name(self) -> str:
    'Opt overrides `field_name` to pass through the subrule field name if not otherwise specified.'
    return super().field_name or self.body.field_name


_max = max

class Quantity(_QuantityRule):
  '''
  A rule that matches some quantity of another rule.
  `sep` is on optional token kind that separates successive elements.
  `sep_at_end` is a three-valued flag:
    * `None` (the default) means that the separator is optional at the end of the sequence.
    * `False` means that the separator is not allowed at the end of the sequence.
    * `True` means that the separator is required at the end of the sequence.
  `repeated_seps` is a boolean flag that controls whether multiple consecutive separators are allowed.
  '''
  type_desc = 'sequence'

  def __init__(self, body:RuleRef, min:int, max:int|None, sep:TokenKind|None=None, sep_at_end:bool|None=None,
   repeated_seps:bool=False, field:str|None='', drop:Iterable[str]=(), transform:QuantityTransform=quantity_els) -> None:
    if min < 0: raise ValueError(min)
    if max is not None and max < 1: raise ValueError(f'Quantity rule must consume at least one element: {max=}')
    if sep is None and sep_at_end is not None: raise ValueError(f'`sep` is `None` but `sep_at_end` is `{sep_at_end}`')
    self.name = ''
    self.field = field
    self.sub_refs = (body,)
    self.heads = ()
    self.sep = sep if sep is None else validate_name(sep)
    self.sep_at_end:bool|None = sep_at_end
    self.repeated_seps = repeated_seps
    self.min = min
    self.max = max
    self.body_heads = frozenset() # Replaced by compile.
    self.drop = _drops = frozenset(iter_str(drop))
    self.transform = transform

    # `consume_seps` returns a tuple of (first_sep_pos, last_sep_end, next_pos).
    if self.sep is None:
      def consume_seps(tokens:list[Token], pos:int) -> tuple[int|None,int,int]:
        'Consume dropped tokens only.'
        while tokens[pos].kind in _drops: pos += 1
        return None, pos, pos

    elif self.repeated_seps:
      def consume_seps(tokens:list[Token], pos:int) -> tuple[int|None,int,int]:
        'Consume any dropped and separator tokens; tracks the position of the first separator only.'
        first_sep_pos = None
        last_sep_end = pos
        while True:
          kind = tokens[pos].kind
          if kind in _drops: pos += 1
          elif kind == self.sep:
            if first_sep_pos is None: first_sep_pos = pos
            pos += 1
            last_sep_end = pos
          else:
            break
        return first_sep_pos, _max(last_sep_end, pos), pos

    else:
      def consume_seps(tokens:list[Token], pos:int) -> tuple[int|None,int,int]:
        'Consume dropped tokens, possibly a single separator, and any subsequent dropped tokens.'
        first_sep_pos = None
        while tokens[pos].kind in _drops: pos += 1
        last_sep_end = pos
        if tokens[pos].kind == self.sep:
          first_sep_pos = pos
          pos += 1
          last_sep_end = pos
        while tokens[pos].kind in _drops: pos += 1
        return first_sep_pos, _max(last_sep_end, pos), pos

    self.consume_seps = consume_seps


  def token_kinds(self) -> Iterable[str]:
    if self.sep is not None:
      yield self.sep
    yield from self.drop


  def parse(self, ctx:ParseCtx, parent:'Rule', pos:int) -> tuple[int,slice,Any]:
    els:list[Any] = []

    while ctx.tokens[pos].kind in self.drop: pos += 1 # Consume leading dropped tokens.

    start_pos = end_pos = pos
    slc_start = slc_stop = ctx.tokens[pos].pos

    first_sep_pos = None
    last_sep_end = pos

    while len(els) != self.max: # Always true when max is None.
      if ctx.tokens[pos].kind not in self.body_heads:
        break
      # Parse the next element.
      pos, el_slc, el = self.parse_sub(ctx, sub=self.body, pos=pos, start_pos=start_pos)
      end_pos = pos
      slc_stop = el_slc.stop
      els.append(el)

      first_sep_pos, last_sep_end, pos = self.consume_seps(ctx.tokens, pos)

    # Handle end conditions.

    if first_sep_pos is None:
      if self.sep_at_end is True:
        raise ParseError(ctx.source, ctx.tokens[pos],
          f'{self} expects final {self.sep} separator; received {ctx.tokens[pos].kind}.')

    elif self.sep_at_end is False:
      # Do not consume any separators. Alternatively, we could raise an error here.
      end_pos = first_sep_pos

    else:
      end_pos = last_sep_end

    if len(els) < self.min:
      body_plural = pluralize(self.min, f'{self.body} element')
      raise ParseError(ctx.source, ctx.tokens[start_pos],
        f'{self} expects at least {body_plural}; received {ctx.tokens[start_pos].kind}.')

    slc = slice(slc_start, slc_stop)
    return end_pos,slc, self.transform(ctx.source, slc, els)



class ZeroOrMore(Quantity):

  def __init__(self, body:RuleRef, sep:TokenKind|None=None, sep_at_end:bool|None=None, repeated_seps:bool=False,
   field:str|None='', drop:Iterable[str]=(), transform:QuantityTransform=quantity_els) -> None:

    super().__init__(body=body, min=0, max=None, sep=sep, sep_at_end=sep_at_end, repeated_seps=repeated_seps,
      field=field, drop=drop, transform=transform)



class OneOrMore(Quantity):

  def __init__(self, body:RuleRef, sep:TokenKind|None=None, sep_at_end:bool|None=None, repeated_seps:bool=False,
   field:str|None='', drop:Iterable[str]=(), transform:QuantityTransform=quantity_els) -> None:

    super().__init__(body=body, min=1, max=None, sep=sep, sep_at_end=sep_at_end, repeated_seps=repeated_seps,
      field=field, drop=drop, transform=transform)



class Struct(_DropRule):
  '''
  A rule that matches a sequence of sub rules, producing a tuple of values.
  '''
  type_desc = 'structure'

  def __init__(self, *fields:RuleRef, drop:Iterable[str]=(), field:str|None='', transform:StructTransform|None=None):
    if not fields: raise ValueError('Struct requires at least one field')
    self.name = ''
    self.field = field
    self.sub_refs = fields
    self.heads = ()
    self.drop = frozenset(iter_str(drop))
    self.transform = transform or _struct_transform_placeholder


  def head_subs(self) -> Iterable['Rule']:
    for field in self.subs:
      yield field
      if not (isinstance(field, _QuantityRule) and field.min == 0):
        break


  def compile(self, parser:'Parser') -> None:
    if self.transform is _struct_transform_placeholder:
      self.transform = parser._mk_struct_transform(name=(self.name or self.field or ''), subs=self.subs)


  def parse(self, ctx:ParseCtx, parent:'Rule', pos:int) -> tuple[int,slice,Any]:
    vals:list[Any] = []
    while ctx.tokens[pos].kind in self.drop: pos += 1
    start_pos = pos
    token = ctx.tokens[pos]
    slc_start = token.pos
    slc_stop = token.pos
    for i, field in enumerate(self.subs):
      if i:
        while ctx.tokens[pos].kind in self.drop: pos += 1
      pos, field_slc, val = self.parse_sub(ctx, sub=field, pos=pos, start_pos=start_pos)
      vals.append(val)
      slc_stop = field_slc.stop
    assert self.transform is not None
    slc = slice(slc_start, slc_stop)
    return pos, slc, self.transform(ctx.source, slc, vals)



class Choice(_DropRule):
  '''
  A rule that matches one of a set of choices, which must have unambiguous heads.
  '''
  type_desc = 'choice'

  def __init__(self, *choices:RuleRef, drop:Iterable[str]=(), field:str|None='', transform:ChoiceTransform|None=None):
    self.name = ''
    self.field = field
    self.sub_refs = choices
    self.heads = ()
    self.drop = frozenset(iter_str(drop))
    if transform is None: raise ValueError(f'Choice constructor requires an explicit transform; choices: {choices}')
    self.transform = transform
    self.head_table:dict[TokenKind,Rule] = {}


  def head_subs(self) -> Iterable[Rule]: return self.subs


  def compile(self, parser:'Parser') -> None:
    for head in self.heads:
      matching_subs = [s for s in self.subs if head in s.heads]
      assert matching_subs
      if len(matching_subs) > 1:
        raise Parser.DefinitionError(f'{self} contains ambiguous choices for head token {head!r}:\n',
          *indent_lines(str(s) for s in matching_subs))
      self.head_table[head] = matching_subs[0]


  def parse(self, ctx:ParseCtx, parent:'Rule', pos:int) -> tuple[int,slice,Any]:
    while ctx.tokens[pos].kind in self.drop: pos += 1
    start_pos = pos
    try: sub = self.head_table[ctx.tokens[pos].kind]
    except KeyError: pass
    else:
      pos,slc, val = self.parse_sub(ctx, sub=sub, pos=pos, start_pos=start_pos)
      return pos,slc, self.transform(ctx.source, slc, sub.field_name, val)
    exp = self.name or f'any of {self.subs_desc}'
    raise ParseError(ctx.source, ctx.tokens[pos], f'{parent} expects {exp}; received {ctx.tokens[pos].kind}.')


class OrderedChoice(_DropRule):
  '''
  A rule that matches one of a set of choices that have identical heads.
  The first choice that matches is returned.
  Note that this rule is not yet optimized: for a PEG parser to perform well generally, it must cache successful sub-parses.
  '''
  type_desc = 'ordered choice'

  def __init__(self, *choices:RuleRef, drop:Iterable[str]=(), field:str|None='', transform:ChoiceTransform|None=None):
    self.name = ''
    self.field = field
    self.sub_refs = choices
    self.heads = ()
    self.drop = frozenset(iter_str(drop))
    if not choices: raise ValueError('OrderedChoice requires at least one choice')
    if transform is None: raise ValueError(f'OrderedChoice constructor requires an explicit transform; choices: {choices}')
    self.transform = transform
    self.head_table:dict[TokenKind,Rule] = {}


  def head_subs(self) -> Iterable[Rule]: return self.subs


  def compile(self, parser:'Parser') -> None:
    pass


  def parse(self, ctx:ParseCtx, parent:Rule, pos:int) -> tuple[int,slice,Any]:

    while ctx.tokens[pos].kind in self.drop: pos += 1
    token = ctx.tokens[pos]
    furthest_parse_error:ParseError|None = None

    for sub in self.subs:
      if token.kind not in sub.heads: continue
      try:
        # Note: `pos` does not advance; we try each sub-rule from the same position.
        end_pos, slc, val = self.parse_sub(ctx, sub=sub, pos=pos, start_pos=pos)
      except ParseError as e:
        if furthest_parse_error is None or get_syntax_slc(e.syntax).start > get_syntax_slc(furthest_parse_error.syntax).start:
          furthest_parse_error = e
        continue
      else:
        return end_pos, slc, self.transform(ctx.source, slc, sub.field_name, val)

    # All choices failed.
    if furthest_parse_error is None:
      exp = self.name or f'any of {self.subs_desc}'
      raise ParseError(ctx.source, token, f'{parent} expects {exp}; received {ctx.tokens[pos].kind}.')
    else:
      raise furthest_parse_error


class Operator:
  'An operator that composes a part of a Precedence rule.'
  level:int = -1 # The precedence level of the operator's group, multiplied by ten.
  sub_level:int = -1 # The `level`, with the group `level_bump` added.
  sub_refs:tuple[RuleRef,...] = ()

  # TODO: spacing requirement options, e.g. no space, some space, symmetrical space.


  @property
  def kinds(self) -> tuple[TokenKind,...]:
    return ()


  def __init__(self, *args:Any, **kwargs:Any):
    raise Exception(f'abstract base class: {self}')


  def parse_right(self, ctx:ParseCtx, parent:Rule, pos:int, left_start:int, left:Any, parse_level:Callable, level:int
   ) -> tuple[int,int,Any]:
    'Returns (pos, slc_stop, right_val).'
    raise NotImplementedError(self)



class Suffix(Operator):
  'A suffix/postfix operator: the suffix follows the primary expression. E.g. `*` in `A*`.'

  def __init__(self, suffix:TokenKind, transform:UnaryTransform=unary_text_val_pair): # TODO: transform should take slc and token?
    self.suffix = validate_name(suffix)
    self.transform = transform


  @property
  def kinds(self) -> tuple[TokenKind,...]:
    return (self.suffix,)


  def parse_right(self, ctx:ParseCtx, parent:Rule, pos:int, left_start:int, left:Any, parse_level:Callable, level:int
   ) -> tuple[int,int,Any]:
    suffix_token = ctx.tokens[pos]
    slc = slice(left_start, suffix_token.slc.stop)
    return pos+1, suffix_token.slc.stop, self.transform(ctx.source, slc, suffix_token, left) # No right-hand side.



class SuffixRule(Operator):
  '''
  A suffix/postfix rule: like the Suffix operator, except the suffix is an arbitrary rule.
  Note: due to current limitations in the linker implementation,
  `suffix` must be a constructed rule and not a string reference.
  '''

  def __init__(self, suffix:Rule, transform:BinaryTransform=binary_vals_pair): # TODO: transform should take slc.
    if isinstance(suffix, str): raise TypeError('SuffixRule requires a constructed rule, not a string reference.') # type: ignore[unreachable]
    self.sub_refs = (suffix,)
    self.transform = transform


  @property
  def suffix(self) -> Rule: return cast(Rule, self.sub_refs[0]) # TODO: link over operators, and refer to self.subs instead.


  @property
  def kinds(self) -> tuple[TokenKind,...]:
    return tuple(self.suffix.heads)


  def parse_right(self, ctx:ParseCtx, parent:Rule, pos:int, left_start:int, left:Any, parse_level:Callable, level:int
   ) -> tuple[int,int,Any]:
    start_pos = pos
    pos, right_slc, right = parent.parse_sub(ctx, sub=self.suffix, pos=pos, start_pos=start_pos) # TODO: start_pos is wrong.
    slc = slice(left_start, right_slc.stop)
    return pos, slc.stop, self.transform(ctx.source, slc, ctx.tokens[start_pos].pos_token(), left, right)



class BinaryOp(Operator):
  'Abstract base class for binary operators that take left and right primary expressions.'



class Adjacency(BinaryOp):
  'A binary operator that joins two primary expressions with no operator token in between.'

  def __init__(self, transform:BinaryTransform=binary_vals_pair): # TODO transform should take slc.
    self.transform = transform


  @property
  def kinds(self) -> tuple[TokenKind,...]:
    raise _AllLeafKinds


  def parse_right(self, ctx:ParseCtx, parent:Rule, pos:int, left_start:int, left:Any, parse_level:Callable, level:int
   ) -> tuple[int,int,Any]:
    start_pos = pos
    pos, right_slc, right = parse_level(ctx=ctx, parent=parent, pos=pos, level=level)
    slc = slice(left_start, right_slc.stop)
    return pos, slc.stop, self.transform(ctx.source, slc, ctx.tokens[start_pos].pos_token(), left, right)



class _AllLeafKinds(Exception):
  'Raised by Adjacency.kinds to signal that the precedence parser associates the set of leaf token kinds with this adjacency op.'



class Infix(BinaryOp):
  'A binary operator that joins two primary expressions with an infix operator.'

  def __init__(self, kind:TokenKind, transform:BinaryTransform=binary_text_vals_triple):
    self.kind = validate_name(kind)
    self.transform = transform


  @property
  def kinds(self) -> tuple[TokenKind,...]:
    return (self.kind,)


  def parse_right(self, ctx:ParseCtx, parent:Rule, pos:int, left_start:int, left:Any, parse_level:Callable, level:int
   ) -> tuple[int,int,Any]:
    infix_pos = pos
    pos, right_slc, right = parse_level(ctx=ctx, parent=parent, pos=pos+1, level=level)
    slc = slice(left_start, right_slc.stop)
    return pos, slc.stop, self.transform(ctx.source, slc, ctx.tokens[infix_pos], left, right)



class Group:
  level_bump = 0
  'Operator precedence group.'

  def __init__(self, *ops:Operator):
    self.ops = ops
    self.level = -1


  @property
  def sub_refs(self) -> Iterator[RuleRef]:
    for op in self.ops:
      yield from op.sub_refs



class Left(Group):
  'Left-associative operator precedence group.'
  level_bump = 1



class Right(Group):
  'Right-associative operator precedence group.'



class Precedence(_DropRule):
  'An operator precedence rule, consisting of groups of operators.'
  type_desc = 'precedence rule'

  def __init__(self, leaves:RuleRef|Iterable[RuleRef], *groups:Group,
   field:str|None='', drop:Iterable[str]=(), transform:UniTransform=uni_val) -> None:

    # Keep track of the distinction between subs that came from leaves vs groups.
    # We catenate them all together to sub_refs, so they all get correctly linked,
    # but remember the number of leaves so that `head_subs` can return just the linked leaves.

    if isinstance(leaves, (str,Rule)): leaves = (leaves,)
    self.leaf_refs = tuple(leaves)
    self.group_refs = tuple(ref for g in groups for ref in g.sub_refs)
    self.name = ''
    self.field = field
    self.sub_refs = self.leaf_refs + self.group_refs
    self.heads = ()
    self.drop = frozenset(iter_str(drop))
    self.transform = transform
    self.groups = groups
    self.head_table:dict[TokenKind,Rule] = {}
    self.tail_table:dict[TokenKind,Operator] = {}


  def token_kinds(self) -> Iterable[str]:
    for group in self.groups:
      for op in group.ops:
        try: yield from op.kinds
        except _AllLeafKinds: pass # Adjacency ops do not directly reference any token.


  def head_subs(self) -> Iterable[Rule]:
    return self.subs[:len(self.leaf_refs)] # Only the leaves can be heads.


  def compile(self, parser:'Parser') -> None:
    for head in self.heads:
      matching_subs = [s for s in self.head_subs() if head in s.heads]
      assert matching_subs
      if len(matching_subs) > 1:
        raise Parser.DefinitionError(f'{self} contains ambiguous primaries for head token {head!r}:\n',
          *indent_lines(str(s) for s in matching_subs))
      self.head_table[head] = matching_subs[0]

    for i, group in enumerate(self.groups):
      group.level = i*10 # Multiplying by ten lets level_bump increase the level by one to achieve left-associativity.
      for op in group.ops:
        op.level = group.level
        op.sub_level = group.level + group.level_bump
        try: kinds = op.kinds
        except _AllLeafKinds: kinds = tuple(self.head_table)
        for kind in kinds:
          try: existing = self.tail_table[kind]
          except KeyError: pass
          else: raise Parser.DefinitionError(f'{self} contains ambiguous operators for token {kind!r}:\n', existing, op)
          self.tail_table[kind] = op


  def parse(self, ctx:ParseCtx, parent:'Rule', pos:int) -> tuple[int,slice,Any]:
    pos, slc, val = self.parse_level(ctx, parent, pos, 0)
    return pos, slc, self.transform(ctx.source, slc, val)


  def parse_level(self, ctx:ParseCtx, parent:Rule, pos:int, level:int) -> tuple[int,slice,Any]:

    while ctx.tokens[pos].kind in self.drop: pos += 1

    token = ctx.tokens[pos]
    sub = self.head_table.get(token.kind)
    if sub is None:
      exp = self.name or f'any of {self.subs_desc}'
      raise ParseError(ctx.source, token, f'{parent} expects {exp}; received {token.kind}.')

    pos, left_slc, left = self.parse_sub(ctx, sub=sub, pos=pos, start_pos=pos)
    #^ `left` is the left-hand side value.

    slc_stop = left_slc.stop
    while True:
      while ctx.tokens[pos].kind in self.drop: pos += 1
      op_token = ctx.tokens[pos]
      try:
        op = self.tail_table[op_token.kind]
      except KeyError:
        break # op_token is not an operator.
      if op.level < level: break # This operator is at a lower precedence.
      pos, slc_stop, left = op.parse_right(ctx, parent, pos, left_slc.start, left, self.parse_level, level=op.sub_level)
    # Current token is either not an operator or of a lower precedence level.
    return pos, slice(left_slc.start, slc_stop), left



class SubParser(Rule):

  def __init__(self, parser:'Parser', rule_name:str, field:str|None='', transform:UniTransform=uni_val):
    self.name = ''
    self.field = field
    self.sub_refs = ()
    self.heads = parser.rules[rule_name].heads
    self.parser = parser
    self.rule = parser.rules[rule_name]
    self.transform = transform


  def parse(self, ctx:ParseCtx, parent:'Rule', pos:int) -> tuple[int,slice,Any]:
    pos, slc, sub_res = self.rule.parse(ctx=ctx, parent=self, pos=pos)
    return pos, slc, self.transform(ctx.source, slc, sub_res)



Preprocessor = Callable[[Source, Iterable[Token]], Iterable[Token]]


class Parser:

  class DefinitionError(Exception):
    def __init__(self, *msgs:Any):
      super().__init__(''.join(str(msg) for msg in msgs))


  def __init__(self, lexer:Lexer, *, preprocessor:Preprocessor|None=None, drop:Iterable[TokenKind]=(),
   literals:Iterable[TokenKind]=(), rules:dict[RuleName,Rule], atom_transform:AtomTransform|None=None,
   transforms:dict[RuleName,Callable]|None=None):

    '''
    lexer: the lexer to use.
    preprocessor: a function that can modify the input token stream.

    drop: a set of token kinds to be dropped from the input token stream.

    literals: a set of token kinds that are fixed strings and should not be included in output structures.
    For example we might parse "(1 2 3)" with a rule like `Struct('paren_o', ZeroOrMore('expr'), 'paren_c')`.
    There is no utility in including the parenthesis tokens in the returned structure, because their string content is known.

    rules: a dict of rule names to rules.
    This dictionary is deep copied so that different parsers can attach different transforms to the same rule set.

    atom_transform: if provided, this transform is the default transformer for atom rules.

    transforms: a dict of rule names to transforms. These override the transforms specified in the rules.
    '''

    self.lexer = lexer
    self.preprocessor = preprocessor
    self.drop = frozenset(iter_str(drop))
    self.literals = frozenset(iter_str(literals))

    self.rules = deepcopy(rules)
    del rules # Forget the original dict. This protects from misuse in the code below.

    self.module_name = caller_module_name(1) # Get the calling module name to use for synthesized NamedTuple types.
    self._struct_types:dict[str,type[GeneratedStruct]] = {}

    self.atom_transform = atom_transform

    if transforms is None: transforms = {}
    for name, transform in transforms.items():
      try: rule = self.rules[name]
      except KeyError: raise Parser.DefinitionError(f'nonexistent rule: {name!r}')
      rule.transform = transform

    for name, rule in self.rules.items():
      validate_name(name)
      assert rule.name == '', rule.name # Names are never set during construction, only during parser initialization.
      rule.name = name

    # Link rule graph. Note: this creates reference cycles which are dissolved by __del__.

    def link_sub_ref(rule:RuleRef) -> Rule:
      if isinstance(rule, Rule): return rule
      if not isinstance(rule, str): raise Parser.DefinitionError(f'subrule must be a Rule or string reference: {rule!r}')
      try: return self.rules[rule]
      except KeyError: pass
      if rule in self.lexer.kinds: # Add the implied Atom rule.
        atom = Atom(rule)
        assert atom.name == ''
        atom.name = rule
        self.rules[rule] = atom
        return atom
      raise Parser.DefinitionError(f'nonexistent rule: {rule!r}')

    def link(rule:Rule) -> Iterable[Rule]:
      assert not rule.subs
      if rule.sub_refs:
        rule.subs = tuple(link_sub_ref(s) for s in rule.sub_refs)
      assert len(rule.subs) == len(rule.sub_refs)
      return rule.subs

    self.nodes = visit_nodes(self.rules.values(), link) # All of the rule nodes.

    for rule in self.nodes:
      # Validate token references.
      for token_kind in rule.token_kinds():
        if token_kind not in lexer.kinds:
          raise Parser.DefinitionError(f'{rule} refers to nonexistent token kind: {token_kind}')
      # Fill out rule heads.
      if not rule.heads:
        heads = set(rule.compile_heads())
        try: heads.remove(_sentinel_kind)
        except KeyError: pass
        rule.heads = tuple(sorted(heads))
        assert rule.heads

    # Compile.
    for rule in self.nodes:
      rule.compile(parser=self)
      if isinstance(rule, _DropRule): rule.validate_drop()

    self.types:Immutable[type] = Immutable(self._struct_types)


  def __del__(self) -> None:
    for rule in self.rules.values():
      rule.__dict__.clear() # Break all references between rules.


  def _mk_struct_transform(self, name:str, subs:tuple[Rule,...]) -> StructTransform:

    includes = [((sub.field is not None) and (bool(sub.field) or (sub.name not in self.literals))) for sub in subs]
    #^ Bool for each sub position.
    #^ If field is None, that is an explicit request to exclude the field.
    #^ If field is provided, always include the field.
    #^ Otherwise, include the field only if it is not a literal.

    if includes.count(True) == 1: # No need for a struct; just extract the interesting child element.
      i = includes.index(True)
      def single_transform(source:Source, slc:slice, fields:list[Any]) -> Any: return fields[i]
      return single_transform

    raw_field_names = [sub.field_name for sub, should_inlude in zip(subs, includes) if should_inlude]
    field_names = ('slc',) + tuple(self._mk_clean_field_name(n, i) for i, n in enumerate(raw_field_names))

    struct_type = self._mk_struct_type(name, field_names=field_names)

    def transform(source:Source, slc:slice, fields:list[Any]) -> Any:
      return struct_type(slc, *(f for f, should_include in zip(fields, includes) if should_include))

    return transform


  def _mk_clean_field_name(self, name:str, idx:int) -> str:
    if not name: return f'f{idx}'
    if iskeyword(name) or issoftkeyword(name) or name == 'token': return name + '_'
    if name[0].isdigit() or name[0] == '_': return 'f' + name
    return name


  def _mk_struct_type(self, name:str, field_names:tuple[str,...]) -> type[GeneratedStruct]:
    if name:
      type_name = typecase_from_snakecase(name)
    elif field_names:
      type_name = '_'.join(typecase_from_snakecase(n) for n in field_names)
    else:
      type_name = 'Empty'

    try: existing = self._struct_types[type_name]
    except KeyError: pass
    else:
      if existing._fields != field_names:
        raise Parser.DefinitionError(
          f'conflicting fields for synthesized struct type {name}:\n  {existing._fields}\n  {field_names}')
      return existing

    struct_type = cast(type[GeneratedStruct], namedtuple(type_name, field_names, rename=True, module=(self.module_name or '?')))
    self._struct_types[type_name] = struct_type
    return struct_type


  def lex_and_preprocess(self, source:Source, dbg_tokens:bool) -> list[Token]:
    stream:Iterable[Token] = self.lexer.lex(source, drop=self.drop, eot=True)
    if self.preprocessor: stream = self.preprocessor(source, stream)
    tokens = list(stream)
    if dbg_tokens:
      for i, t in enumerate(tokens):
        errL(f'Parser tokens[{i}]: {t}: {source[t]!r}')
    return tokens


  def parse(self, rule_name:RuleName, source:Source, ignore_excess:bool=False, skeletonize:bool=False, dbg_tokens:bool=False
   ) -> Any:
    rule = self.rules[rule_name]
    tokens = self.lex_and_preprocess(source, dbg_tokens)
    ctx = ParseCtx(source=source, tokens=tokens)
    pos, _slc, result = rule.parse(ctx=ctx, parent=rule, pos=0) # Top rule is passed as its own parent.
    excess_token = ctx.tokens[pos] # Must exist because end_of_text cannot be consumed by a legal parser.
    if not ignore_excess and excess_token.kind != 'end_of_text':
      raise ExcessToken(source, excess_token, f'excess token: {excess_token.mode_kind}.')
    if skeletonize:
      result = syn_skeleton(result, source=source)
    return result


  def parse_or_fail(self, rule_name:RuleName, source:Source, ignore_excess:bool=False, skeletonize:bool=False,
   dbg_tokens:bool=False) -> Any:
    try:
      return self.parse(rule_name=rule_name, source=source, ignore_excess=ignore_excess, skeletonize=skeletonize,
        dbg_tokens=dbg_tokens)
    except ParseError as e: e.fail()


  def parse_all(self, rule_name:RuleName, source:Source, skeletonize:bool=False, dbg_tokens:bool=False) -> Iterator[Any]:
    rule = self.rules[rule_name]
    tokens = self.lex_and_preprocess(source, dbg_tokens)
    ctx = ParseCtx(source=source, tokens=tokens)
    pos = 0
    while True:
      if ctx.tokens[pos].kind == 'end_of_text': return
      pos, slc, result = rule.parse(ctx=ctx, parent=rule, pos=pos)
      #^ Top rule is passed as its own parent.
      pos = slc.stop
      if skeletonize:
        result = syn_skeleton(result, source=source)
      yield result



def validate_name(name:Any) -> str:
  if not isinstance(name, str):
    raise Parser.DefinitionError(f'name is not a string: {name!r}')
  if not valid_name_re.fullmatch(name):
    raise Parser.DefinitionError(f'invalid name: {name!r}')
  if name in reserved_names:
    raise Parser.DefinitionError(f'name is reserved: {name!r}')
  return name
