# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter, defaultdict, namedtuple
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Annotated, Any, ClassVar, Literal, NamedTuple

from pithy.frozendicts import frozendict
from pithy.transtruct import Transtructor, TranstructorError
from utest import utest, utest_exc, utest_val


ttor = Transtructor(strict=False)

# Primitive types.

utest(0, ttor.transtruct, int, 0)
utest(0, ttor.transtruct, int, 0.0)
utest_exc(ValueError, ttor.transtruct, int, 0.9) # Fractional floats are rejected.
utest(0, ttor.transtruct, int, '0')

utest(0.0, ttor.transtruct, float, 0.0)
utest(0.0, ttor.transtruct, float, 0)
utest(0.0, ttor.transtruct, float, '0.0')

utest('0', ttor.transtruct, str, '0')
utest_exc(ValueError, ttor.transtruct, str, 0)
utest_exc(ValueError, ttor.transtruct, str, 0.0)

utest(1, ttor.transtruct, object, 1) # object passes any value through.

# Bool conversion accepts only well-known values; unknown values raise ValueError.
utest(True, ttor.transtruct, bool, True)
utest(False, ttor.transtruct, bool, False)
utest(True, ttor.transtruct, bool, 'true')
utest(False, ttor.transtruct, bool, 'false')
utest(True, ttor.transtruct, bool, '1')
utest(False, ttor.transtruct, bool, '0')
utest(True, ttor.transtruct, bool, 'yes')
utest(False, ttor.transtruct, bool, 'no')
utest(False, ttor.transtruct, bool, '') # Empty string maps to False.
utest(False, ttor.transtruct, bool, 0)
utest(True, ttor.transtruct, bool, 1)
utest_exc(ValueError, ttor.transtruct, bool, 'maybe')
utest_exc(ValueError, ttor.transtruct, bool, 2)
utest_exc(ValueError, ttor.transtruct, bool, 2.5)
utest_exc(ValueError, ttor.transtruct, bool, None)

# bool passes through to int/float because bool is a subclass of int.
utest(1, ttor.transtruct, int, True)
utest(0, ttor.transtruct, int, False)
utest(1.0, ttor.transtruct, float, True)
utest(0.0, ttor.transtruct, float, False)

# Strings that spell booleans must not double-convert through bool into int/float.
utest_exc(ValueError, ttor.transtruct, int, 'True')
utest_exc(ValueError, ttor.transtruct, int, 'yes')
utest_exc(ValueError, ttor.transtruct, float, 'True')
utest_exc(ValueError, ttor.transtruct, float, 'yes')

# Genuine numeric strings still convert directly.
utest(1, ttor.transtruct, int, '1')
utest(1.0, ttor.transtruct, float, '1')


@dataclass
class DC1:
  a:int
  b:str

class NT1(NamedTuple):
  a:int
  b:str

NTU1 = namedtuple('NTU1', 'a b') # Untyped namedtuple.


dc1 = DC1(1, 'a')
nt1 = NT1(1, 'a')
ntu1 = NTU1(1, 'a')


utest(dc1, ttor.transtruct, DC1, nt1)
utest(dc1, ttor.transtruct, DC1, ntu1)

utest(nt1, ttor.transtruct, NT1, dc1)
utest(nt1, ttor.transtruct, NT1, ntu1)

utest(ntu1, ttor.transtruct, NTU1, dc1)
utest(ntu1, ttor.transtruct, NTU1, nt1)


utest([dc1], ttor.transtruct, list[DC1], [nt1])
utest([dc1], ttor.transtruct, list[DC1], [ntu1])

utest([nt1], ttor.transtruct, list[NT1], [dc1])
utest([nt1], ttor.transtruct, list[NT1], [ntu1])

utest([ntu1], ttor.transtruct, list[NTU1], [dc1])
utest([ntu1], ttor.transtruct, list[NTU1], [nt1])


utest({'a':1}, ttor.transtruct, dict[str,int], Counter({'a':1}))
utest({'a':1}, ttor.transtruct, dict[str,int], defaultdict(lambda: 0, {'a':1}))

