# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Availability within a local wall-clock day, represented by normalized five-minute intervals.

Intervals are half-open. Slot boundaries run from 0 through 288; 288 is the following midnight.
This module does not resolve dates, time zones, recurrence, or daylight-saving transitions.
Callers must resolve those separately when turning a wall-clock schedule into actual appointments.
'''

from dataclasses import dataclass
from datetime import time
from typing import Iterable, Iterator


_context_keywords_ = ['availability', 'booking', 'calendar', 'interval subtraction', 'scheduling', 'time slots']

slot_minutes = 5
day_minutes = 1440
day_slots = day_minutes // slot_minutes


@dataclass(frozen=True, init=False)
class DaySlots:
  '''An immutable union of five-minute slots, sorted and merged into disjoint, nonadjacent intervals.'''

  ranges:tuple[tuple[int,int],...]

  def __init__(self, ranges:Iterable[tuple[int,int]]=()) -> None:
    normalized:list[tuple[int,int]] = []
    for start, end in sorted(ranges):
      if type(start) is not int or type(end) is not int or not 0 <= start <= end <= day_slots:
        raise ValueError(f'Invalid slot interval: {(start, end)!r}.')
      if start == end: continue
      if normalized and start <= normalized[-1][1]:
        normalized[-1] = (normalized[-1][0], max(end, normalized[-1][1]))
      else:
        normalized.append((start, end))
    object.__setattr__(self, 'ranges', tuple(normalized))


  @classmethod
  def from_minutes(cls, ranges:Iterable[tuple[int,int]]) -> DaySlots:
    'Construct from minute-of-day boundaries. Reject boundaries not divisible by five; do not round.'
    return cls((slot_for_minute(start), slot_for_minute(end)) for start, end in ranges)


  @property
  def minute_ranges(self) -> tuple[tuple[int,int],...]:
    return tuple((start * slot_minutes, end * slot_minutes) for start, end in self.ranges)


  @property
  def total_minutes(self) -> int:
    return sum(end - start for start, end in self.ranges) * slot_minutes


  def __bool__(self) -> bool:
    return bool(self.ranges)


  def __iter__(self) -> Iterator[int]:
    'Iterate over the occupied slot indices.'
    for start, end in self.ranges:
      yield from range(start, end)


  def __or__(self, other:DaySlots) -> DaySlots:
    return DaySlots((*self.ranges, *other.ranges))


  def __and__(self, other:DaySlots) -> DaySlots:
    ranges = []
    i = j = 0
    while i < len(self.ranges) and j < len(other.ranges):
      a, b = self.ranges[i]
      c, d = other.ranges[j]
      start, end = max(a, c), min(b, d)
      if start < end: ranges.append((start, end))
      if b <= d: i += 1
      else: j += 1
    return DaySlots(ranges)


  def __sub__(self, other:DaySlots) -> DaySlots:
    ranges = []
    j = 0
    for start, end in self.ranges:
      while j < len(other.ranges) and other.ranges[j][1] <= start:
        j += 1
      while j < len(other.ranges) and other.ranges[j][0] < end:
        busy_start, busy_end = other.ranges[j]
        if start < busy_start: ranges.append((start, busy_start))
        start = max(start, busy_end)
        if start >= end: break
        j += 1
      if start < end: ranges.append((start, end))
    return DaySlots(ranges)


  def contains_minutes(self, start:int, end:int) -> bool:
    'Return whether the whole interval is contained. An empty interval is contained in every set.'
    interval = DaySlots.from_minutes(((start, end),))
    return not (interval - self)


  def start_minutes(self, *, duration_minutes:int, step_minutes:int=slot_minutes) -> list[int]:
    '''
    Return starts that fit the entire duration, with cadence anchored to midnight.

    Duration and cadence must be positive multiples of five. Durations longer than a day yield no starts.
    '''
    for name, value in (('duration_minutes', duration_minutes), ('step_minutes', step_minutes)):
      if type(value) is not int or value <= 0 or value % slot_minutes:
        raise ValueError(f'{name} must be a positive multiple of {slot_minutes}: {value!r}.')
    starts:list[int] = []
    for start, end in self.minute_ranges:
      first = (start + step_minutes - 1) // step_minutes * step_minutes
      starts.extend(range(first, end - duration_minutes + 1, step_minutes))
    return starts


def slot_for_minute(minute:int) -> int:
  'Convert a five-minute-aligned day boundary, including 1440, to a slot boundary.'
  if type(minute) is not int or not 0 <= minute <= day_minutes or minute % slot_minutes:
    raise ValueError(f'Invalid five-minute day boundary: {minute!r}.')
  return minute // slot_minutes


def minute_for_time(value:time) -> int:
  'Convert a naive, five-minute-aligned time to minutes from midnight, rejecting sub-minute precision.'
  if value.tzinfo is not None or value.second or value.microsecond or value.minute % slot_minutes:
    raise ValueError(f'Expected a naive, five-minute-aligned time without seconds or microseconds: {value!r}.')
  return value.hour * 60 + value.minute
