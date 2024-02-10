# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from dataclasses import dataclass, field
from datetime import date as Date, datetime as DateTime, time as Time, timedelta as TimeDelta, tzinfo as TZInfo, UTC as tz_utc
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


def now_utc() -> DateTime:
  'Return a DateTime for the current moment in the UTC timezone.'
  return DateTime.now(tz_utc)


def today_utc() -> Date:
  'Return a Date for the current moment in the UTC timezone.'
  return now_utc().date()


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


def dt_IM(dt:DateTime|Time, compact=False) -> str:
  'Format a DateTime or Time as e.g. "4:00".'
  return f'{dt:%I:%M}'.lstrip('0') # '04:00'.lstrip('0') => '4:00'.


def dtp_IM(start:DateTime|Time, end:DateTime|Time) -> str:
  'Format a DateTime or Time range as e.g. "4:00-5:00".'
  return f'{dt_IM(start)}-{dt_IM(end)}'


def dt_IMp(dt:DateTime|Time, compact=False) -> str:
  'Format a DateTime or Time as e.g. "4:00PM", or "4PM" if compact is True.'
  if compact and not dt.minute:
    return f'{dt:%I%p}'.lstrip('0') # '04AM'.lstrip('0') => '4AM'.
  return f'{dt:%I:%M%p}'.lstrip('0') # '04:30AM'.lstrip('0') => '4:30AM'.


def dtp_IMp(start:DateTime|Time, end:DateTime|Time, compact=False) -> str:
  'Format a DateTime or Time range as e.g. "4:00PM-5:00PM", or "4PM-5PM" if compact is True.'
  return f'{dt_IMp(start, compact)}-{dt_IMp(end, compact)}'


def dt_Ymd_IMp(dt:DateTime|Time, include_at:bool=False) -> str:
  'Format a DateTime or Time as e.g. "2020-01-01 4:30PM".'
  time = dt_IMp(dt)
  at = ' at ' if include_at else ' '
  return f'{dt:%Y-%m-%d}{at}{time}'


def parse_dt(string: str, fmt:str|None=None) -> DateTime:
  if fmt: return DateTime.strptime(string, fmt)
  return DateTime.fromisoformat(string)


def parse_date(string: str, fmt:str|None=None) -> Date:
  if fmt: return DateTime.strptime(string, fmt).date()
  return Date.fromisoformat(string)


def parse_time(string:str, tz:TZInfo|None=None) -> Time:
  '''
  Parse a time string, accepting either 24-hour (isoformat) or 12-hour (with AM/PM) formats.
  Isoformat times with an explicit timezone are rejected.
  Raises ValueError.
  '''
  try: isotime = Time.fromisoformat(string)
  except ValueError: pass
  else:
    if isotime.tzinfo is not None: raise ValueError(isotime)
    if tz: isotime = isotime.replace(tzinfo=tz)
    return isotime
  return parse_time_12h(string, tz=tz)


def parse_time_12h(string:str, tz:TZInfo|None=None) -> Time:
  '''
  Parse a time string in 12-hour (with AM/PM) format.
  raises ValueError.
  '''
  match = time_re.fullmatch(string)
  if match is None: raise ValueError(string)

  sh, sm, ss, sf, ampm = match.group('h', 'm', 's', 'f', 'ampm')

  h = int(sh)
  m = int(sm)
  s = int(ss) if ss is not None else 0
  f = int(sf) if sf is not None else 0
  if ampm is None: raise ValueError(f'parse_time_12h: missing AM/PM: {string!r}')
  if h > 12: raise ValueError(string)
  if ampm == 'am':
    if h == 12: h = 0
  else:
    assert ampm == 'pm', ampm
    if h < 12: h += 12
  return Time(h, m, s, f, tzinfo=tz)


time_re = re.compile(r'''(?ix)
  (?P<h>\d{1,2})
  : (?P<m>\d{2})
  (?: # Seconds are optional.
    : P(?P<s>\d{2})
    (?: # Fractional seconds are optional.
      \. (?P<f>\d*)
    )?
  )?
  (?P<ampm>[ap]m)? # AM/PM is optional.
  ''')


def parse_time_12hmp(string:str, tz:TZInfo|None=None) -> Time:
  '''
  Parse a time string in 12-hour H:MM AM/PM format.
  raises ValueError.
  '''
  match = time_12hmp_re.fullmatch(string)
  if match is None: raise ValueError(string)

  sh, sm, ampm = match.groups()

  h = int(sh)
  m = int(sm)
  assert 1 <= h <= 12, h
  assert 0 <= m <= 59, m
  ampm = ampm.lower()
  if ampm == 'am':
    if h == 12: h = 0
  else:
    assert ampm == 'pm', ampm
    if h < 12: h += 12
  return Time(h, m, tzinfo=tz)


time_12hmp_re = re.compile(r'(1[012]|[1-9]):([0-5][0-9]) ?([AaPp][Mm])')


def dt_from_ts_utc(ts:float) -> DateTime:
  'Create a DateTime from a UTC timestamp.'
  return DateTime.fromtimestamp(ts, tz_utc)


def dt_from(*, date:Date, hours:int=0, minutes:int=0, seconds:int=0, tzinfo:TZInfo|None=None) -> DateTime:
  return DateTime(date.year, date.month, date.day, tzinfo=tzinfo) + TimeDelta(hours=hours, minutes=minutes, seconds=seconds)


_DateOrDateTime = TypeVar('_DateOrDateTime', Date, DateTime)

def next_day(date_: _DateOrDateTime) -> _DateOrDateTime:
  return date_ + TimeDelta(days=1)

def next_week(date_: _DateOrDateTime) -> _DateOrDateTime:
  return date_ + TimeDelta(days=7)


def time_delta(a:Time, b:Time) -> TimeDelta:
  'Subtract two times, returning a timedelta.'
  return TimeDelta(hours=a.hour - b.hour, minutes=a.minute - b.minute, seconds=a.second - b.second,
    microseconds=a.microsecond - b.microsecond)