utest(Counter({'a':1}), ttor.transtruct, Counter[str], {'a':'1'})

utest(frozendict({'a':1}), ttor.transtruct, frozendict[str,int], {'a':'1'})
utest(frozendict({'a':1}), ttor.transtruct, frozendict[str,int], frozendict({'a':'1'}))


# A failing element inside a container notes its locus on the exception: the zero-based index for iterables,
# the key for dicts, and the field name for annotated classes.

def _locus_notes(desired:Any, val:Any) -> list[str]:
  '''
  Transtruct and return the locus notes of the raised exception chain; transtruct is expected to fail.
  The chain is walked because dict element failures are wrapped in TranstructorError, with the notes on the cause.
  The `desired`/`input` notes added by `try_transtruct` are excluded.
  '''
  try: ttor.transtruct(desired, val)
  except Exception as e:
    notes:list[str] = []
    exc:BaseException|None = e
    while exc is not None:
      notes.extend(n for n in getattr(exc, '__notes__', ()) if 'desired: ' not in n)
      exc = exc.__cause__
    return notes
  return ['<no exception>']

utest_val(['note: element 1 of list[int]'], _locus_notes(list[int], ['0', 'x']), desc='list element note')
utest_val(['note: element 0 of set[int]'], _locus_notes(set[int], ['x']), desc='set element note')
utest_val(['note: element 2 of tuple[int, ...]'], _locus_notes(tuple[int,...], ('0', '1', 'x')), desc='seq tuple element note')
utest_val(['note: element 1 of tuple[int, str]'], _locus_notes(tuple[int,str], ('0', 1)), desc='fixed tuple element note')

# Nested containers accumulate notes from innermost to outermost.
utest_val(['note: element 1 of list[int]', 'note: element 2 of list[list[int]]'],
  _locus_notes(list[list[int]], [['0'], ['1'], ['2', 'x']]), desc='nested list element notes')

# Dict failures note the failing key, or the key of the failing value.
utest_val(['note: key 0 of dict[str, int]'], _locus_notes(dict[str,int], {0: 1}), desc='dict key note')
utest_val(["note: value for key 'a' of dict[str, int]"], _locus_notes(dict[str,int], {'a': 'x'}), desc='dict value note')

# Annotated class fields note the field name for mapping input, or the argument index and field name for positional input.
utest_val([f"note: field 'a' of {DC1}"], _locus_notes(DC1, {'a': 'x', 'b': 'b'}), desc='class mapping field note')
utest_val([f"note: argument 0 (field 'a') of {DC1}"], _locus_notes(DC1, ['x', 'b']), desc='class positional field note')


utest(0, ttor.transtruct, int|str|None, 0)
utest('0', ttor.transtruct, int|str|None, '0')
utest(None, ttor.transtruct, int|str|None, None)

# Union members are validated: a primitive value must be an instance of a primitive member to pass through.
utest_exc(TranstructorError, ttor.transtruct, int|str|None, 0.5)
utest(True, ttor.transtruct, int|str|None, True) # bool is an int subclass.


class CustomInit:
  'Custom __init__ with parameters that differ from class-level annotations; transtruct uses the __init__ annotations.'

  data:dict[str,int]

  def __init__(self, key:str, val:int) -> None:
    self.data = {key: val}

  def __eq__(self, other:object) -> bool:
    return isinstance(other, CustomInit) and self.data == other.data

  def __repr__(self) -> str:
    return f'CustomInit({self.data!r})'


utest(CustomInit(key='a', val=1), ttor.transtruct, CustomInit, {'key': 'a', 'val': 1})


class BareAnnotated:
  'Annotation-only class with no custom __init__ or __new__; transtruct instantiates it and sets attributes directly.'

  x:int
  y:int
  note:str = 'default'

  def __eq__(self, other:object) -> bool:
    return isinstance(other, BareAnnotated) and (self.x, self.y, self.note) == (other.x, other.y, other.note)

  def __repr__(self) -> str:
    return f'BareAnnotated(x={self.x!r}, y={self.y!r}, note={self.note!r})'


