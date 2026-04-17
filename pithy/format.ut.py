# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.format import *
from utest import utest, utest_exc, utest_seq


utest(False, has_formatter, '')
utest(False, has_formatter, 'a')
utest(False, has_formatter, '{{}}')
utest(True, has_formatter, '{}')
utest(True, has_formatter, 'a {i!r:2d}')

utest_exc(FormatError("<str>:1:1: invalid format character: '{'"), has_formatter, '{')
utest_exc(FormatError("<str>:1:1: invalid format character: '}'"), has_formatter, '}')

utest(0, count_formatters, 'a b')
utest(2, count_formatters, 'a {i} b {} c')

utest_seq([('', '', '', str), ('a', 'r', '2d', int)], parse_formatters, '{} {a!r:2d}')

utest('0 {i} {} J', format_partial, '{} {i} {} {j}', 0, j='J')

utest(re.compile(r'a\-(.+?)\-(?P<n>.+?)\.txt'), format_to_re, 'a-{}-{n:{w}}.txt')

utest(re.compile(r'(\d+)'), format_to_re, '{:d}')

utest_exc(FormatError("<str>:1:1: invalid format character: '{'"), format_to_re, '{x')

utest_exc(FormatError("<str>:2:1: invalid format character: '{'"), format_to_re, '{}\n{')
