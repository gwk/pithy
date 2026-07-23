# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# An example of every Python syntax type.
# Used to test completeness of the Sem implementation.
# Match statements are omitted here and exercised separately in basic.ut.python.

# Imports. The type: ignore comment produces a SemTypeIgnore child on the SemModule. TODO: use a different kind of ignore that doesn't upset the checker.
import os
import os.path as op
from contextlib import asynccontextmanager
from os import path as p
from os.path import join
from typing import Any, AsyncGenerator, Callable, Iterator


_unused_imports = (op, p, join)

_:Any

# Type aliases.
type Int = int # TypeVar, empty type_params. TODO: remove?
type Vector[T] = list[T] # TypeVar
type Shape[*Ts] = tuple[*Ts] # TypeVarTuple
type Decorator[**P] = Callable[P, None]  # ParamSpec

x:int = 1 # Annotated assignment with value (SemAnnAssign with store).

y:int # Annotated assignment without value (declaration-only SemAnnAssign).

z = 2 # Simple assignment (SemAssign).

class Matrix:
    def __matmul__(self, other:Matrix) -> Matrix: return Matrix()

_i:int = 0
_f:float = 0.0
_m = Matrix()

# Augmented assignments: AugAssign.
_i += 1   # SemAdd
_i -= 1   # SemSub
_i *= 1   # SemMult
_f /= 1   # SemDiv
_i %= 1   # SemMod
_i **= 1  # SemPow
_i <<= 1  # SemLShift
_i >>= 1  # SemRShift
_i |= 1   # SemBitOr
_i ^= 1   # SemBitXor
_i &= 1   # SemBitAnd
_i //= 1  # SemFloorDiv
_m @= _m  # SemMatMult

_ = _f + _f   # SemBinOp.

# Boolean operators: SemBoolOp.
_ = _i and _i # SemAnd
_ = _i or _i  # SemOr

# Unary operators.
_ = ~_i    # SemInvert
_ = not _i  # SemNot
_ = +_i    # SemUAdd
_ = -_i    # SemUSub

# Comparison operators.
_ = _i == 1        # SemEq
_ = _i != 1        # SemNotEq
_ = _i < 1         # SemLt
_ = _i <= 1        # SemLtE
_ = _i > 1         # SemGt
_ = _i >= 1        # SemGtE
_ = _i is None     # SemIs
_ = _i is not None  # SemIsNot
_ = _i in [1]      # SemIn
_ = _i not in [1]  # SemNotIn


# Named expression / walrus (SemNamedExpr).
if (w := 10) > 5:
  pass

# Conditional expression / ternary (SemIfExp).
_ = 1 if _i else 0

# f-string: SemJoinedStr with SemFormattedValue and SemConstant children.
_name = 'world'
_fstr = f'hello {_name}'

# t-string: SemTemplateStr with SemInterpolation children.
_tstr = t'hello {_name}'

# Lambda (SemLambda, SemArguments, SemArg, SemKeyword in the default-value keyword).
_lam = lambda a, b=0, *args, c=1, **kw: a + b + c

# Dict, set, list, tuple literals.
_dict = {'key': 'val'}
_set = {1, 2}
_list = [1, 2, 3]
_tuple = (1, 2, 3)

# Subscript and slice (SemSubscript, SemSlice).
_ = _list[0]
_ = _list[1:2]
_ = _list[::2]

# Attribute access (SemAttribute).
_ = os.path

# Call with keyword argument (SemCall, SemKeyword).
_ = dict(a=1, b=2)

def f(*args:int) -> tuple[int,...]: return args

# Starred in function call (SemStarred with load context).
f(*_list)

# Starred in tuple assignment (SemStarred with store context, SemTuple store).
_first, *_rest = _list

# List with store context (SemList store).
[_a, _b] = [1, 2]

# Delete (SemDelete, SemName with del context).
del _a, _b

# Assert (SemAssert).
assert _i >= 0, 'must be non-negative'

# Bare expression statement (SemExpr).
os.getcwd()

# Comprehensions (SemListComp, SemSetComp, SemDictComp, SemGeneratorExp, SemComprehension).
_lc = [i for i in range(10) if i > 5]
_sc = {i for i in range(10)}
_dc = {i: i * 2 for i in range(10)}
_ge = (i for i in range(10))

# Try/except/else/finally (SemTry, SemExceptHandler).
try:
  raise ValueError('demo')  # SemRaise
except ValueError as _e:
  _ = _e
except (TypeError, KeyError):
  pass
else:
  pass # type: ignore[unreachable]
finally:
  pass

# Exception groups / TryStar (SemTryStar).
try:
  pass
except* ValueError:
  pass

# If/elif/else (SemIf).
if _i == 1:
  pass
elif _i == 2:
  pass
else:
  pass

# While with break and continue (SemWhile, SemBreak, SemContinue).
while _i > 100:
  if _i == 99:
    break
  continue

# For with break and continue (SemFor).
for _i in range(10):
  if _i == 0:
    continue
  if _i == 9:
    break

# With statement (SemWith, SemWithItem).
with open(os.devnull) as _file:
  pass

# Class definitions (SemClassDef, SemPass, SemAnnAssign declaration).
class Base:
  pass

class Derived(Base):
  x: int

  def method(self, a:int, b:int=0, *args:str, c:int=1, **kwargs:str) -> None:
    pass


# Generic class and functions — exercises SemTypeVar, SemParamSpec, SemTypeVarTuple.
class GenericClass[T, **P, *Ts]:
  pass

def generic_fn[T](a:T) -> T:
  return a


# Function with global declaration (SemGlobal).
_g = 0
def fn_global() -> None:
  global _g
  _g += 1


# Nested function with nonlocal (SemNonlocal).
def fn_outer() -> None:
  _v = 0
  def fn_inner() -> None:
    nonlocal _v
    _v += 1
  fn_inner()


# Generator function with yield and yield from (SemYield, SemYieldFrom).
def gen_fn() -> Iterator[int]:
  yield 1
  yield from range(10)


# Async helpers — bodies kept minimal for parsing only.
async def _async_gen() -> AsyncGenerator[int]:
  yield 1


@asynccontextmanager
async def _async_cm() -> AsyncGenerator[None, None]:
  yield


# Async function with await, async for, async with (SemAsyncFunctionDef, SemAwait,
# SemAsyncFor, SemAsyncWith).
async def async_fn() -> None:
  import asyncio
  await asyncio.sleep(0)
  async for _ in _async_gen():
    pass
  async with _async_cm() as _:
    pass