def _bare_annotated(x:int, y:int, note:str='default') -> BareAnnotated:
  b = BareAnnotated()
  b.x = x
  b.y = y
  b.note = note
  return b


utest(_bare_annotated(1, 2), ttor.transtruct, BareAnnotated, {'x': 1, 'y': '2'})
utest(_bare_annotated(1, 2, 'hi'), ttor.transtruct, BareAnnotated, {'x': 1, 'y': 2, 'note': 'hi'})
utest(_bare_annotated(1, 2), ttor.transtruct, BareAnnotated, [1, 2]) # Positional sequence fills annotations in order.

# A missing key with no class-level default raises TranstructorError.
utest_exc(TranstructorError, ttor.transtruct, BareAnnotated, {'x': 1})


# Strict mode: unrecognized keys in mapping input raise TranstructorError; lax mode ignores them.

strict_ttor = Transtructor(strict=True)

utest(DC1(1, 'a'), ttor.transtruct, DC1, {'a': 1, 'b': 'a', 'extra': 0}) # Lax: extra key is ignored.
utest_exc(TranstructorError, strict_ttor.transtruct, DC1, {'a': 1, 'b': 'a', 'extra': 0})
utest_exc(TranstructorError, strict_ttor.transtruct, NT1, {'a': 1, 'b': 'a', 'extra': 0})
utest_exc(TranstructorError, strict_ttor.transtruct, BareAnnotated, {'x': 1, 'y': 2, 'extra': 0})

# Strict mode still accepts exactly matching keys.
utest(DC1(1, 'a'), strict_ttor.transtruct, DC1, {'a': 1, 'b': 'a'})
utest(NT1(1, 'a'), strict_ttor.transtruct, NT1, {'a': 1, 'b': 'a'})
utest(_bare_annotated(1, 2), strict_ttor.transtruct, BareAnnotated, {'x': 1, 'y': 2})


# Underscore-prefixed annotations are constructible fields like any other; use ClassVar to exclude internal state.

@dataclass
class DCU:
  _a:int
  b:str

utest(DCU(1, 'x'), ttor.transtruct, DCU, {'_a': 1, 'b': 'x'})
utest(DCU(1, 'x'), strict_ttor.transtruct, DCU, {'_a': 1, 'b': 'x'})


class UnderscoreInit:
  'Custom __init__ with an underscore-prefixed parameter.'

  def __init__(self, _key:str, val:int) -> None:
    self.data = {_key: val}

  def __eq__(self, other:object) -> bool:
    return isinstance(other, UnderscoreInit) and self.data == other.data

  def __repr__(self) -> str:
    return f'UnderscoreInit({self.data!r})'


utest(UnderscoreInit(_key='a', val=1), ttor.transtruct, UnderscoreInit, {'_key': 'a', 'val': 1})
utest(UnderscoreInit(_key='a', val=1), strict_ttor.transtruct, UnderscoreInit, {'_key': 'a', 'val': 1})


class BareUnderscore:
  'Annotation-only class with an underscore field; it is constructible, and absent input falls back to the class default.'

  x:int
  _hidden:int = 0

  def __eq__(self, other:object) -> bool:
    return isinstance(other, BareUnderscore) and (self.x, self._hidden) == (other.x, other._hidden)

  def __repr__(self) -> str:
    return f'BareUnderscore(x={self.x!r}, _hidden={self._hidden!r})'


def _bare_underscore(x:int, _hidden:int=0) -> BareUnderscore:
  b = BareUnderscore()
  b.x = x
  b._hidden = _hidden
  return b

utest(_bare_underscore(1, 3), ttor.transtruct, BareUnderscore, {'x': 1, '_hidden': 3})
utest(_bare_underscore(1, 3), strict_ttor.transtruct, BareUnderscore, {'x': 1, '_hidden': 3})
utest(_bare_underscore(1), ttor.transtruct, BareUnderscore, {'x': 1}) # Absent underscore field uses the class default.


