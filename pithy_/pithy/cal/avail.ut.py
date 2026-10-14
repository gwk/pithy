# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import FrozenInstanceError
from datetime import time, timezone
from random import Random

from pithy.cal.avail import DaySlots, minute_for_time, slot_for_minute
from utest import utest, utest_exc, utest_run, utest_val


utest(DaySlots(((1, 8),)), DaySlots, ((4, 6), (1, 3), (3, 4), (5, 8), (8, 8)))
utest(False, bool, DaySlots())
utest(True, bool, DaySlots(((0, 1),)))
utest(288, slot_for_minute, 1440)
utest(545, minute_for_time, time(9, 5))
for minute in (-5, 1, 1445, 5.0, True):
  utest_exc(ValueError, slot_for_minute, minute)
for value in (time(9, 1), time(9, 5, 1), time(9, 5, microsecond=1), time(9, tzinfo=timezone.utc)):
  utest_exc(ValueError, minute_for_time, value)
for ranges in (((-1, 1),), ((0, 289),), ((2, 1),), ((1.0, 2),)):
  utest_exc(ValueError, DaySlots, ranges)
utest_exc(FrozenInstanceError, setattr, DaySlots(), 'ranges', ((0, 1),))

available = DaySlots.from_minutes(((540, 720), (780, 1020)))
busy = DaySlots.from_minutes(((610, 655), (650, 675)))
utest_val(((540, 610), (675, 720), (780, 1020)), (available - busy).minute_ranges)
utest_val(355, (available - busy).total_minutes)
utest_val(busy, available & busy)
utest_val(available, available | busy)
utest_val(DaySlots(), available - available)
utest(True, available.contains_minutes, 540, 720)
utest(False, available.contains_minutes, 715, 785)
utest(True, DaySlots().contains_minutes, 1440, 1440)

short = DaySlots.from_minutes(((545, 600),))
utest([555, 570], short.start_minutes, duration_minutes=30, step_minutes=15)
utest([545, 550, 555, 560, 565, 570], short.start_minutes, duration_minutes=30)
utest([570], short.start_minutes, duration_minutes=30, step_minutes=30)
utest([], short.start_minutes, duration_minutes=60)
utest([0], DaySlots(((0, 288),)).start_minutes, duration_minutes=1440)
utest([], DaySlots(((0, 288),)).start_minutes, duration_minutes=1445)
utest([1435], DaySlots.from_minutes(((1435, 1440),)).start_minutes, duration_minutes=5)
for invalid in (0, -5, 1, 7, 5.0, True):
  utest_exc(ValueError, short.start_minutes, duration_minutes=invalid)
  utest_exc(ValueError, short.start_minutes, duration_minutes=5, step_minutes=invalid)


@utest_run
def test_against_slot_set_oracle() -> None:
  'Compare normalization, set operations, and candidate starts against independent discrete sets.'
  rng = Random(801)

  def rand_range() -> tuple[int,int]:
    x, y = rng.randrange(289), rng.randrange(289)
    return (min(x, y), max(x, y))

  for _ in range(300):
    raw_a = [rand_range() for _ in range(rng.randrange(8))]
    raw_b = [rand_range() for _ in range(rng.randrange(8))]
    a = DaySlots(raw_a)
    b = DaySlots(raw_b)
    sa = {i for s, e in raw_a for i in range(s, e)}
    sb = {i for s, e in raw_b for i in range(s, e)}
    utest_val(sa, set(a))
    utest_val(sa | sb, set(a | b))
    utest_val(sa & sb, set(a & b))
    utest_val(sa - sb, set(a - b))
    duration = rng.randrange(1, 30)
    step = rng.choice((1, 3, 6))
    expected = [s * 5 for s in range(0, 289-duration, step) if set(range(s, s+duration)) <= sa-sb]
    utest(expected, (a-b).start_minutes, duration_minutes=duration*5, step_minutes=step*5)
