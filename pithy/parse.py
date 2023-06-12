# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
A simple parser library based on recursive descent and operator precedence parsing.
Recursive decent is performed by looking at the next token,
and then dispatching through a table of token kinds to select the appropriate Rule.

Upon parsing, each type of rule produces a generic result, which is then passed to a user-provided transformer function.
Different rule types have different result and transformer function types to match the shape of the parsed structure.
Transformers can return results of any type.

Several types of rules are available:
* Atom: a single token kind.
* Quantity: a body rule, optionally interleaved with a separator token, with optional `min` and `max` quantities.
* Choice: one of several rules, which must be distinguishable by the head token.
* Struct: a fixed-length sequence of heterogenous subrules.
* Precedence: a family of binary precedence operators.

The main design feature of Parser is that operators are not first-class rules:
they are parsed within the context of a Precedence rule.
This allows us to use the operator-precedence parsing algorithm,
while expressing other aspects of a grammar using straightforward recursive descent.
'''

from collections import namedtuple
from copy import deepcopy
from dataclasses import dataclass
from keyword import iskeyword, issoftkeyword
from typing import (Any, Callable, cast, Dict, FrozenSet, Iterable, Iterator, List, NoReturn, Optional, Tuple, Type, TypeVar,
  Union)

from tolkien import Source, Syntax, SyntaxMsg, Token

from .buffer import Buffer
from .graph import visit_nodes
from .io import tee_to_err
from .lex import Lexer, reserved_names, valid_name_re
from .meta import caller_module_name
from .string import indent_lines, iter_str, pluralize, typecase_from_snakecase
from .untyped import Immutable


TokenKind = str
RuleName = str
RuleRef = Union['Rule',RuleName]
_T = TypeVar('_T')


class ParseError(Exception):
  error_prefix = 'parse'

  def __init__(self, source:Source, syntax:Syntax, msg:str, notes:Iterable[SyntaxMsg]=()):
    self.source = source
    self.notes:List[SyntaxMsg] = list(notes)
    self.syntax = syntax
    self.msg = msg
    super().__init__((self.syntax, self.msg))

  def fail(self) -> NoReturn:
    self.source.fail(*reversed(self.notes), (self.syntax, f'{self.error_prefix} error: {self.msg}'))

  def add_in_note(self, syntax:Syntax, context:Any) -> None:
    # For repeated positions, keep only the innermost note.
    # Outer notes are for choice, quantity, and optional, which are not very informative for debugging parse errors.
    if not self.notes or self.notes[-1][0] != syntax:
      self.notes.append((syntax, f'note: in {context}:'))


class ExcessToken(ParseError):
  'Raised by Parser when expression parsing completes but does not exhaust the token stream.'


def append(list_:List[_T], el:_T) -> List[_T]:
  'Append an element to a list and return the list. Useful when writing transform lambdas.'
  list_.append(el)
  return list_


def append_or_list(list_or_el:Union[_T,List[_T]], el:_T) -> List[_T]:
  'Create a list from two elements, or if the left element is already a list, append the right element to it and return it.'
  if isinstance(list_or_el, list):
    list_or_el.append(el)
    return list_or_el
  else:
    return [list_or_el, el]


@dataclass(frozen=True)
class Syn:
  slc:slice
  val:Any


AtomTransform = Callable[[Source,Token],Any]

def atom_token(source:Source, token:Token) -> Token: return token
def atom_kind(source:Source, token:Token) -> str: return token.kind
def atom_text(source:Source, token:Token) -> str: return source[token]

UniTransform = Callable[[Source,slice,Any],Any]
def uni_val(source:Source, slc:slice, val:Any) -> Any: return val
def uni_syn(source:Source, slc:slice, val:Any) -> Syn: return Syn(slc, val)
def uni_text(source:Source, slc:slice, val:Any) -> str: return source[slc]

SuffixTransform = Callable[[Source,Token,Any],Any]
def suffix_val(source:Source, token:Token, val:Any) -> Any: return val
def suffix_text_val_pair(source:Source, token:Token, val:Any) -> Tuple[str,Any]: return (source[token], val)

def suffix_text(source:Source, token:Token, val:Any) -> str:
  assert isinstance(val, str)
  return val + source[token]

BinaryTransform = Callable[[Source,Token,Any,Any],Any]
def binary_text_vals_triple(source:Source, token:Token, left:Any, right:Any) -> Tuple[str,Any,Any]: return (source[token], left, right)
def binary_vals_pair(source:Source, token:Token, left:Any, right:Any) -> Tuple[Any,Any]: return (left, right)
def binary_to_list(source:Source, token:Token, left:Any, right:Any) -> List[Any]: return append_or_list(left, right)

QuantityTransform = Callable[[Source,slice,List[Any]],Any]
def quantity_els(source:Source, slc:slice, elements:List[Any]) -> List[Any]: return elements
def quantity_syn(source:Source, slc:slice, elements:List[Any]) -> Syn: return Syn(slc, elements)
def quantity_text(source:Source, slc:slice, elements:List[Any]) -> str: return source[slc]

StructTransform = Callable[[Source,slice,List[Any]],Any]
def struct_fields_tuple(source:Source, slc:slice, fields:list[Any]) -> Tuple[Any,...]: return tuple(fields)
def struct_syn(source, slc:slice, fields:list[Any]): return Syn(slc, fields)

def _struct_default_transform_placeholder(source, slc:slice, fields:list[Any]):
  raise Exception('_struct_placeholder should have been replaced by a real transform')

ChoiceTransform = Callable[[Source,slice,RuleName,Any],Any]
def choice_val(source:Source, slc:slice, label:RuleName, val:Any) -> Any: return val
def choice_label(source:Source, slc:slice, label:RuleName, val:Any) -> str: return label
def choice_labeled(source:Source, slc:slice, label:RuleName, val:Any) -> tuple[str,Any]: return (label, val)
def choice_syn(source:Source, slc:slice, label:RuleName, val:Any) -> Syn: return Syn(slc, val)
def choice_text(source:Source, slc:slice, label:RuleName, val:Any) -> str: return source[slc]

_sentinel_kind = '!SENTINEL'



class Rule:
  'A parser rule. A complete parser is created from a graph of rules.'

  name:str # Optional name, used to link the rule graph.
  field:str|None # Optional field name, used for generated structures.
  #^ A value of '' (the default) causes the rule name or else a default field name to be used.
  #^ An explicit value of None causes the field to be omitted.
  type_desc:str # Type description for diagnostic descriptions.
  sub_refs:Tuple[RuleRef,...] = () # The rules or references (name strings) that this rule refers to.
  subs:Tuple['Rule',...] = () # Sub-rules, obtained by linking sub_refs.
  heads:Tuple[TokenKind,...] # Set of leading token kinds for this rule.
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


  def expect(self, source:Source, token:Token, kind:str) -> Token:
    if token.kind != kind: raise ParseError(source, token, f'{self} expects {kind}; received {token.kind}.')
    return token


  def parse(self, parent:'Rule', source:Source, token:Token, buffer:Buffer[Token]) -> tuple[slice,Any]:
    raise NotImplementedError(self)


  def parse_sub(self, sub:'Rule', source:Source, start:Token, token:Token, buffer:Buffer[Token]) -> tuple[slice,Any]:
    try:
      return sub.parse(self, source, token, buffer)
    except ParseError as e:
      e.add_in_note(start, self)
      raise


  @property
  def field_name(self) -> str: return self.field or self.name



class Alias(Rule):
  '''
  A rule that is an alias for another named rule.
  This can be used as a placeholder during parser development, to add a transform to a rule, or to change the field name.
  '''

  type_desc = 'alias'

  def __init__(self, alias:str, field='', transform:UniTransform=uni_val):
    self.name = ''
    self.field = field
    self.alias = alias
    self.sub_refs = (alias,)
    self.heads = ()
    self.transform = transform

  def head_subs(self) -> Iterable['Rule']:
    return self.subs

  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> tuple[slice,Any]:
    slc, res = self.parse_sub(self.subs[0], source, token, token, buffer)
    return slc, self.transform(source, slc, res)



class Atom(Rule):
  '''
  A rule that matches a single token.
  '''
  type_desc = 'atom'

  def __init__(self, kind:TokenKind, field='', transform:AtomTransform=atom_token):
    self.name = ''
    self.field = field
    self.heads = (kind,) # Pre-fill heads; compile_heads will return without calling head_subs, which Atom does not implement.
    self.kind = validate_name(kind)
    self.transform = transform


  def token_kinds(self) -> Iterable[str]:
    yield self.kind


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> tuple[slice,Any]:
    parent.expect(source, token=token, kind=self.kind)
    #^ We use `parent` and not `self` to expect the token for a more contextualized error message.
    #^ Using `self` we would get messages like "'newline' atom expects newline".
    return token.slc, self.transform(source, token)



class _QuantityRule(Rule):
  'Base class for Opt and Quantity.'
  min:int
  body_heads:FrozenSet[str]
  drop:FrozenSet[str]

  @property
  def body(self) -> Rule:
    return self.subs[0]


  def head_subs(self) -> Iterable['Rule']:
    return self.subs


  def compile(self, parser:'Parser') -> None:
    self.body_heads = frozenset(self.body.heads)
    drop_body_intersect = self.body_heads & self.drop
    if drop_body_intersect:
      raise Parser.DefinitionError(f'{self} drop kinds and body head kinds intersect: {drop_body_intersect}')



class Opt(_QuantityRule):
  '''
  A rule that optionally matches another rule.
  If the subrule matches, then its result is passed into `transform`.
  If not, then `dflt` is passed into the transform.
  '''
  type_desc = 'optional'
  min = 0

  def __init__(self, body:RuleRef, field='', drop:Iterable[str]=(), dflt=None, transform:UniTransform=uni_val):
    self.name = ''
    self.field = field
    self.sub_refs = (body,)
    self.heads = ()
    self.body_heads = frozenset() # Replaced by compile.
    self.drop = frozenset(iter_str(drop))
    self.dflt = dflt
    self.transform = transform


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> tuple[slice,Any]:
    while token.kind in self.drop:
      token = next(buffer)
    if token.kind in self.body_heads:
      slc, res = self.parse_sub(self.body, source, token, token, buffer)
    else:
      pos = token.pos
      slc = slice(pos, pos)
      res = self.dflt
      buffer.push(token)
    return slc, self.transform(source, slc, res)


  @property
  def field_name(self) -> str:
    'Override to default to passing through the subrule field name.'
    return super().field_name or self.body.field_name



class Quantity(_QuantityRule):
  '''
  A rule that matches some quantity of another rule.
  '''
  type_desc = 'sequence'

  def __init__(self, body:RuleRef, min:int, max:int|None, sep:TokenKind|None=None, sep_at_end:bool|None=None, repeated_seps=False,
   field='', drop:Iterable[str]=(), transform:QuantityTransform=quantity_els) -> None:
    if min < 0: raise ValueError(min)
    if max is not None and max < 1: raise ValueError(max) # The rule must consume at least one token; see `parse` implementation.
    if sep is None and sep_at_end is not None: raise ValueError(f'`sep` is `None` but `sep_at_end` is `{sep_at_end}`')
    self.name = ''
    self.field = field
    self.sub_refs = (body,)
    self.heads = ()
    self.sep = sep if sep is None else validate_name(sep)
    self.sep_at_end:Optional[bool] = sep_at_end
    self.repeated_seps = repeated_seps
    self.min = min
    self.max = max
    self.body_heads = frozenset() # Replaced by compile.
    self.drop = frozenset(iter_str(drop))
    self.transform = transform


  def token_kinds(self) -> Iterable[str]:
    if self.sep is not None:
      yield self.sep
    yield from self.drop


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> tuple[slice,Any]:
    els:List[Any] = []
    sep_token:Token|None = None
    start = token
    end = start.pos
    while True:
      while token.kind in self.drop:
        token = next(buffer)
      if len(els) == self.max or token.kind not in self.body_heads: break
      el_slc, el = self.parse_sub(self.body, source, start, token, buffer)
      end = el_slc.stop
      els.append(el)
      token = next(buffer)
      if self.sep is not None: # Parse separator.
        sep_token = token if (token.kind == self.sep) else None
        if sep_token:
          token = next(buffer)
        elif self.sep_at_end:
          raise ParseError(source, token, f'{self} expects {self.sep} separator; received {token.kind}.')
        else:
          break
        if self.repeated_seps:
          while token.kind == self.sep:
            token = next(buffer)

    if len(els) < self.min:
      body_plural = pluralize(self.min, f'{self.body} element')
      raise ParseError(source, token, f'{self} expects at least {body_plural}; received {token.kind}.')

    buffer.push(token)
    if self.sep_at_end is False and sep_token: buffer.push(sep_token)
    slc = slice(start.pos, end)
    return slc, self.transform(source, slc, els)



class ZeroOrMore(Quantity):

  def __init__(self, body:RuleRef, sep:TokenKind|None=None, sep_at_end:bool|None=None, repeated_seps=False,
   field='', drop:Iterable[str]=(), transform:QuantityTransform=quantity_els) -> None:

    super().__init__(body=body, min=0, max=None, sep=sep, sep_at_end=sep_at_end, repeated_seps=repeated_seps,
      field=field, drop=drop, transform=transform)



class OneOrMore(Quantity):

  def __init__(self, body:RuleRef, sep:TokenKind|None=None, sep_at_end:bool|None=None, repeated_seps=False,
   field='', drop:Iterable[str]=(), transform:QuantityTransform=quantity_els) -> None:

    super().__init__(body=body, min=1, max=None, sep=sep, sep_at_end=sep_at_end, repeated_seps=repeated_seps,
      field=field, drop=drop, transform=transform)



class Struct(Rule):
  '''
  A rule that matches a sequence of sub rules, producing a tuple of values.
  '''
  type_desc = 'structure'

  def __init__(self, *fields:RuleRef, drop:Iterable[str]=(), field='', transform:StructTransform|None=None):
    if not fields: raise ValueError('Struct requires at least one field')
    self.name = ''
    self.field = field
    self.sub_refs = fields
    self.heads = ()
    self.drop = frozenset(iter_str(drop))
    self.transform = transform or _struct_default_transform_placeholder


  def head_subs(self) -> Iterable['Rule']:
    for field in self.subs:
      yield field
      if not (isinstance(field, _QuantityRule) and field.min == 0):
        break


  def compile(self, parser:'Parser') -> None:
    if self.transform is _struct_default_transform_placeholder:
      self.transform = parser._mk_struct_transform(name=self.name, subs=self.subs)


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> tuple[slice,Any]:
    vals:List[Any] = []
    while token.kind in self.drop:
      token = next(buffer)
    start = token
    end = start.pos
    for i, field in enumerate(self.subs):
      if i:
        token = next(buffer)
        while token.kind in self.drop:
          token = next(buffer)
      field_slc, val = self.parse_sub(field, source, start, token, buffer)
      vals.append(val)
      end = field_slc.stop
    assert self.transform is not None
    slc = slice(start.pos, end)
    return slc, self.transform(source, slc, vals)



class Choice(Rule):
  '''
  A rule that matches one of a set of choices, which must have unambiguous heads.
  '''
  type_desc = 'choice'

  def __init__(self, *choices:RuleRef, drop:Iterable[str]=(), field='', transform:ChoiceTransform|None=None):
    self.name = ''
    self.field = field
    self.sub_refs = choices
    self.heads = ()
    self.drop = frozenset(iter_str(drop))
    if transform is None: raise ValueError('Choice requires an explicit transform')
    self.transform = transform
    self.head_table:Dict[TokenKind,Rule] = {}


  def head_subs(self) -> Iterable[Rule]: return self.subs


  def compile(self, parser:'Parser') -> None:
    for head in self.heads:
      matching_subs = [s for s in self.subs if head in s.heads]
      assert matching_subs
      if len(matching_subs) > 1:
        raise Parser.DefinitionError(f'{self} contains ambiguous choices for head token {head!r}:\n',
          *indent_lines(str(s) for s in matching_subs))
      self.head_table[head] = matching_subs[0]


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> tuple[slice,Any]:
    start = token
    while token.kind in self.drop:
      token = next(buffer)
    try: sub = self.head_table[token.kind]
    except KeyError: pass
    else:
      slc, val = self.parse_sub(sub, source, start, token, buffer)
      return slc, self.transform(source, slc, sub.field_name, val)
    exp = self.name or f'any of {self.subs_desc}'
    raise ParseError(source, token, f'{parent} expects {exp}; received {token.kind}.')



class Operator:
  'An operator that composes a part of a Precedence rule.'
  kinds:Tuple[TokenKind,...] = ()
  sub_refs:Tuple[RuleRef,...] = ()

  # TODO: spacing requirement options, e.g. no space, some space, symmetrical space.
  def __init__(self, *args:Any, **kwargs:Any): raise Exception(f'abstract base class: {self}')


  def parse_right(self, parent:Rule, source:Source, left:Any, op_token:Token, buffer:Buffer[Token], parse_level:Callable, level:int) -> tuple[int,Any]:
    raise NotImplementedError(self)



class Suffix(Operator):
  'A suffix/postfix operator: the suffix follows the primary expression. E.g. `*` in `A*`.'

  def __init__(self, suffix:TokenKind, transform:SuffixTransform=suffix_text_val_pair): # TODO: transform should take slc and token?
    self.kinds = (validate_name(suffix),)
    self.transform = transform


  def parse_right(self, parent:Rule, source:Source, left:Any, op_token:Token, buffer:Buffer[Token], parse_level:Callable, level:int) -> tuple[int,Any]:
    return op_token.end, self.transform(source, op_token, left) # No right-hand side.



class SuffixRule(Operator):
  '''
  A suffix/postfix rule: like the Suffix operator, except the suffix is an arbitrary rule.
  Note: due to current limitations in the linker implementation,
  `suffix` must be a constructed rule and not a string reference.
  '''

  def __init__(self, suffix:Rule, transform:BinaryTransform=binary_text_vals_triple): # TODO: transform should take slc.
    self.sub_refs = (suffix,)
    self.transform = transform


  @property
  def suffix(self) -> Rule: return cast(Rule, self.sub_refs[0]) # TODO: link over operators, and refer to self.subs instead.


  @property
  def kinds(self) -> Tuple[TokenKind,...]: # type: ignore[override]
    return tuple(self.suffix.heads)


  def parse_right(self, parent:Rule, source:Source, left:Any, op_token:Token, buffer:Buffer[Token], parse_level:Callable, level:int) -> tuple[int,Any]:
    slc, right = parent.parse_sub(self.suffix, source, op_token, op_token, buffer)
    return slc.stop, self.transform(source, op_token.pos_token(), left, right)



class BinaryOp(Operator):
  'Abstract base class for binary operators that take left and right primary expressions.'



class Adjacency(BinaryOp):
  'A binary operator that joins two primary expressions with no operator token in between.'
  kinds:Tuple[TokenKind,...] = () # Adjacency operators have no operator token.

  def __init__(self, transform:BinaryTransform=binary_vals_pair): # TODO transform should take slc.
    self.transform = transform


  @property # type: ignore[no-redef, override]
  def kinds(self) -> Tuple[TokenKind,...]:
    raise _AllLeafKinds


  def parse_right(self, parent:Rule, source:Source, left:Any, op_token:Token, buffer:Buffer[Token], parse_level:Callable, level:int) -> tuple[int,Any]:
    slc, right = parse_level(parent=parent, source=source, token=op_token, buffer=buffer, level=level)
    return slc.stop, self.transform(source, op_token.pos_token(), left, right)



class _AllLeafKinds(Exception):
  'Raised by Adjacency.kinds to signal that the precedence parser associates the set of leaf token kinds with this adjacency op.'



class Infix(BinaryOp):
  'A binary operator that joins two primary expressions with an infix operator.'

  def __init__(self, kind:TokenKind, transform:BinaryTransform=binary_text_vals_triple):
    self.kinds = (validate_name(kind),)
    self.transform = transform


  def parse_right(self, parent:Rule, source:Source, left:Any, op_token:Token, buffer:Buffer[Token], parse_level:Callable, level:int) -> tuple[int,Any]:
    slc, right = parse_level(parent=parent, source=source, token=next(buffer), buffer=buffer, level=level)
    return slc.stop, self.transform(source, op_token, left, right)



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



class Precedence(Rule):
  'An operator precedence rule, consisting of groups of operators.'
  type_desc = 'precedence rule'

  def __init__(self, leaves:Union[RuleRef,Iterable[RuleRef]], *groups:Group,
   field='', drop:Iterable[str]=(), transform:UniTransform=uni_val) -> None:

    # Keep track of the distinction between subs that came from leaves vs groups.
    # This allows us to catenate them all together to sub_refs, so they all get correctly linked,
    # and then get the linked leaves back via the leaves property implemented below.
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
    self.head_table:Dict[TokenKind,Rule] = {}
    self.tail_table:Dict[TokenKind,Tuple[Group,Operator]] = {}


  def token_kinds(self) -> Iterable[str]:
    for group in self.groups:
      for op in group.ops:
        try: yield from op.kinds
        except _AllLeafKinds: pass # Adjacency ops do not directly reference any token.


  def head_subs(self) -> Iterable[Rule]:
    return iter(self.subs[:len(self.leaf_refs)]) # Only the leaves can be heads.


  def compile(self, parser:'Parser') -> None:
    for head in self.heads:
      matching_subs = [s for s in self.subs if head in s.heads]
      assert matching_subs
      if len(matching_subs) > 1:
        raise Parser.DefinitionError(f'{self} contains ambiguous primaries for head token {head!r}:\n',
          *indent_lines(str(s) for s in matching_subs))
      self.head_table[head] = matching_subs[0]

    for i, group in enumerate(self.groups):
      group.level = i*10 # Multiplying by ten lets level_bump increase the level by one to achieve left-associativity.
      for op in group.ops:
        try: kinds = op.kinds
        except _AllLeafKinds: kinds = tuple(self.head_table)
        for kind in kinds:
          try: existing = self.tail_table[kind]
          except KeyError: pass
          else: raise Parser.DefinitionError(f'{self} contains ambiguous operators for token {kind!r}:\n', existing, op)
          self.tail_table[kind] = (group, op)


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> tuple[slice,Any]:
    slc, val = self.parse_level(parent, source, token, buffer, 0)
    return slc, self.transform(source, slc, val)


  def parse_level(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token], level:int) -> tuple[slice,Any]:
    left_slc, left = self.parse_leaf(parent, source, token, buffer)
    end = left_slc.stop
    while True:
      op_token = next(buffer)
      while op_token.kind in self.drop:
        op_token = next(buffer)
      try:
        group, op = self.tail_table[op_token.kind]
      except KeyError:
        break # op_token is not an operator.
      if group.level < level: break # This operator is at a lower precedence.
      end, left = op.parse_right(parent, source, left, op_token, buffer, self.parse_level, level=group.level+group.level_bump)
    # op_token is either not an operator, or of a lower precedence level.
    buffer.push(op_token) # Put it back.
    return slice(left_slc.start, end), left


  def parse_leaf(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> tuple[slice,Any]:
    start = token
    while token.kind in self.drop:
      token = next(buffer)
    try: sub = self.head_table[token.kind]
    except KeyError: pass
    else: return self.parse_sub(sub, source, start, token, buffer)
    exp = self.name or f'any of {self.subs_desc}'
    raise ParseError(source, token, f'{parent} expects {exp}; received {token.kind}.')



class SubParser(Rule):

  def __init__(self, parser:'Parser', rule_name:str, field='', transform:UniTransform=uni_val):
    self.name = ''
    self.field = field
    self.sub_refs = ()
    self.heads = parser.rules[rule_name].heads
    self.parser = parser
    self.rule = parser.rules[rule_name]
    self.transform = transform


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> tuple[slice,Any]:
    slc, sub_res = self.rule.parse(self, source, token, buffer)
    return slc, self.transform(source, slc, sub_res)



Preprocessor = Callable[[Source, Iterator[Token]], Iterable[Token]]


class Parser:
  '''
  drop: a set of token kinds to be dropped from the input token stream.

  literals: a set of token kinds that are fixed strings and should not be included in output structures.
  For example we might parse "(1 2 3)" with a rule like `Struct('paren_o', ZeroOrMore('expr'), 'paren_c')`.
  There is no utility in including the parenthesis tokens in the returned structure, because their string content is known.

  rules: a dict of rule names to rules.
  This dictionary is deep copied so that different parsers can attach different transforms to the same rule set.
  '''

  class DefinitionError(Exception):
    def __init__(self, *msgs:Any):
      super().__init__(''.join(str(msg) for msg in msgs))


  def __init__(self, lexer:Lexer, *, preprocessor:Preprocessor|None=None, drop:Iterable[TokenKind]=(),
   literals:Iterable[TokenKind]=(), rules:Dict[RuleName,Rule], transforms:dict[RuleName,Callable]|None=None):
    self.lexer = lexer
    self.preprocessor = preprocessor
    self.drop = frozenset(iter_str(drop))
    self.literals = frozenset(iter_str(literals))

    self.rules = deepcopy(rules)
    rules = None # type: ignore[assignment] # Forget the original dict. This protects from misuse in the code below.

    self.module_name = caller_module_name(1) # Get the calling module name to use for synthesized NamedTuple types.
    self._struct_types:Dict[str,Type] = {}

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

    self.types:Immutable[Type] = Immutable(**self._struct_types)


  def __del__(self) -> None:
    for rule in self.rules.values():
      rule.__dict__.clear() # Break all references between rules.


  def _mk_struct_transform(self, name:str, subs:Tuple[Rule,...]) -> StructTransform:

    includes = [((sub.field is not None) and (bool(sub.field) or (sub.name not in self.literals))) for sub in subs]
    #^ Bool for each sub position.
    #^ If field is None, that is an explicit request to exclude the field.
    #^ If field is provided, always include the field.
    #^ Otherwise, include the field only if it is not a literal.

    if includes.count(True) == 1: # No need for a struct; just extract the interesting child element.
      i = includes.index(True)
      def single_transform(source:Source, slc:slice, fields:List[Any]) -> Any: return fields[i]
      return single_transform

    raw_field_names = [sub.field_name for sub, should_inlude in zip(subs, includes) if should_inlude]
    field_names = ('slc', *(self._mk_clean_field_name(n, i) for i, n in enumerate(raw_field_names)))

    struct_type = self._mk_struct_type(name, field_names=field_names)

    def transform(source:Source, slc:slice, fields:List[Any]) -> Any:
      return struct_type(slc, *(f for f, should_include in zip(fields, includes) if should_include))

    return transform


  def _mk_clean_field_name(self, name:str, idx:int) -> str:
    if not name: return f'f{idx}'
    if iskeyword(name) or issoftkeyword(name) or name == 'token': return name + '_'
    if name[0].isdigit() or name[0] == '_': return 'f' + name
    return name


  def _mk_struct_type(self, name:str, field_names:tuple[str,...]) -> Type:
    if name:
      type_name = typecase_from_snakecase(name)
    else:
      type_name = '_'.join(typecase_from_snakecase(n) for n in field_names)

    try: existing = self._struct_types[type_name]
    except KeyError: pass
    else:
      if existing._fields != field_names:
        raise Parser.DefinitionError(f'conflicting fields for synthesized struct type {name}:\n  {existing._fields}\n  {field_names}')
      return existing
    struct_type = namedtuple(type_name, field_names, rename=True, module=self.module_name or '?') # type: ignore[misc]
    self._struct_types[type_name] = struct_type
    return struct_type


  def make_buffer(self, source:Source, dbg_tokens:bool) -> Buffer[Token]:
    stream = self.lexer.lex(source, drop=self.drop, eot=True)
    if self.preprocessor: stream = iter(self.preprocessor(source, stream))
    if dbg_tokens:
      stream = tee_to_err(stream, label='Parser dbg_tokens', transform=lambda t: f'{t}: {source[t]!r}')
    return Buffer(stream)


  def parse(self, rule_name:RuleName, source:Source, ignore_excess=False, dbg_tokens=False) -> Any:
    rule = self.rules[rule_name]
    buffer = self.make_buffer(source, dbg_tokens)
    token = next(buffer)
    _, result = rule.parse(parent=rule, source=source, token=token, buffer=buffer) # Top rule is passed as its own parent.
    excess_token = next(buffer) # Must exist because end_of_text cannot be consumed by a legal parser.
    if not ignore_excess and excess_token.kind != 'end_of_text':
      raise ExcessToken(source, excess_token, f'excess token: {excess_token.mode_kind}.')
    return result


  def parse_or_fail(self, rule_name:RuleName, source:Source, ignore_excess=False, dbg_tokens=False) -> Any:
    try: return self.parse(rule_name=rule_name, source=source, ignore_excess=ignore_excess, dbg_tokens=dbg_tokens)
    except ParseError as e: e.fail()


  def parse_all(self, rule_name:RuleName, source:Source, dbg_tokens=False) -> Iterator[Any]:
    rule = self.rules[rule_name]
    buffer = self.make_buffer(source, dbg_tokens=dbg_tokens)
    while True:
      token = next(buffer)
      if token.kind == 'end_of_text': return
      yield rule.parse(parent=rule, source=source, token=token, buffer=buffer) # Top rule is passed as its own parent.



def validate_name(name:Any) -> str:
  if not isinstance(name, str):
    raise Parser.DefinitionError(f'name is not a string: {name!r}')
  if not valid_name_re.fullmatch(name):
    raise Parser.DefinitionError(f'invalid name: {name!r}')
  if name in reserved_names:
    raise Parser.DefinitionError(f'name is reserved: {name!r}')
  return name
