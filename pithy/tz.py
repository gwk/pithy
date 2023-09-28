# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from datetime import datetime as DateTime, tzinfo as TZInfo, UTC as tz_utc


class TimeZoneError(ValueError): pass


def now_utc() -> DateTime:
  'Return the current time in UTC.'
  return DateTime.now(tz_utc)


def parse_dt_utc(date_str:str) -> DateTime:
  '''
  Parse a UTC datetime string.
  '''
  dt = DateTime.fromisoformat(date_str)
  if dt.tzinfo != tz_utc: raise TimeZoneError(f'Expected UTC time, got {date_str!r}')
  return dt


def parse_dt_naive_utc(date_str:str) -> DateTime:
  '''
  Parse a naive (no timezone) datetime string as UTC.
  '''
  dt = DateTime.fromisoformat(date_str)
  if dt.tzinfo is not None: raise TimeZoneError(f'Expected naive UTC time; received {date_str!r}')
  return dt.replace(tzinfo=tz_utc)


def parse_dt_naive(date_str:str, tz:TZInfo|None=None) -> DateTime:
  '''
  Parse a naive (no timezone) datetime string.
  If `tz` is provided, the parsed datetime will be given that timezone.
  '''
  dt = DateTime.fromisoformat(date_str)
  if dt.tzinfo is not None: raise TimeZoneError(f'Expected naive Eastern time; received {date_str!r}')
  if tz is not None: dt = dt.replace(tzinfo=tz)
  return dt
