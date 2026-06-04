# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter, defaultdict, namedtuple
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, NamedTuple

from pithy.frozendicts import frozendict
from pithy.transtruct import Transtructor
from utest import utest, utest_exc


ttor = Transtructor()

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


utest(0, ttor.transtruct, int|str|None, 0)
utest('0', ttor.transtruct, int|str|None, '0')
utest(None, ttor.transtruct, int|str|None, None)


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
prefigure_date_ttor = Transtructor()

@prefigure_date_ttor.prefigure(date)
def _prefigure_us_date(cls:type, val:Any, ctx:Any) -> Any:
  if isinstance(val, str): # Reshape 'MM/DD/YYYY' into an isoformat string for the default parser.
    month, day, year = val.split('/')
    return f'{year}-{month}-{day}'
  return val

utest(date(2026, 12, 31), prefigure_date_ttor.transtruct, date, '12/31/2026')
# The prefigure applies tree-wide to every `date` element.
utest([date(2026, 12, 30), date(2026, 12, 31)], prefigure_date_ttor.transtruct, list[date], ['12/30/2026', '12/31/2026'])