class BareClassVar:
  'A ClassVar annotation is excluded from transtruction: never settable from input, unrecognized in strict mode.'

  x:int
  _registry:ClassVar[dict[str,int]] = {}

  def __eq__(self, other:object) -> bool:
    return isinstance(other, BareClassVar) and self.x == other.x

  def __repr__(self) -> str:
    return f'BareClassVar(x={self.x!r})'


def _bare_class_var(x:int) -> BareClassVar:
  b = BareClassVar()
  b.x = x
  return b

utest(_bare_class_var(1), ttor.transtruct, BareClassVar, {'x': 1, '_registry': {'a': 1}}) # Lax: ClassVar key is ignored.
utest_exc(TranstructorError, strict_ttor.transtruct, BareClassVar, {'x': 1, '_registry': {'a': 1}})
utest({}, lambda: BareClassVar._registry) # The class-level value is untouched.


# Scalar date/datetime/time types: parse isoformat strings by default.
utest(date(2026, 12, 31), ttor.transtruct, date, '2026-12-31')
utest(datetime(2026, 12, 31, 12, 30), ttor.transtruct, datetime, '2026-12-31T12:30:00')
utest(time(12, 30), ttor.transtruct, time, '12:30:00')

# Already-typed values pass through.
utest(date(2026, 12, 31), ttor.transtruct, date, date(2026, 12, 31))
utest(datetime(2026, 12, 31, 12, 30), ttor.transtruct, datetime, datetime(2026, 12, 31, 12, 30))
utest(time(12, 30), ttor.transtruct, time, time(12, 30))

# A datetime is truncated to a pure date (datetime is a date subclass).
utest(date(2026, 12, 31), ttor.transtruct, date, datetime(2026, 12, 31, 12, 30))

# Unparseable strings raise ValueError.
utest_exc(ValueError, ttor.transtruct, date, 'not-a-date')

# Non-string, non-temporal inputs raise ValueError rather than a bare fromisoformat TypeError.
utest_exc(ValueError, ttor.transtruct, date, 123)
utest_exc(ValueError, ttor.transtruct, datetime, 123)
utest_exc(ValueError, ttor.transtruct, time, 123)

# Scalars compose inside collections and optionals.
utest([date(2026, 12, 30), date(2026, 12, 31)], ttor.transtruct, list[date], ['2026-12-30', '2026-12-31'])
utest(date(2026, 12, 31), ttor.transtruct, date|None, '2026-12-31')
utest(None, ttor.transtruct, date|None, None)


# A prefigure can override the default scalar format; it reshapes the raw input before the default parser runs.
prefigure_date_ttor = Transtructor(strict=False)

@prefigure_date_ttor.prefigure(date)
def _prefigure_us_date(cls:type, val:Any, ctx:Any) -> Any:
  if isinstance(val, str): # Reshape 'MM/DD/YYYY' into an isoformat string for the default parser.
    month, day, year = val.split('/')
    return f'{year}-{month}-{day}'
  return val

utest(date(2026, 12, 31), prefigure_date_ttor.transtruct, date, '12/31/2026')
# The prefigure applies tree-wide to every `date` element.
utest([date(2026, 12, 30), date(2026, 12, 31)], prefigure_date_ttor.transtruct, list[date], ['12/30/2026', '12/31/2026'])


# TypeForm support: Literal types, None shorthand, `type X = ...` aliases and Annotated wrappers.

# Literal: exact members match directly; other inputs are coerced to a member type and must then match a member value.
utest('n', ttor.transtruct, Literal['n', 's'], 'n')
utest_exc(TranstructorError, ttor.transtruct, Literal['n', 's'], 'x')
utest(1, ttor.transtruct, Literal[1, 2], 1)
utest(1, ttor.transtruct, Literal[1, 2], '1')
utest_exc(TranstructorError, ttor.transtruct, Literal[1, 2], '3')
utest(True, ttor.transtruct, Literal[True], 'true')
utest(1, ttor.transtruct, Literal[1, 2], True) # Per PEP 586 True is not a member of Literal[1], but it coerces to int 1.
utest(None, ttor.transtruct, Literal['n', None], None) # None is permitted in Literal.

