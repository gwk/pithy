# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from zoneinfo import ZoneInfo as ZoneInfo

from pithy.tz import now_utc, parse_dt_naive, parse_dt_naive_utc, parse_dt_utc, TimeZoneError
from utest import utest, utest_exc


tz_et = ZoneInfo('US/Eastern')

_now_utc = now_utc()
_now_naive_utc = _now_utc.replace(tzinfo=None)
_now_et = _now_utc.astimezone(tz_et)

utest(_now_utc, parse_dt_utc, _now_utc.isoformat())
utest_exc(TimeZoneError, parse_dt_utc, _now_et.isoformat())

utest(_now_utc, parse_dt_naive_utc, _now_naive_utc.isoformat())
utest_exc(TimeZoneError, parse_dt_naive_utc, _now_utc.isoformat())

utest(_now_utc, parse_dt_naive_utc, _now_naive_utc.isoformat())
utest_exc(TimeZoneError, parse_dt_naive_utc, _now_utc.isoformat())
utest_exc(TimeZoneError, parse_dt_naive_utc, _now_et.isoformat())

utest(_now_naive_utc, parse_dt_naive, _now_naive_utc.isoformat())
utest_exc(TimeZoneError, parse_dt_naive, _now_utc.isoformat())
utest_exc(TimeZoneError, parse_dt_naive, _now_et.isoformat())
