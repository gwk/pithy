# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass, field
from datetime import (date as Date, datetime as DateTime, time as Time, timedelta as TimeDelta, timezone as TimeZone,
  tzinfo as TZInfo)
from typing import Iterator, overload, Sequence, TypeVar


sec_per_min = 60
sec_per_hour = sec_per_min * 60
sec_per_day = sec_per_hour * 24

months = ('January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December')

month_days = {
  1: 31,
  2: 28, # Leap day must be handled separately.
  3: 31,
  4: 30,
  5: 31,
  6: 30,
  7: 31,
  8: 31,
  9: 30,
  10: 31,
  11: 30,
  12: 31,
}


def num_days_of_month(year:int, month:int) -> int:
  if month == 2 and is_leap_year(year): return 29
  return month_days[month]


def days_in_year(year:int) -> int:
  if year % 4: return 365
  if year % 100: return 366
  if year % 400: return 365
  return 366


def is_leap_year(year:int) -> bool:
  return not bool((year%4) and (year%100 or not (year%400)))


DateLike = TypeVar('DateLike', 'DateDelta', Date, DateTime)


@dataclass(frozen=True)
class DateDelta:
  years:int = 0
  months:int = 0


  def __add__(self, other:DateLike) -> DateLike:
    if isinstance(other, DateDelta):
      carry_years, months = divmod(self.months + other.months, 12)
      years = self.years + other.years + carry_years
      return DateDelta(years, months)
    try:
      date_year = other.year
      date_month = other.month
      date_day = other.day
      date_replace = other.replace
    except AttributeError as e:
      raise TypeError(f'cannot add DateDelta to {type(other).__name__!r}') from e
    carry_years, month0 = divmod(date_month + self.months - 1, 12)
    year = date_year + self.years + carry_years
    month = month0 + 1
    last_valid_day = num_days_of_month(year, month)
    if date_day > last_valid_day:
      return date_replace(year=year, month=month, day=last_valid_day)
    else:
      return date_replace(year=year, month=month)


  def __neg__(self) -> 'DateDelta':
    return DateDelta(-self.years, -self.months)


  def __sub__(self, other:DateLike) -> DateLike:
    if isinstance(other, DateDelta):
      return DateDelta(self.years - other.years, self.months - other.months)
    raise TypeError(f'cannot subtract {type(other).__name__!r} from DateDelta')



@dataclass(frozen=True)
class DateRange(Sequence[Date]):
  start:Date
  end:Date
  step:DateDelta|TimeDelta = TimeDelta(days=1)
  _seq:list[Date] = field(default_factory=list, compare=False, init=False, repr=False)


  def __post_init__(self):
    start = self.start
    end = self.end
    if start > end: raise ValueError(f'start > end: start={start}; end={end}.')
    d = start
    while d < end:
      self._seq.append(d)
      d = self.step + d # Add in this order to accommodate DateDelta.


  def __contains__(self, value: object) -> bool:
    return super().__contains__(value)


  @overload
  def __getitem__(self, index:int) -> Date: ...

  @overload
  def __getitem__(self, index:slice) -> Sequence[Date]: ...

  def __getitem__(self, index): return self._seq[index]


  def __iter__(self) -> Iterator[Date]: return iter(self._seq)

  def __len__(self) -> int: return len(self._seq)



def parse_dt(string: str, fmt:str|None=None) -> DateTime:
  if fmt: return DateTime.strptime(string, fmt)
  return DateTime.fromisoformat(string)


def parse_date(string: str, fmt:str|None=None) -> Date:
  if fmt: return DateTime.strptime(string, fmt).date()
  return Date.fromisoformat(string)


def dt_for_utc_ts(ts:float) -> DateTime:
  return DateTime.fromtimestamp(ts, TimeZone.utc)


def dt_from(*, date:Date, hours:int=0, minutes:int=0, seconds:int=0, tzinfo:TZInfo|None=None) -> DateTime:
  return DateTime(date.year, date.month, date.day, tzinfo=tzinfo) + TimeDelta(hours=hours, minutes=minutes, seconds=seconds)


_DateOrDateTime = TypeVar('_DateOrDateTime', Date, DateTime)

def next_day(date_: _DateOrDateTime) -> _DateOrDateTime:
  return date_ + TimeDelta(days=1)

def next_week(date_: _DateOrDateTime) -> _DateOrDateTime:
  return date_ + TimeDelta(days=7)