# None is shorthand for NoneType.
utest(None, ttor.transtruct, None, None)
utest_exc(ValueError, ttor.transtruct, None, 0)

# Annotated delegates to the underlying type.
utest(1, ttor.transtruct, Annotated[int, 'meta'], '1')

# Aliases are unwrapped, at the top level and nested.
type Direction = Literal['n', 's', 'e', 'w']
type IntList = list[int]
type AnnotatedInt = Annotated[int, 'meta']
type OptDirection = Direction|None

utest('n', ttor.transtruct, Direction, 'n')
utest_exc(TranstructorError, ttor.transtruct, Direction, 'x')
utest([1, 2], ttor.transtruct, IntList, ['1', 2])
utest(1, ttor.transtruct, AnnotatedInt, '1')
utest('n', ttor.transtruct, OptDirection, 'n')
utest(None, ttor.transtruct, OptDirection, None)

# Literal nested in generics and unions.
utest(['n', 's'], ttor.transtruct, list[Literal['n', 's']], ['n', 's'])
utest('n', ttor.transtruct, Literal['n', 's']|None, 'n')
utest(None, ttor.transtruct, Literal['n', 's']|None, None)

# A Literal member of a union validates values that do not match a primitive member.
utest(5, ttor.transtruct, Literal['n', 's']|int, 5)
utest('n', ttor.transtruct, Literal['n', 's']|int, 'n')
utest_exc(TranstructorError, ttor.transtruct, Literal['n', 's']|int, 'x')


@dataclass
class Move:
  direction:Direction
  dist:int

utest(Move('n', 2), ttor.transtruct, Move, {'direction': 'n', 'dist': '2'}) # Alias field type resolves through the annotation.
utest_exc(TranstructorError, ttor.transtruct, Move, {'direction': 'x', 'dist': '2'})


# Unions with more than one non-primitive member require a selector, keyed on the union of the non-primitive members.

@dataclass
class Circle:
  radius:float


@dataclass
class Rect:
  w:float
  h:float


shape_ttor = Transtructor(strict=False)

@shape_ttor.selector(Circle|Rect)
def _select_shape(T:Any, val:Any, ctx:Any) -> Any:
  return Circle if 'radius' in val else Rect


utest(Circle(1.5), shape_ttor.transtruct, Circle|Rect, {'radius': '1.5'})
utest(Rect(1.0, 2.0), shape_ttor.transtruct, Circle|Rect, {'w': 1, 'h': '2'})
utest([Circle(1.0), Rect(1.0, 2.0)], shape_ttor.transtruct, list[Circle|Rect], [{'radius': 1}, {'w': 1, 'h': 2}])

# The lookup key is the union of the non-primitive members, so wider unions with primitive members are also served.
utest(None, shape_ttor.transtruct, Circle|Rect|None, None)
utest(Circle(1.0), shape_ttor.transtruct, Circle|Rect|None, {'radius': 1})
utest('name', shape_ttor.transtruct, Circle|Rect|str, 'name')
utest(Rect(1.0, 2.0), shape_ttor.transtruct, Circle|Rect|str, {'w': 1, 'h': 2})

# Without a registered selector, a union with multiple non-primitive members fails at transtructor construction.
utest_exc(TranstructorError, ttor.transtruct, Circle|Rect, {'radius': 1})

# A selector that returns a non-member raises for each offending value.
bad_shape_ttor = Transtructor(strict=False)

@bad_shape_ttor.selector(Circle|Rect)
def _select_bad(T:Any, val:Any, ctx:Any) -> Any:
  return str

utest_exc(TranstructorError, bad_shape_ttor.transtruct, Circle|Rect, {'radius': 1}) # Via the selector refinement path.
utest_exc(TranstructorError, bad_shape_ttor.transtruct, Circle|Rect|None, {'radius': 1}) # Via the union residue path.
