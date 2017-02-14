#!/usr/bin/env python3

from utest import utest, utest_exc
from pithy.string_utils import *

utest('abc', render_template, 'a${y}c', y='b')

utest(True, string_contains, '', '') # strange, but simply the behavior of string.find.
utest(True, string_contains, 'a', '')
utest(True, string_contains, 'a', 'a')
utest(False, string_contains, '', 'a')

utest('-body', clip_prefix, 'prefix-body', 'prefix')
utest('prefix-body', clip_prefix, 'prefix-body', 'missing', req=False)
utest_exc(ValueError('prefix-body'), clip_prefix, 'prefix-body', 'missing')

utest('body-', clip_suffix, 'body-suffix', 'suffix')
utest('body-suffix', clip_suffix, 'body-suffix', 'Z', req=False)
utest_exc(ValueError('body-suffix'), clip_suffix, 'body-suffix', 'missing')

utest('-body', clip_first_prefix, 'prefix-body', ['miss0', 'prefix', 'miss1'])
utest('prefix-body', clip_first_prefix, 'prefix-body', ['miss0', 'miss1'], req=False)
utest_exc(ValueError('prefix-body'), clip_first_prefix, 'prefix-body', ['miss0', 'miss1'])


def iter_excluding_str_test(val):
  'iter_excluding_str returns an iterator, this is testable.'
  try: it = iter_excluding_str(val)
  except TypeError: return ('atom:', val)
  else: return ('collection:', *val)

utest(('atom:', 'string'), iter_excluding_str_test, 'string')
utest(('collection:', 1, 2, 3), iter_excluding_str_test, [1,2,3])


utest('-1 things',  pluralize, -1, 'thing')
utest('0 things',   pluralize,  0, 'thing')
utest('1 thing',    pluralize,  1, 'thing')
utest('2 things',   pluralize,  2, 'thing')
utest(' 0 oxen',    pluralize,  0, 'ox', 'oxen', spec=' ')
utest(' 1 ox',      pluralize,  1, 'ox', 'oxen', spec=' ')

utest('',     format_nonempty, '({})', '')
utest('(A)',  format_nonempty, '({})', 'A')

utest('',   prepend_to_nonempty,  '#', '')
utest('#1', prepend_to_nonempty,  '#', '1')

utest('',   append_to_nonempty, '', '')
utest('1:', append_to_nonempty, '1', ':')


format_byte_count_test_vals = [
  ('1 B',         '1 byte',             1),
  ('1.000 kB',    '1.000 kilobytes',    1000),
  ('1.000 MB',    '1.000 megabytes',    1000000),
  ('1.000 GB',    '1.000 gigabytes',    999999500),
  ('1.000 TB',    '1.000 terabytes',    999999500000),
  ('1.000 PB',    '1.000 petabytes',    999999500000000),
  ('1.000 EB',    '1.000 exabytes',     999999500000000000),
  ('1.000 ZB',    '1.000 zettabytes',   999999500000000000000),
  ('1.000 YB',    '1.000 yottabytes',   999999500000000000000000),
  ('999 B',       '999 bytes',          999),
  ('999.999 kB',  '999.999 kilobytes',  999999),
  ('999.999 MB',  '999.999 megabytes',  999999499),
  ('999.999 GB',  '999.999 gigabytes',  999999499999),
  ('999.999 TB',  '999.999 terabytes',  999999499999999),
  ('999.999 PB',  '999.999 petabytes',  999999499999999999),
  ('999.999 EB',  '999.999 exabytes',   999999499999999999999),
  ('999.999 ZB',  '999.999 zettabytes', 999999499999999999999999),
  ('999.999 YB',  '999.999 yottabytes', 999999499999999999999999999),
]

for (exp_abbr, exp_full, count) in format_byte_count_test_vals:
  utest(exp_abbr, format_byte_count, count)
  utest(exp_full, format_byte_count, count, abbr=False)

# pluralization special case for zero precision.
utest('1 kilobyte',  format_byte_count, 1499, prec=0, abbr=False)
utest('2 kilobytes', format_byte_count, 1500, prec=0, abbr=False)


utest((0, 0), line_col_0, '', 0)
utest((0, 0), line_col_0, 'a\nb\n', 0)
utest((0, 1), line_col_0, 'a\nb\n', 1)
utest((1, 0), line_col_0, 'a\nb\n', 2)
utest((1, 1), line_col_0, 'a\nb\n', 3)
utest((2, 0), line_col_0, 'a\nb\n', 4)

utest_exc(IndexError(-1), line_col_0, '', -1)
utest_exc(IndexError(1), line_col_0, '', 1)
utest_exc(IndexError(2), line_col_0, 'a', 2)

utest((1, 1), line_col_1, '', 0)
