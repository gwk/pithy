#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# total hours in a timesheet.

# format is:

# 12:00 begin
# 18:30 change tasks
# 24:00 end = 12:00

import os
import re
from argparse import ArgumentParser
from pithy.io import *


def main():
  parser = ArgumentParser(description='Validate timesheets.')
  parser.add_argument('timesheet', nargs='?', default='timesheet.txt')
  parser.add_argument('-rate', type=int, default=0)
  args = parser.parse_args()

  path = args.timesheet
  hourly_rate = args.rate


  start_minutes = None
  end_minutes   = None
  total_minutes = 0
  total_payment = 0
  total_expense = 0

  valid = True

  try: f = open(path)
  except FileNotFoundError: exit(f'bad path: {path}')

  for line in f:
    l = line.rstrip('\n')
    outZ(f'{l:64}')
    time_match = time_re.match(line)

    if time_match:
      m = minutes(time_match)
      if start_minutes is None: start_minutes = m
      else: end_minutes = m
      outZ(f'|{m:4} ')

    subtotal_match = subtotal_re.search(line)

    if subtotal_match:
      if start_minutes is None or end_minutes is None:
        outL()
        exit(f'ERROR: subtotal line has invalid time.')
      sub_minutes = end_minutes - start_minutes
      total_minutes += sub_minutes
      start_minutes = None
      end_minutes = None
      m = minutes(subtotal_match)
      outZ(f'= {sub_minutes:4}m')
      if m != sub_minutes:
        outZ(f' *** found: {m}; calculated: {sub_minutes}')
        valid = False

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


  hours = total_minutes // 60
  rem_minutes = int(total_minutes) % 60
  time_expense = hourly_rate * total_minutes / 60
  total = time_expense + total_payment + total_expense
  if hourly_rate:
    hourly_string = ' @ {:0.2f}/hr = ${:,.2f}'.format(hourly_rate, time_expense)
  else:
    hourly_string = ''

  outL()
  outL(f'TOTAL HOURS:   {hours:2}:{rem_minutes:02}{hourly_string}')
  outL(f'TOTAL EXPENSE: ${total_expense:,.2f}')
  outL(f'TOTAL PAYMENT: ${total_payment:,.2f}')
  outL(f'TOTAL:         ${total:,.2f}')

  if not valid:
    outL('*** INVALID ***')


def minutes(match):
  return int(match.group(1)) * 60 + int(match.group(2))


time_re     = re.compile(r'(\d{2}):(\d{2}) ')
subtotal_re = re.compile(r'= (\d{1,2}):(\d{2})')
money_re    = re.compile(r'([+-])\s*\$(\d+)(\.?\d*)')


if __name__ == '__main__': main()
