#!/usr/bin/env python3

from utest import utest, utest_exc
from pithy.strings import *


utest(True, string_contains, '', '') # strange, but simply the behavior of string.find.
utest(True, string_contains, 'a', '')
utest(True, string_contains, 'a', 'a')
utest(False, string_contains, '', 'a')

utest('-rest', clip_prefix, 'prefix-rest', 'prefix')
utest('prefix-rest', clip_prefix, 'prefix-rest', 'notpresent', req=False)
utest_exc(ValueError('prefix-rest'), clip_prefix, 'prefix-rest', 'notpresent')

utest('rest-', clip_suffix, 'rest-suffix', 'suffix')
utest('rest-suffix', clip_suffix, 'rest-suffix', 'notpresent', req=False)
utest_exc(ValueError('rest-suffix'), clip_suffix, 'rest-suffix', 'notpresent')
# What is the difference between this and clip definition wise, and why does it work like this

utest('-rest', clip_first_prefix, 'firstprefix-rest', ['firstprefix','first'])
utest('firstprefix-rest', clip_first_prefix, 'firstprefix-rest', ['notpresent','notpresenteither'], req=False)
utest_exc(ValueError('firstprefix-rest'), clip_first_prefix, 'firstprefix-rest', ['notpresent','notpresenteither'])

utest('', plural_s, 1)
utest('s', plural_s, 9)

utest('rest-', clip_suffix, 'rest-suffix', 'suffix')
utest_exc(ValueError('rest-suffix'), clip_suffix, 'rest-suffix', 'notpresent')

format_test_vals = [
  ('999 B', '999 bytes', '999.0000 B', '999.00 B', 999),
  ('1000.00 kB', '1000.00 kilobytes', '999.9990 kB', '1000.00 kB',  999999),
  ('1000.00 MB', '1000.00 megabytes', '1000.0000 MB', '1000.00 MB', 999999999),
  ('1000.00 GB', '1000.00 gigabytes', '1000.0000 GB', '1000.00 GB', 999999999999),
  ('1000.00 TB', '1000.00 terabytes', '1000.0000 TB', '1000.00 TB', 999999999999999),
  ('100.00 PB', '100.00 petabytes', '100.0000 PB', '100.00 PB',     99999999999999999),
  ('100.00 EB', '100.00 exabytes', '100.0000 EB', '100.00 EB',      99999999999999999999),
  ('100.00 ZB', '100.00 zettabytes', '100.0000 ZB', '100.00 ZB',    99999999999999999999999),
  ('100.00 YB', '100.00 yottabytes', '100.0000 YB', '100.00 YB',    99999999999999999999999999)
]

for (exp_abbrev, exp_non_abbrev, exp_precision, exp_small_ints, test_count) in format_test_vals:
  utest(exp_abbrev, format_byte_count_dec, test_count)
  utest(exp_precision, format_byte_count_dec, test_count, precision=4, small_ints=False)
  utest(exp_non_abbrev, format_byte_count_dec, test_count, abbreviated=False)
  utest(exp_small_ints, format_byte_count_dec, test_count, small_ints=False)

def iter_excluding_str_test(val):
  'iter_excluding_str returns an iterator, this is testable.'
  try: it = iter_excluding_str(val)
  except TypeError: return ('atom:', val)
  else: return ('collection:', *val)

utest(('atom:', 'string'), iter_excluding_str_test, 'string')
utest(('collection:', 1, 2, 3), iter_excluding_str_test, [1,2,3])

