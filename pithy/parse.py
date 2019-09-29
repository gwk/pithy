# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
A simple parser library based on recursive descent and operator precedence parsing.
Recursive decent is performed by looking at the next token,
and then dispatching through a table of token kinds to select the appropriate Rule.

Upon parsing, each type of rule produces a generic result, which is then passed to a user-provided transformer function.
Different rule types have different transformer function types to match the shape of the parsed structure.
Transformers can return results of any type.

Several types of rules are available:
* Atom: a single token kind.
* Prefix: a prefix token, followed by a body rule, optionally followed by a suffix.
* Quantity: a body rule, optionally interleaved with a separator token, with optional `min` and `max` quantities.
* Choice: one of several rules, which must be distinguishable by the head token.
* Precedence: a family of binary precedence operators.

The main design feature of Parser is that operators are not first-class rules:
they are parsed within the context of a Precedence rule.
This allows us to use the simple operator-precedence parsing algorithm,
while expressing other aspects of a grammar using straightforward recursive descent.
'''

import re
from typing import Any, Callable, Dict, FrozenSet, Iterable, Iterator, List, NoReturn, Optional, Set, Tuple, Union, cast

from tolkien import Source, Token

from .buffer import Buffer
from .graph import visit_nodes
from .lex import Lexer, Token, reserved_names, valid_name_re
from .string import indent_lines, pluralize



class ParseError(Exception):
  def __init__(self, source:Source, token:Token, *msgs:Any) -> None:
    self.source = source
    self.token = token
    self.msgs = msgs
    super().__init__((self.token, self.msgs))

  def fail(self) -> NoReturn:
    msg = ''.join(str(m) for m in self.msgs)
    self.source.fail(self.token, msg=msg)



class ExcessToken(ParseError):
  'Raised by Parser when expression parsing completes but does not exhaust the token stream.'



TokenKind = str
RuleName = str
RuleRef = Union['Rule',RuleName]


TreeTransform = Callable[[Source,Any],Any]
def tree_identity(source:Source, obj:Any) -> Any: return obj

TokenTransform = Callable[[Source,Token],Any]
def token_syn(source:Source, token:Token) -> str: return source[token]

UnaryTransform = Callable[[Source,Token,Any],Any]
def unary_syn(source:Source, token:Token, obj:Any) -> Tuple[str,Any]: return (source[token], obj)

BinaryTransform = Callable[[Source,Token,Any,Any],Any]
def binary_syn(source:Source, token:Token, left:Any, right:Any) -> Tuple[str,Any,Any]: return (source[token], left, right)

def adjacency_syn(source:Source, token:Token, left:Any, right:Any) -> Tuple[Any,Any]: return (left, right)

QuantityTransform = Callable[[Source,List[Any]],Any]
def quantity_identity(source:Source, elements:List[Any]) -> List[Any]: return elements

StructTransform = Callable[[Source,List[Any]],Any]
def struct_syn(source:Source, elements:List[Any]) -> Tuple[Any,...]: return tuple(elements)

ChoiceTransform = Callable[[Source,RuleName,Any],Any]
def choice_syn(source:Source, name:RuleName, obj:Any) -> Tuple[str,Any]: return (name, obj)


_sentinel_kind = '!SENTINEL'



class Rule:
  'A parser rule. A complete parser is created from a graph of rules.'

  name:str # Optional name, used to link the rule graph.
  type_desc:str # Type description for diagnostic descriptions.
  sub_refs:Tuple[RuleRef,...] = () # The rules or references (name strings) that this rule refers to.
  subs:Tuple['Rule',...] = () # Sub-rules, obtained by linking sub_refs.
  heads:Tuple[TokenKind,...] # Set of leading token kinds for this rule.

  def __init__(self, *args:Any, **kwargs:Any) -> None: raise Exception(f'abstract base class: {self}')


  def __str__(self) -> str:
    if self.name: return f'{self.name!r} {self.type_desc}'
    else: return repr(self)


  def __repr__(self) -> str:
    parts = []
    if self.name: parts.append(f'name={self.name!r}')
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
    if self.heads: # For recursive rules, the sentinel causes recursion to break here.
      yield from self.heads
      return
    # Otherwise, this rule does not yet know its own heads; discover them recursively.
    self.heads = (_sentinel_kind,) # Temporarily set to prevent recursion loops; use an impossible name.
    for sub in self.head_subs():
      yield from sub.compile_heads()
    # Now reset self.heads; it is up to Parser to call `compile_heads` for each node.
    # Otherwise, we would be relying on possibly incomplete sets that accumulate in intermediates during deep recursion.
    self.heads = ()


  def compile(self) -> None: pass


  def expect(self, source:Source, token:Token, kind:str) -> Token:
    if token.kind != kind: raise ParseError(source, token, f'{self} expects {kind}; received {token.kind}.')
    return token


  def parse(self, parent:'Rule', source:Source, token:Token, buffer:Buffer[Token]) -> Any:
    raise NotImplementedError(self)



class Atom(Rule):
  '''
  A rule that matches a single token.
  '''
  type_desc = 'atom'

  def __init__(self, kind:TokenKind, transform:TokenTransform=token_syn) -> None:
    self.name = ''
    self.heads = (kind,) # Pre-fill heads; compile_heads will return without calling head_subs, which Atom does not implement.
    self.kind = validate_name(kind)
    self.transform = transform


  def token_kinds(self) -> Iterable[str]:
    yield self.kind


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> Any:
    parent.expect(source, token, self.kind)
    #^ We use `parent` and not `self` to expect the token for a more contextualized error message.
    #^ Using `self` we get messages like "'newline' atom expects newline".
    return self.transform(source, token)



class Prefix(Rule):
  '''
  A rule that matches a prefix token, a body rule, and an optional suffix token.
  '''
  type_desc = 'prefix rule'

  def __init__(self, prefix:TokenKind, body:RuleRef, suffix:TokenKind=None, transform:UnaryTransform=unary_syn) -> None:
    self.name = ''
    self.sub_refs = (body,)
    self.heads = (prefix,) # Pre-fill heads.
    self.prefix = validate_name(prefix)
    self.suffix = suffix if suffix is None else validate_name(suffix)
    self.transform = transform


  @property
  def body(self) -> Rule:
    assert len(self.subs) == len(self.sub_refs), (self, self.subs, self.sub_refs)
    return self.subs[0]


  def token_kinds(self) -> Iterable[str]:
    yield self.prefix
    if self.suffix is not None:
      yield self.suffix


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> Any:
    self.expect(source, token, self.prefix)
    syn = self.body.parse(self, source, next(buffer), buffer)
    if self.suffix: self.expect(source, next(buffer), self.suffix)
    return self.transform(source, token, syn)



class _QuantityRule(Rule):
  'Base class for Opt and Quantity.'
  min:int
  body_heads:FrozenSet[str]
  drop:FrozenSet[str]

  @property
  def body(self) -> Rule:
    return self.subs[0]


  def head_subs(self) -> Iterable['Rule']:
    return (self.body,)


  def compile(self) -> None:
    self.body_heads = frozenset(self.body.heads)
    drop_body_intersect = self.body_heads & self.drop
    if drop_body_intersect:
      raise Parser.DefinitionError(f'{self} drop kinds and body head kinds intersect: {drop_body_intersect}')



class Opt(_QuantityRule):
  '''
  A rule that optionally matches another rule.
  '''
  type_desc = 'optional'
  min = 0

  def __init__(self, body:RuleRef, drop:Iterable[str]=(), transform:TreeTransform=tree_identity) -> None:
    self.sub_refs = (body,)
    self.heads = ()
    self.body_heads = frozenset() # Replaced by compile.
    self.drop = frozenset([drop] if isinstance(drop, str) else drop)
    self.transform = transform


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> Any:
    res = None
    while token.kind in self.drop:
      token = next(buffer)
    if token.kind in self.body_heads:
      res = self.body.parse(self, source, token, buffer)
    else:
      buffer.push(token)
    return self.transform(source, res)



class Quantity(_QuantityRule):
  '''
  A rule that matches some quantity of another rule.
  '''
  type_desc = 'quantity'

  def __init__(self, body:RuleRef, sep:TokenKind=None, sep_at_end:Optional[bool]=None, min=0, max=None, drop:Iterable[str]=(),
   transform:QuantityTransform=quantity_identity) -> None:
    if min < 0: raise ValueError(min)
    if max is not None and max < 1: raise ValueError(max) # The rule must consume at least one token; see `parse` implementation.
    if sep is None and sep_at_end is not None: raise ValueError(f'`sep` is None but `sep_at_end` is `{sep_at_end}`')
    self.name = ''
    self.sub_refs = (body,)
    self.heads = ()
    self.sep = sep if sep is None else validate_name(sep)
    self.sep_at_end:Optional[bool] = sep_at_end
    self.min = min
    self.max = max
    self.body_heads = frozenset() # Replaced by compile.
    self.drop = frozenset([drop] if isinstance(drop, str) else drop)
    self.transform = transform


  def token_kinds(self) -> Iterable[str]:
    if self.sep is not None:
      yield self.sep
    yield from self.drop


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> Any:
    els:List[Any] = []
    found_sep = False
    while True:
      while token.kind in self.drop:
        token = next(buffer)
      if len(els) == self.max or token.kind not in self.body_heads: break
      el = self.body.parse(self, source, token, buffer)
      els.append(el)
      token = next(buffer)
      if self.sep is not None: # Parse separator.
        found_sep = (token.kind == self.sep)
        if found_sep:
          token = next(buffer)
        elif self.sep_at_end:
          raise ParseError(source, token, f'{self} expects {self.sep} separator; received {token.kind}.')
        else:
          break

    if len(els) < self.min:
      body_plural = pluralize(self.min, f'{self.body} element')
      raise ParseError(source, token, f'{self} expects at least {body_plural}; received {token.kind}.')

    if self.sep_at_end is False and found_sep:
      raise ParseError(source, token, f'{self} received unpexpected {self.sep} separator.')

    buffer.push(token)
    return self.transform(source, els)


class ZeroOrMore(Quantity):
  def __init__(self, body:RuleRef, sep:TokenKind=None, sep_at_end:Optional[bool]=None, drop:Iterable[str]=(),
   transform:QuantityTransform=quantity_identity) -> None:
    super().__init__(body=body, sep=sep, sep_at_end=sep_at_end, min=0, drop=drop, transform=transform)


class OneOrMore(Quantity):
  def __init__(self, body:RuleRef, sep:TokenKind=None, sep_at_end:Optional[bool]=None, drop:Iterable[str]=(),
   transform:QuantityTransform=quantity_identity) -> None:
    super().__init__(body=body, sep=sep, sep_at_end=sep_at_end, min=1, drop=drop, transform=transform)


class Struct(Rule):
  '''
  A rule that matches a sequence of sub rules, producing a tuple of values.
  '''
  type_desc = 'structure'

  def __init__(self, *fields:RuleRef, drop:Iterable[str]=(), transform:StructTransform=struct_syn) -> None:
    if not fields: raise ValueError('Struct requires at least one field')
    self.name = ''
    self.sub_refs = fields
    self.heads = ()
    self.drop = frozenset([drop] if isinstance(drop, str) else drop)
    self.transform = transform


  def head_subs(self) -> Iterable['Rule']:
    for field in self.subs:
      yield field
      if not (isinstance(field, Quantity) and field.min == 0):
        break


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> Any:
    els:List[Any] = []
    for i, field in enumerate(self.subs):
      if i:
        token = next(buffer)
      while token.kind in self.drop:
        token = next(buffer)
      el = field.parse(self, source, token, buffer)
      els.append(el)
    return self.transform(source, els)



class Choice(Rule):
  '''
  A rule that matches one of a set of choices, which must have unambiguous heads.
  '''
  type_desc = 'choice'

  def __init__(self, *choices:RuleRef, drop:Iterable[str]=(), transform:ChoiceTransform=choice_syn) -> None:
    self.name = ''
    self.sub_refs = choices
    self.heads = ()
    self.drop = frozenset([drop] if isinstance(drop, str) else drop)
    self.transform = transform
    self.head_table:Dict[TokenKind,Rule] = {}


  def head_subs(self) -> Iterable[Rule]: return self.subs


  def compile(self) -> None:
    for head in self.heads:
      matching_subs = [s for s in self.subs if head in s.heads]
      assert matching_subs
      if len(matching_subs) > 1:
        raise Parser.DefinitionError(f'{self} contains ambiguous choices for head token {head!r}:\n',
          *indent_lines(str(s) for s in matching_subs))
      self.head_table[head] = matching_subs[0]


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> Any:
    while token.kind in self.drop:
      token = next(buffer)
    try: sub = self.head_table[token.kind]
    except KeyError: pass
    else:
      syn = sub.parse(self, source, token, buffer)
      return self.transform(source, sub.name, syn)
    raise ParseError(source, token, f'{self} expects any of {self.subs_desc}; received {token.kind}')



class Operator:
  'An operator that composes a part of a Precedence rule.'
  kinds:Tuple[TokenKind,...] = ()
  sub_refs:Tuple[RuleRef,...] = ()

  # TODO: spacing requirement options, e.g. no space, some space, symmetrical space.
  def __init__(self, *args:Any, **kwargs:Any) -> None: raise Exception(f'abstract base class: {self}')


  def parse_right(self, left:Any, source:Source, op_token:Token, buffer:Buffer[Token], parse_precedence_level:Callable, level:int) -> Any:
    raise NotImplementedError(self)



class Suffix(Operator):
  'A suffix/postfix operator: the suffix follows the primary expression. E.g. `*` in `A*`.'

  def __init__(self, suffix:TokenKind, transform:UnaryTransform=unary_syn) -> None:
    self.kinds = (validate_name(suffix),)
    self.transform = transform


  def parse_right(self, left:Any, source:Source, op_token:Token, buffer:Buffer[Token], parse_precedence_level:Callable, level:int) -> Any:
    return self.transform(source, op_token, left) # No right-hand side.



class SuffixRule(Operator):
  '''
  A suffix/postfix rule: like the Suffix operator, except the suffix is an arbitrary rule.
  Note: due to current limitations in the linker implementation,
  `suffix` must be a constructed rule and not a string reference.
  '''

  def __init__(self, suffix:Rule, transform:BinaryTransform=binary_syn) -> None:
    self.sub_refs = (suffix,)
    self.transform = transform


  @property
  def suffix(self) -> Rule: return cast(Rule, self.sub_refs[0]) # TODO: link over operators, and refer to self.subs instead.


  @property
  def kinds(self) -> Tuple[TokenKind,...]: # type: ignore
    return tuple(self.suffix.heads)


  def parse_right(self, left:Any, source:Source, op_token:Token, buffer:Buffer[Token],
   parse_precedence_level:Callable, level:int) -> Any:
    right = self.suffix.parse(cast(Rule, self), source, op_token, buffer)
    return self.transform(source, op_token.pos_token(), left, right)



class BinaryOp(Operator):
  'Abstract base class for binary operators that take left and right primary expressions.'



class Adjacency(BinaryOp):
  'A binary operator that joins two primary expressions with no operator token in between.'
  kinds:Tuple[TokenKind,...] = () # Adjacency operators have no operator token.

  def __init__(self, transform:BinaryTransform=adjacency_syn) -> None:
    self.transform = transform


  @property # type: ignore
  def kinds(self) -> Tuple[TokenKind,...]: # type: ignore
    raise _AllLeafKinds


  def parse_right(self, left:Any, source:Source, op_token:Token, buffer:Buffer[Token], parse_precedence_level:Callable, level:int) -> Any:
    right = parse_precedence_level(source=source, token=op_token, buffer=buffer, level=level)
    return self.transform(source, op_token.pos_token(), left, right)



class _AllLeafKinds(Exception):
  'Raised by Adjacency.kinds to signal that the precedence parser associates the set of leaf token kinds with this adjacency op.'



class Infix(BinaryOp):
  'A binary operator that joins two primary expressions with an infix operator.'

  def __init__(self, kind:TokenKind, transform:BinaryTransform=binary_syn) -> None:
    self.kinds = (validate_name(kind),)
    self.transform = transform


  def parse_right(self, left:Any, source:Source, op_token:Token, buffer:Buffer[Token], parse_precedence_level:Callable, level:int) -> Any:
    right = parse_precedence_level(source=source, token=next(buffer), buffer=buffer, level=level)
    return self.transform(source, op_token, left, right)



class Group:
  level_bump = 0
  'Operator precedence group.'

  def __init__(self, *ops:Operator) -> None:
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

  def __init__(self, leaves:Union[RuleRef,Iterable[RuleRef]], *groups:Group, transform:TreeTransform=tree_identity) -> None:
    # Keep track of the distinction between subs that came from leaves vs groups.
    # This allows us to catenate them all together to sub_refs, so they all get correctly linked,
    # and then get the linked leaves back via the leaves property implemented below.
    if isinstance(leaves, (str,Rule)): leaves = (leaves,)
    self.leaf_refs = tuple(leaves)
    self.group_refs = tuple(ref for g in groups for ref in g.sub_refs)
    self.name = ''
    self.sub_refs = self.leaf_refs + self.group_refs
    self.heads = ()
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


  def compile(self) -> None:
    for head in self.heads:
      matching_subs = [s for s in self.subs if head in s.heads]
      assert matching_subs
      if len(matching_subs) > 1:
        raise Parser.DefinitionError(f'{self} contains ambiguous primaries for head token {head!r}:\n',
          *indent_lines(str(s) for s in matching_subs))
      self.head_table[head] = matching_subs[0]

    for i, group in enumerate(self.groups):
      group.level = i*10 # Multiplying by ten lets us fudge the level by one to achieve right-associativity.
      for op in group.ops:
        try: kinds = op.kinds
        except _AllLeafKinds: kinds = tuple(self.head_table)
        for kind in kinds:
          try: existing = self.tail_table[kind]
          except KeyError: pass
          else: raise Parser.DefinitionError(f'{self} contains ambiguous operators for token {kind!r}:\n', existing, op)
          self.tail_table[kind] = (group, op)


  def parse(self, parent:Rule, source:Source, token:Token, buffer:Buffer[Token]) -> Any:
    syn = self.parse_precedence_level(source, token, buffer, 0)
    return self.transform(source, syn)


  def parse_precedence_level(self, source:Source, token:Token, buffer:Buffer[Token], level:int) -> Any:
    left = self.parse_leaf(source, token, buffer)
    while True:
      op_token = next(buffer)
      try:
        group, op = self.tail_table[op_token.kind]
      except KeyError:
        break # op_token is not an operator.
      if group.level < level: break # This operator is at a lower precedence.
      left = op.parse_right(left, source, op_token, buffer, self.parse_precedence_level, level=group.level+group.level_bump)
    # op_token is either not an operator, or of a lower precedence level.
    buffer.push(op_token) # Put it back.
    return left


  def parse_leaf(self, source:Source, token:Token, buffer:Buffer[Token]) -> Any:
    try: sub = self.head_table[token.kind]
    except KeyError: pass
    else: return sub.parse(self, source, token, buffer)
    raise ParseError(source, token, f'{self} expects any of {self.subs_desc}; received {token.kind}.')



class Parser:
  '''
  '''

  class DefinitionError(Exception):
    def __init__(self, *msgs:Any) -> None:
      super().__init__(''.join(str(msg) for msg in msgs))


  def __init__(self, lexer:Lexer, rules:Dict[RuleName,Rule], drop:Iterable[TokenKind]=()) -> None:
    self.lexer = lexer
    self.rules = rules
    self.drop = frozenset([drop] if isinstance(drop, str) else drop)

    for name, rule in rules.items():
      validate_name(name)
      rule.name = name

    # Link rule graph. Note: this creates reference cycles which are dissolved with unlink() in __del__ below.

    def linker(rule:RuleRef) -> Rule:
      if isinstance(rule, Rule): return rule
      try: return rules[rule]
      except KeyError: pass
      raise Parser.DefinitionError(f'nonexistent rule: {rule!r}')

    def link(rule:Rule) -> Iterable[Rule]:
      assert not rule.subs
      if rule.sub_refs:
        rule.subs = tuple(linker(s) for s in rule.sub_refs)
      assert len(rule.subs) == len(rule.sub_refs)
      return rule.subs

    self.nodes = visit_nodes(self.rules.values(), link) # All of the rule nodes.

    for rule in self.nodes:
      # Validate token references.
      for token_kind in rule.token_kinds():
        if token_kind not in lexer.patterns:
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
      rule.compile()


  def __del__(self) -> None:
    for rule in self.rules.values():
      rule.__dict__.clear() # Break all references between rules.


  def make_buffer(self, source:Source) -> Buffer[Token]:
    stream = self.lexer.lex(source, drop=self.drop, eot=True)
    return Buffer(stream)


  def parse(self, rule_name:RuleName, source:Source, ignore_excess=False) -> Any:
    rule = self.rules[rule_name]
    buffer = self.make_buffer(source)
    token = next(buffer)
    result = rule.parse(parent=rule, source=source, token=token, buffer=buffer) # Top rule is passed as its own parent.
    excess_token = next(buffer) # Must exist because end_of_text cannot be consumed by a legal parser.
    if not ignore_excess and excess_token.kind != 'end_of_text':
      raise ExcessToken(source, excess_token, 'error: excess token: ', excess_token.kind)
    return result


  def parse_or_fail(self, rule_name:RuleName, source:Source, ignore_excess=False) -> Any:
    try: return self.parse(rule_name=rule_name, source=source, ignore_excess=ignore_excess)
    except ParseError as e: e.fail()


  def parse_all(self, rule_name:RuleName, source:Source) -> Iterator[Any]:
    rule = self.rules[rule_name]
    buffer = self.make_buffer(source)
    while True:
      token = next(buffer)
      if token.kind == 'end_of_text': return
      yield rule.parse(parent=rule, source=source, token=token, buffer=buffer) # Top rule is passed as its own parent.



def validate_name(name:str) -> str:
  if not (isinstance(name, str) and valid_name_re.fullmatch(name)):
    raise Parser.DefinitionError(f'invalid name: {name!r}')
  if name in reserved_names:
    raise Parser.DefinitionError(f'name is reserved: {name!r}')
  return name
