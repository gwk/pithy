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

from pithy.iterable import fan_by_key_fn
from pithy.io import outL, outZ


def main() -> None:
  parser = ArgumentParser(description='Validate timesheets.')
  parser.add_argument('timesheet', nargs='?', default='timesheet.txt')
  parser.add_argument('-rates', nargs='+', default=[0])
  args = parser.parse_args()

  path = args.timesheet
  hourly_rates = [int(r) for r in args.rates]

  days:List[Day] = []
  all_blocks:List[TimeBlock] = []

  curr_blocks:List[TimeBlock] = []
  start_minutes:Optional[int] = None
  prev_minutes:Optional[int] = None
  end_minutes:Optional[int] = None
  prev_rate:Optional[int] = None
  total_payment = 0.0
  total_expense = 0.0

  valid = True

  try: f = open(path)
  except FileNotFoundError: exit(f'bad path: {path}')

  for line in f:
    l = line.rstrip('\n')
    outZ(f'{l:48}')

    # Match a date line, e.g. '2020-01-01' or '01-01'.
    day_match = day_re.match(line)
    if day_match:
      outL('.')
      if start_minutes is not None or end_minutes is not None:
        exit(f'timesheet error: previous day is missing end time.')
      curr_blocks = []
      days.append(Day(day=day_match[0], blocks=curr_blocks))
      continue

    # Match a time line, e.g. '12:00: some note.'.
    if time_match := time_re.match(line):

      # Parse the optional rate.
      if rate_match := rate_idx_re.search(line):
        rate_idx = int(rate_match.group(1))
        if rate_idx >= len(hourly_rates):
          exit(f'timesheet error: rate index {rate_idx} is out of range.')
        rate = hourly_rates[rate_idx]
      else:
        rate = hourly_rates[0]

      m = minutes_for(time_match)
      if start_minutes is None:
        start_minutes = m
        block_str = ''
      else:
        end_minutes = m # Cumulative from last start.
        assert prev_minutes is not None
        assert prev_rate is not None
        block = TimeBlock(start=prev_minutes, end=end_minutes, rate=prev_rate)
        all_blocks.append(block)
        curr_blocks.append(block)
        block_str = f' {block}'
      prev_minutes = m
      prev_rate = rate
      outZ(f'|{m:4}{block_str}')

      # Match an inline subtotal, e.g. '12:00 finished = 1:00'.
      if subtotal_match := subtotal_re.search(line):
        if not time_match:
          outL()
          exit(f'timesheet error: subtotal line does not specify a time.')
        if start_minutes is None or end_minutes is None:
          outL()
          exit(f'timesheet error: subtotal line has invalid time: {subtotal_match[0]!r}')
        sub_minutes = end_minutes - start_minutes
        m = minutes_for(subtotal_match)
        outZ(f' = {sub_minutes:4}m')
        if m != sub_minutes:
          outZ(f' *** found: {m}; calculated: {sub_minutes}')
          valid = False
        if sub_minutes <= 0:
          outL()
          exit(f'timesheet error: subtototal is negative')

        start_minutes = None
        prev_minutes = None
        end_minutes = None

    if money_match := money_re.match(line):
      s = ''.join(money_match.groups())
      i = float(s)
      if (i < 0):
        total_payment += i
      else:
        total_expense += i
      outZ(f'               {i: 10,.2f}')

    outL()

  outL()
  outL(f'DAYS:')
  for day in days: outL(day.desc_with_rates(hourly_rates))

  rate_blocks = fan_by_key_fn(all_blocks, lambda b: b.rate)
  total_hours = { r : sum(b.hours for b in blocks) for r, blocks in rate_blocks.items() }

  outL()
  outL(f'Total hours:')
  for r, h in sorted(total_hours.items()):
    outL(f'  {h:.02f} @ ${r}/hr = ${h * r:,.02f}')

  time_expense = sum(day.price for day in days)
  total = time_expense + total_payment + total_expense

  outL(f'Total expenses: ${total_expense:,.2f}')
  outL(f'Total payments: ${total_payment:,.2f}')
  outL(f'TOTAL:         ${total:,.2f}')

  if not valid:
    exit('*** INVALID ***')


def minutes_for(match:Match) -> int:
  return int(match.group(1)) * 60 + int(match.group(2))

day_re      = re.compile(r'(?:(\d\d\d\d)-)?(\d\d)-(\d\d)')
time_re     = re.compile(r'(\d\d):(\d\d) ')
subtotal_re = re.compile(r'= (\d{1,2}):(\d\d)')
money_re    = re.compile(r'([+-]?)\s*\$(\d+)(\.?\d*)')
rate_idx_re = re.compile(r'\bR(\d+)\b')


@dataclass
class TimeBlock:
  start: int # In minutes from midnight.
  end: int # In minutes from midnight.
  minutes: int # In minutes.
  rate: int

  def __init__(self, start:int, end:int, rate:int):
    assert start < end
    self.start = start
    self.end = end
    self.minutes = end - start
    assert self.minutes > 0
    self.rate = rate

  @property
  def hours(self) -> float:
    return self.minutes / 60

  @property
  def price(self) -> float:
    return self.hours * self.rate


@dataclass
class Day:
  day:str
  blocks:list[TimeBlock]

  def __init__(self, day:str, blocks:list[TimeBlock]):
    self.day = day
    self.blocks = blocks

  @property
  def price(self) -> float:
    return sum(block.price for block in self.blocks)

  def rate_minutes(self, rates_count:int) -> list[int]:
    rate_blocks = fan_by_key_fn(self.blocks, lambda b: b.rate)
    return [sum(b.minutes for b in blocks) for r, blocks in sorted(rate_blocks.items())]

  def desc_with_rates(self, rates:list[int]) -> str:
    parts = []
    for rate, minutes in zip(rates, self.rate_minutes(len(rates))):
      h, m = divmod(minutes, 60)
      parts.append(f'{h:}:{m:02} @ {rate}/hr')
    return f'{self.day}:  ' + ', '.join(parts)



if __name__ == '__main__': main()
