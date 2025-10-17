# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Callable, Self, TypeVar


Leaf = TypeVar('Leaf')


class Logic[Leaf]():
  'A base class for logical operations.'

  slc:slice|None = None

  def __init__(self, slc:slice|None=None):
    self.slc = slc

  def __eq__(self, other:Any) -> bool:
    return bool(self.__class__ == other.__class__ and self.slc == other.slc and self.subs == other.subs)

  def __replace__(self, **changes:Any) -> Self:
    'Return a copy of this logic node with some fields replaced.'
    params = {**self.__dict__, **changes}
    return self.__class__(**params)

  @property
  def subs(self) -> tuple[Logic[Leaf]|Leaf,...]:
    'Return the sub-expressions of this logic node.'
    raise NotImplementedError

  def skeletonize(self, skeletonize_sub:Callable) -> Self:
    raise NotImplementedError


class LogicUnary[Leaf](Logic[Leaf]):
  'A base class for unary logical operations.'
  sub:Logic[Leaf]|Leaf

  def __init__(self, slc:slice|None=None, *, sub:Logic[Leaf]|Leaf):
    super().__init__(slc=slc)
    self.sub = sub

  def __repr__(self) -> str:
    slc_str= '' if self.slc is None else f'{self.slc.start}…{self.slc.stop}, '
    return f'{self.__class__.__name__}({slc_str}sub={self.sub})'

  def __str__(self) -> str:
    return f'{self.__class__.__name__}({self.sub})'

  @property
  def subs(self) -> tuple[Logic[Leaf]|Leaf,...]:
    return (self.sub,)

  def skeletonize(self, skeletonize_sub:Callable) -> Self:
    return self.__class__(slc=None, sub=skeletonize_sub(self.sub))


class LogicBinary(Logic[Leaf]):
  'A base class for binary logical operations.'
  l:Logic[Leaf]|Leaf
  r:Logic[Leaf]|Leaf

  def __init__(self, slc:slice|None=None, *, l:Logic[Leaf]|Leaf, r:Logic[Leaf]|Leaf):
    super().__init__(slc=slc)
    self.l = l
    self.r = r

  def __repr__(self) -> str:
    slc_str= '' if self.slc is None else f'{self.slc.start}…{self.slc.stop}, '
    return f'{self.__class__.__name__}({slc_str}l={self.l}, r={self.r})'

  def __str__(self) -> str:
    return f'{self.__class__.__name__}({self.l}, {self.r})'

  @property
  def subs(self) -> tuple[Logic[Leaf]|Leaf,...]:
    return (self.l, self.r)

  def skeletonize(self, skeletonize_sub:Callable) -> Self:
    return self.__class__(slc=None, l=skeletonize_sub(self.l), r=skeletonize_sub(self.r))


class Assign(LogicBinary):
  'A class representing the assignment operation.'

class Or(LogicBinary):
  'A class representing the logical OR operation.'

class And(LogicBinary):
  'A class representing the logical AND operation.'

class Not(LogicUnary):
  'A class representing the logical NOT operation.'

class Comparison(LogicBinary):
  'A class representing comparison operations.'

class Lt(Comparison):
  'A class representing the less-than comparison operation.'

class Le(Comparison):
  'A class representing the less-than-or-equal-to comparison operation.'

class Gt(Comparison):
  'A class representing the greater-than comparison operation.'

class Ge(Comparison):
  'A class representing the greater-than-or-equal-to comparison operation.'

class Eq(Comparison):
  'A class representing the equality comparison operation.'

class Ne(Comparison):
  'A class representing the inequality comparison operation.'

class Match(Comparison):
  'A class representing the regex match comparison operation.'

class Is(Comparison):
  'A class representing the identity comparison operation.'

class IsNot(Comparison):
  'A class representing the non-identity comparison operation.'

class In(Comparison):
  'A class representing the membership test operation.'

class NotIn(Comparison):
  'A class representing the non-membership test operation.'

class BitOr(LogicBinary):
  'A class representing the bitwise OR operation.'

class BitXor(LogicBinary):
  'A class representing the bitwise XOR operation.'

class BitAnd(LogicBinary):
  'A class representing the bitwise AND operation.'

class Shift(LogicBinary):
  'A class representing the bitwise shift operation.'

class LShift(Shift):
  'A class representing the left shift operation.'

class RShift(Shift):
  'A class representing the right shift operation.'

class Add(LogicBinary):
  'A class representing the addition operation.'

class Sub(LogicBinary):
  'A class representing the subtraction operation.'

class Mul(LogicBinary):
  'A class representing the multiplication operation.'

class MatMul(LogicBinary):
  'A class representing the matrix multiplication operation.'

class Div(LogicBinary):
  'A class representing the division operation.'

class FloorDiv(LogicBinary):
  'A class representing the floor division operation.'

class Mod(LogicBinary):
  'A class representing the modulo operation.'

class Pos(LogicUnary):
  'A class representing the unary positive operation.'

class Neg(LogicUnary):
  'A class representing the unary negative operation.'

class BitNot(LogicUnary):
  'A class representing the bitwise NOT operation.'

class Pow(LogicBinary):
  'A class representing the exponentiation operation.'

class Subscript(LogicBinary):
  'A class representing subscript operations.'

class Call(LogicBinary):
  'A class representing function call operatios.'

class Access(LogicBinary):
  'A class representing attribute access operations.'
