# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Simple parser based on recursive descent and operator precedence parsing.
'''

import re
from typing import Any, Callable, Dict, FrozenSet, Iterable, Iterator, List, NewType, NoReturn, Set, Tuple, Union, cast

from .buffer import Buffer
from .graph import visit_nodes
from .lex import Lexer, Token, pos_token, reserved_names, token_fail, valid_name_re
from .string import indent_lines


class ParseError(Exception):
  def __init__(self, token:Token, *msgs:str) -> None:
    self.token = token
    self.msg = ' '.join(msgs)
    super().__init__(self.msg)

  def fail(self, path:str) -> NoReturn:
    token_fail(path=path, token=self.token, msg=self.msg)


class ExcessToken(ParseError): pass


TokenKind = str
RuleName = str
RuleRef = Union['Rule',RuleName]


Transform = Callable[[Any],Any]
def identity(obj:Any) -> Any: return obj

TokenTransform = Callable[[Token],Any]
def token_syn(token:Token) -> Any: return token[0]

UnaryTransform = Callable[[Token,Any],Any]
def unary_syn(token:Token, obj:Any) -> Any: return (token[0], obj)

BinaryTransform = Callable[[Token,Any,Any],Any]
def binary_syn(token:Token, left:Any, right:Any) -> Any: return (token[0], left, right)

ChoiceTransform = Callable[[RuleName,Any],Any]
def choice_syn(name:RuleName, obj:Any) -> Any: return (name, obj)


_sentinel_kind = '!SENTINEL'


class Rule:
  name:str
  sub_refs:Tuple[RuleRef,...] = ()
  subs:Tuple['Rule',...] = () # Sub-rules, obtained by linking sub_refs.
  heads:Tuple[TokenKind,...] # Set of leading token kinds for this rule.

  def __init__(self, *args:Any, **kwargs:Any) -> None: raise Exception(f'abstract base class: {self}')

  def __str__(self) -> str:
    if self.name: return f'{self.name}:{type(self).__name__}'
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
  def head_subs(self) -> Iterable['Rule']:
    raise NotImplementedError(repr(self))

  def compile_heads(self) -> Iterator[TokenKind]:
    if self.heads: # For recursive rules, the sentinel causes recursion to break here.
      yield from self.heads
      return
    # This rule does not yet know its own heads; discover them recursively.
    self.heads = (_sentinel_kind,) # Temporarily set to prevent recursion loops; use an impossible name for Match.lastgroup.
    for sub in self.head_subs:
      yield from sub.compile_heads()
    # Now reset self.heads; it is up to Parser to do so for each node. Otherwise results will be incomplete.
    self.heads = ()


  def compile(self) -> None: pass


  def expect(self, token:Token, kind:str) -> Token:
    if token.lastgroup != kind: raise ParseError(token, f'{self} expects {kind}: received {token.lastgroup}.')
    return token


  def parse(self, token:Token, buffer:Buffer) -> Any:
    raise NotImplementedError(self)


class Atom(Rule):
  '''
  A rule that matches a single token.
  '''

  def __init__(self, kind:TokenKind, transform:TokenTransform=token_syn) -> None:
    self.name = ''
    self.heads = (kind,)
    self.kind = validate_name(kind)
    self.transform = transform

  def parse(self, token:Token, buffer:Buffer) -> Any:
    self.expect(token, self.kind)
    return self.transform(token)


class Prefix(Rule):
  '''
  A rule that matches a prefix token, a body rule, and an optional suffix token.
  '''

  def __init__(self, prefix:TokenKind, body:RuleRef, suffix:TokenKind=None, transform:UnaryTransform=unary_syn) -> None:
    self.name = ''
    self.sub_refs = (body,)
    self.heads = (prefix,)
    self.prefix = validate_name(prefix)
    self.suffix = suffix and validate_name(suffix)
    self.transform = transform

  @property
  def body(self) -> Rule:
    assert len(self.subs) == len(self.sub_refs), (self, self.subs, self.sub_refs)
    return self.subs[0]

  def parse(self, token:Token, buffer:Buffer) -> Any:
    self.expect(token, self.prefix)
    syn = self.body.parse(next(buffer), buffer)
    if self.suffix: self.expect(next(buffer), self.suffix)
    return self.transform(token, syn)


class Choice(Rule):
  '''
  A rule that matches one of a set of choices, which must have unambiguous heads.
  '''

  def __init__(self, *choices:RuleRef, transform:ChoiceTransform=choice_syn) -> None:
    self.name = ''
    self.sub_refs = choices
    self.heads = ()
    self.transform = transform
    self.head_table:Dict[TokenKind,Rule] = {}

  @property
  def head_subs(self) -> Iterable[Rule]: return self.subs

  def compile(self) -> None:
    for head in self.heads:
      matching_subs = [s for s in self.subs if head in s.heads]
      assert matching_subs
      if len(matching_subs) > 1:
        raise Parser.DefinitionError(f'{self} contains ambiguous choices for head token {head!r}:\n',
          *indent_lines(str(s) for s in matching_subs))
      self.head_table[head] = matching_subs[0]

  def parse(self, token:Token, buffer:Buffer) -> Any:
    try: sub = self.head_table[token.lastgroup]
    except KeyError: pass
    else:
      syn = sub.parse(token, buffer)
      return self.transform(sub.name, syn)
    raise ParseError(token, f'{self} expects any of {sorted(self.subs)}; received {token.lastgroup}')


class Operator:
  'An operator that composes a part of a Precedence rule.'
  kinds:Tuple[TokenKind,...] = ()
  sub_refs:Tuple[RuleRef,...] = ()

  # TODO: spacing requirement options, e.g. no space, some space, symmetrical space.
  def __init__(self, *args:Any, **kwargs:Any) -> None: raise Exception(f'abstract base class: {self}')

  def parse_right(self, left:Any, op_token:Token, buffer:Buffer, parse_precedence_level:Callable, level:int) -> Any:
    raise NotImplementedError(self)


class Suffix(Operator):
  'A suffix/postfix operator: the suffix follows the primary expression. E.g. `*` in `A*`.'
  def __init__(self, suffix:TokenKind, transform:UnaryTransform=unary_syn) -> None:
    self.kinds = (validate_name(suffix),)
    self.transform = transform

  def parse_right(self, left:Any, op_token:Token, buffer:Buffer, parse_precedence_level:Callable, level:int) -> Any:
    return self.transform(op_token, left) # No right-hand side.


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

  def parse_right(self, left:Any, op_token:Token, buffer:Buffer, parse_precedence_level:Callable, level:int) -> Any:
    right = self.suffix.parse(op_token, buffer)
    return self.transform(pos_token(op_token), left, right)


class BinaryOp(Operator):
  'Abstract base class for binary operators that take left and right primary expressions.'


class Adjacency(BinaryOp):
  'A binary operator that joins two primary expressions with no operator token in between.'
  kinds:Tuple[TokenKind,...] = () # Adjacency operators have no operator token.

  def __init__(self, transform:BinaryTransform=binary_syn) -> None:
    self.transform = transform

  @property
  def kinds(self) -> Tuple[TokenKind,...]: # type: ignore
    raise _AllLeafKinds

  def parse_right(self, left:Any, op_token:Token, buffer:Buffer, parse_precedence_level:Callable, level:int) -> Any:
    right = parse_precedence_level(token=op_token, buffer=buffer, level=level)
    return self.transform(pos_token(op_token), left, right)

class _AllLeafKinds(Exception): pass


class Infix(BinaryOp):
  'A binary operator that joins two primary expressions with an infix operator.'
  def __init__(self, kind:TokenKind, transform:BinaryTransform=binary_syn) -> None:
    self.kinds = (validate_name(kind),)
    self.transform = transform

  def parse_right(self, left:Any, op_token:Token, buffer:Buffer, parse_precedence_level:Callable, level:int) -> Any:
    right = parse_precedence_level(token=next(buffer), buffer=buffer, level=level)
    return self.transform(op_token, left, right)


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

  def __init__(self, leaves:Iterable[RuleRef], *groups:Group, transform:Transform=identity) -> None:
    # Keep track of the distinction between subs that came from leaves vs groups.
    # This allows us to catenate them all together to sub_refs, so they all get correctly linked,
    # and then get the linked leaves back via the leaves property implemented below.
    self.leaf_refs = tuple(leaves)
    self.group_refs = tuple(ref for g in groups for ref in g.sub_refs)
    self.name = ''
    self.sub_refs = self.leaf_refs + self.group_refs
    self.heads = ()
    self.transform = transform
    self.groups = groups
    self.head_table:Dict[TokenKind,Rule] = {}
    self.tail_table:Dict[TokenKind,Tuple[Group,Operator]] = {}

  @property
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


  def parse(self, token:Token, buffer:Buffer) -> Any:
    syn = self.parse_precedence_level(token, buffer, 0)
    return self.transform(syn)


  def parse_precedence_level(self, token:Token, buffer:Buffer, level:int) -> Any:
    left = self.parse_leaf(token, buffer)
    while True:
      op_token = next(buffer)
      try:
        group, op = self.tail_table[op_token.lastgroup]
      except KeyError:
        break # op_token is not an operator.
      if group.level < level: break # This operator is at a lower precedence.
      left = op.parse_right(left, op_token, buffer, self.parse_precedence_level, level=level+group.level_bump)
    # op_token is either not an operator, or of a lower precedence level.
    buffer.push(op_token) # Put it back.
    return left


  def parse_leaf(self, token:Token, buffer:Buffer) -> Any:
    try: sub = self.head_table[token.lastgroup]
    except KeyError: pass
    else: return sub.parse(token, buffer)
    raise ParseError(token, f'{self} expects any of {sorted(self.subs)}; received {token.lastgroup}')



class Parser:
  '''
  '''

  class DefinitionError(Exception):
    def __init__(self, *msgs:Any) -> None:
      super().__init__(''.join(str(msg) for msg in msgs))


  def __init__(self, lexer:Lexer, rules:Dict[RuleName,Rule], drop:Iterable[TokenKind]=()) -> None:
    self.lexer = lexer
    self.rules = rules
    self.drop = frozenset(drop)

    for name, rule in rules.items():
      validate_name(name)
      rule.name = name

    # Link rule graph. Note: this creates reference cycles which are dissolved with unlink() in __del__ below.

    def linker(rule:RuleRef) -> Rule:
      return rule if isinstance(rule, Rule) else rules[rule]

    def link(rule:Rule) -> Iterable[Rule]:
      assert not rule.subs
      if rule.sub_refs:
        rule.subs = tuple(linker(s) for s in rule.sub_refs)
      assert len(rule.subs) == len(rule.sub_refs)
      return rule.subs

    self.nodes = visit_nodes(self.rules.values(), link) # All of the rule nodes.

    # Compile heads.
    for rule in self.nodes:
      if isinstance(rule, Atom):
        if rule.kind not in lexer.patterns:
          raise Parser.DefinitionError(f'{rule} refers to nonexistent token kind: {rule.kind}')
      if not rule.heads:
        heads = set(rule.compile_heads())
        try: heads.remove(_sentinel_kind)
        except KeyError: pass
        rule.heads = tuple(sorted(heads))
        assert rule.heads
    for rule in self.nodes:
      rule.compile()


  def __del__(self) -> None:
    for rule in self.rules.values():
      rule.__dict__.clear() # Break all references between rules.


  def make_buffer(self, text:str) -> Buffer[Token]:
    stream = self.lexer.lex(text, drop=self.drop, eot=True)
    return Buffer(stream)


  def parse(self, name:RuleName, text:str, ignore_excess=False) -> Any:
    rule = self.rules[name]
    buffer = self.make_buffer(text)
    token = next(buffer)
    result = rule.parse(token, buffer)
    excess_token = next(buffer) # Must exist because end_of_text cannot be consumed by a legal parser.
    if not ignore_excess and excess_token.lastgroup != 'end_of_text':
      raise ExcessToken(excess_token, 'error: excess token')
    return result


  def parse_or_fail(self, path:str, name:RuleName, text:str, ignore_excess=False) -> Any:
    try: return self.parse(name=name, text=text, ignore_excess=ignore_excess)
    except ParseError as e:
      token_fail(path=path, token=e.token, msg=e.msg)


  def parse_all(self, name:RuleName, text:str) -> Iterator[Any]:
    rule = self.rules[name]
    buffer = self.make_buffer(text)
    while True:
      token = next(buffer)
      if token.lastgroup == 'end_of_text': return
      yield rule.parse(token, buffer)



def validate_name(name:str) -> str:
  if not valid_name_re.fullmatch(name):
    raise Parser.DefinitionError(f'invalid name: {name!r}')
  if name in reserved_names:
    raise Parser.DefinitionError(f'name is reserved: {name!r}')
  return name
