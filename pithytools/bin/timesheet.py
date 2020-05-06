#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# total hours in a timesheet.

# format is:

# (YYYY-)?MM-DD
# 12:00 begin some task.
# 18:30 change tasks.
# 24:00 end the task = 12:00.
# +$100 cost of materials.
# -$100 a payment.

import re
from argparse import ArgumentParser
from dataclasses import dataclass
from typing import List, Match, Optional

from pithy.io import outL, outZ


@dataclass
class Day:
  day: str
  minutes: int = 0

  def __str__(self) -> str:
    return '{}: {:>2}:{:02}'.format(self.day, *divmod(self.minutes, 60))


def main() -> None:
  parser = ArgumentParser(description='Validate timesheets.')
  parser.add_argument('timesheet', nargs='?', default='timesheet.txt')
  parser.add_argument('-rate', type=int, default=0)
  args = parser.parse_args()

  path = args.timesheet
  hourly_rate = args.rate

  days:List[Day] = []
  start_minutes:Optional[int] = None
  end_minutes:Optional[int]   = None
  total_minutes = 0
  total_payment = 0.0
  total_expense = 0.0

  valid = True

  try: f = open(path)
  except FileNotFoundError: exit(f'bad path: {path}')

  for line in f:
    l = line.rstrip('\n')
    outZ(f'{l:64}')

    day_match = day_re.match(line)
    if day_match:
      outL('(day)')
      if start_minutes is not None or end_minutes is not None:
        exit(f'timesheet error: previous day is missing end time.')
      days.append(Day(day_match[0]))
      continue

    time_match = time_re.match(line)
    if time_match:
      m = minutes_for(time_match)
      if start_minutes is None: start_minutes = m
      else: end_minutes = m # Cumulative from last start.
      outZ(f'|{m:4} ')

    subtotal_match = subtotal_re.search(line)
    if subtotal_match:
      if not time_match:
        outL()
        exit(f'timesheet error: subtotal line does not specify a time.')
      if start_minutes is None or end_minutes is None:
        outL()
        exit(f'timesheet error: subtotal line has invalid time: {subtotal_match[0]!r}')
      sub_minutes = end_minutes - start_minutes
      m = minutes_for(subtotal_match)
      outZ(f'= {sub_minutes:4}m')
      if m != sub_minutes:
        outZ(f' *** found: {m}; calculated: {sub_minutes}')
        valid = False
      if sub_minutes <= 0:
        outL()
        exit(f'timesheet error: subtototal is negative')
      days[-1].minutes += sub_minutes
      total_minutes += sub_minutes
      start_minutes = None
      end_minutes = None

    money_match = money_re.match(line)
    if money_match:
      s = ''.join(money_match.groups())
      i = float(s)
      if (i < 0):
        total_payment += i
      else:
        total_expense += i
      outZ(f'               {i: 10,.2f}')

    outL()


  hours, minutes = divmod(int(total_minutes), 60)
  time_expense = hourly_rate * total_minutes / 60
  total = time_expense + total_payment + total_expense
  if hourly_rate:
    hourly_string = ' @ {:0.2f}/hr = ${:,.2f}'.format(hourly_rate, time_expense)
  else:
    hourly_string = ''

  outL()
  outL(f'DAYS:')
  for day in days: outL(day)

  outL()
  outL(f'TOTAL HOURS:   {hours:2}:{minutes:02}{hourly_string}')
  outL(f'TOTAL EXPENSE: ${total_expense:,.2f}')
  outL(f'TOTAL PAYMENT: ${total_payment:,.2f}')
  outL(f'TOTAL:         ${total:,.2f}')

  if not valid:
    exit('*** INVALID ***')


def minutes_for(match:Match) -> int:
  return int(match.group(1)) * 60 + int(match.group(2))

day_re      = re.compile(r'(?:(\d\d\d\d)-)?(\d\d)-(\d\d)')
time_re     = re.compile(r'(\d\d):(\d\d) ')
subtotal_re = re.compile(r'= (\d{1,2}):(\d\d)')
money_re    = re.compile(r'([+-])\s*\$(\d+)(\.?\d*)')


if __name__ == '__main__': main()
