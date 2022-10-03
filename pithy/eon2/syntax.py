# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from functools import singledispatch
from typing import Iterable, Iterator, Union

from tolkien import Source, Token


section_rank_leaf = 1_000_000_000

class EonNode:
  token:Token

  @property
  def section_rank(self) -> int:
    token = self.token
    if token.kind == 'section':
      return token.end - token.pos
    return section_rank_leaf


EonSyntax = Union[Token,EonNode]


def eon_syntax_token(syntax:EonSyntax) -> Token:
  return syntax if isinstance(syntax, Token) else syntax.token


def is_eon_syntax_inlineable(syntax:EonSyntax) -> bool:
  if isinstance(syntax, (Token, EonStr)):
    return True
  if isinstance(syntax, EonBinding):
    assert is_eon_syntax_inlineable(syntax.key), syntax.key
    return is_eon_syntax_inlineable(syntax.val)
  if isinstance(syntax, EonList):
    return False
  raise TypeError(syntax)



class EonBinding(EonNode):
  key: EonSyntax
  eq: Token # TODO: remove and just use `token`?
  val: EonSyntax

  def __init__(self, token:Token, key:EonSyntax, val:EonSyntax):
    self.token = token
    self.key = key
    self.val = val


class EonList(EonNode):
  def __init__(self, token:Token, els:list['EonSyntax']):
    self.token = token
    self.els = els

  def __repr__(self) -> str: return f'{type(self).__name__}({self.token}, <{len(self.els)} els>)'

  def __iter__(self) -> Iterator[EonSyntax]: return iter(self.els)


class EonStr(EonNode):
  def __init__(self, token:Token, tokens:list[Token]):
    self.token = token
    self.tokens = tokens

  def __repr__(self) -> str: return f'{type(self).__name__}({self.token}, <{len(self.tokens)} tokens>)'

  def __iter__(self) -> Iterator[EonSyntax]: return iter(self.tokens)

  def value(self, source:Source) -> str:
    return ''.join(source[t] for t in self.tokens) # TODO: handle escapes!!


@singledispatch
def render_eon_syntax(syntax:EonSyntax, source:Source, depth:int=0) -> Iterable[str]:
    raise NotImplementedError


@render_eon_syntax.register # type: ignore[no-redef]
def _(syntax:Token, source:Source, depth:int=0) -> Iterable[str]:
    return source[syntax]


@render_eon_syntax.register # type: ignore[no-redef]
def _(syntax:EonStr, source:Source, depth:int=0) -> Iterable[str]:
  q = source[syntax.token]
  content = ''.join(source[t] for t in syntax.tokens)
  return f'{q}{content}{q}'


@render_eon_syntax.register # type: ignore[no-redef]
def _(syntax:EonBinding, source:Source, depth:int=0) -> Iterator[str]:
  assert is_eon_syntax_inlineable(syntax.key)
  yield from render_eon_syntax(syntax.key, source, depth=depth)
  if is_eon_syntax_inlineable(syntax.val):
    yield '='
  else:
    yield ' =\n' + '  ' * (depth+1)
  yield from render_eon_syntax(syntax.val, source, depth=depth+1)


@render_eon_syntax.register # type: ignore[no-redef]
def _(syntax:EonList, source:Source, depth:int=0) -> Iterable[str]:
  child_indent = '  ' * (depth+1)
  is_inline = True
  has_inlined = False
  if syntax.token.kind == 'section':
    yield source[syntax.token]
    has_inlined = True
  is_el_inlineable = True
  for el in syntax.els:
    r = render_eon_syntax(el, source, depth=depth+1)
    is_el_inlineable = is_eon_syntax_inlineable(el)
    if is_inline and is_el_inlineable:
      if has_inlined: yield ' '
      else: has_inlined = True
      if isinstance(r, str): yield r # Optimization; otherwise would yield character by character.
      else: yield from r
    else:
      assert has_inlined
      if is_inline:
        yield '\n'
        is_inline = False
      yield child_indent
      if isinstance(r, str):
        yield r # Optimization.
      else:
        yield from r
      if is_el_inlineable:
        yield '\n'
  if is_inline:
    yield '\n'
