#!/usr/bin/env python3

from utest import *
from pithy.format import *

utest(False, has_formatter, '')
utest(False, has_formatter, 'a')
utest(False, has_formatter, '{{}}')
utest(False, has_formatter, '{')
utest(False, has_formatter, '}')
utest(True, has_formatter, '{}')
utest(True, has_formatter, 'a {i!r:2d}')

utest(0, count_formatters, 'a b')
utest(2, count_formatters, 'a {i} b {} c')

utest_seq([('', None, None), ('a', 'r', '2d')], parse_formatters, '{} {a!r:2d}')

utest(re.compile(r'a\-(.*)\-(.*)\.txt'), format_to_re, 'a-{}-{n:{w}}.txt')

utest(re.compile(r'(\d+)'), format_to_re, '{:d}')


utest_exc(FormatError("error: <str>:1:1: invalid format character: '{'"),
  format_to_re, '{')

utest_exc(FormatError("PREFIX: <str>:1:1: invalid format character: '{'"),
  format_to_re, '{', error_prefix='PREFIX')

utest_exc(FormatError("PREFIX: PATH:1:1: invalid format character: '{'"),
  format_to_re, '{', error_prefix='PREFIX', path='PATH')
