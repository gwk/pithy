# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from datetime import date, datetime, timedelta


def parse_datetime(string, fmt='%Y-%m-%d %H:%M:%S'):
  return datetime.strptime(string, fmt)


def parse_date(string, fmt='%Y-%m-%d'):
  return datetime.strptime(string, fmt).date()


def next_days(date_, days):
  return date_ + timedlta(days=days)

def next_day(date_):
  return date_ + timedelta(days=1)

def next_week(date_):
  return date_ + timedelta(days=7)


def days_range(start, end, next=next_day):
  d = start
  while d < end:
    yield d
    d = next(d)
