# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.timespans import convert_timespan, parse_timespan_as_seconds, timespan_suffixes
from utest import utest, utest_exc, utest_val


# timespan_suffixes is derived from the dict so the ordering matches.
utest_val(['ns', 'us', 'ms', 's', 'm', 'h', 'd', 'w', 'mo', 'y'], timespan_suffixes, 'timespan_suffixes')


# parse_timespan_as_seconds: each unit.
utest(1e-9,         parse_timespan_as_seconds, '1ns')
utest(1e-6,         parse_timespan_as_seconds, '1us')
utest(1e-3,         parse_timespan_as_seconds, '1ms')
utest(1.0,          parse_timespan_as_seconds, '1s')
utest(60.0,         parse_timespan_as_seconds, '1m')
utest(3600.0,       parse_timespan_as_seconds, '1h')
utest(86400.0,      parse_timespan_as_seconds, '1d')
utest(604800.0,     parse_timespan_as_seconds, '1w')
utest(2_592_000.0,  parse_timespan_as_seconds, '1mo')
utest(31_536_000.0, parse_timespan_as_seconds, '1y')

# Fractional values.
utest(0.5,    parse_timespan_as_seconds, '500ms')
utest(90.0,   parse_timespan_as_seconds, '1.5m')
utest(5400.0, parse_timespan_as_seconds, '1.5h')

# 's' suffix must not match inside 'ms', 'ns', or 'us'.
utest(1e-3, parse_timespan_as_seconds, '1ms')
utest(1e-9, parse_timespan_as_seconds, '1ns')

# Errors.
utest_exc(ValueError("invalid timespan (unrecognized suffix): 'abc'"), parse_timespan_as_seconds, 'abc')
utest_exc(ValueError("invalid timespan (unrecognized suffix): '1x'"),  parse_timespan_as_seconds, '1x')
utest_exc(ValueError("invalid timespan (unrecognized suffix): ''"),    parse_timespan_as_seconds, '')
utest_exc(ValueError("invalid timespan: 'nans'"),                      parse_timespan_as_seconds, 'nans')


# convert_timespan.
utest('60m',  convert_timespan, '1h',     to='m')
utest('1s',   convert_timespan, '1000ms', to='s')
utest('60h',  convert_timespan, '2.5d',   to='h')
utest('1h',   convert_timespan, '3600s',  to='h')
utest('0.5s', convert_timespan, '500ms',  to='s')
utest('1ms',  convert_timespan, '1ms',    to='ms')

# convert_timespan: invalid target suffix.
utest_exc(ValueError("invalid timespan suffix: 'x'"), convert_timespan, '1s', to='x')
