#!/usr/bin/env python3

from utest import utest, utest_exc
from pithy.strings import *


utest(True, string_contains, '', '') # strange, but simply the behavior of string.find.
utest(True, string_contains, 'a', '')
utest(True, string_contains, 'a', 'a')
utest(False, string_contains, '', 'a')

utest('postmortem', clip_prefix, 'postpostmortem', 'post')
utest('postmortem', clip_prefix, 'postmortem', 'test', req=False)
utest_exc(ValueError('postmortem'), clip_prefix, 'postmortem', 'test')

utest('abcde', clip_suffix, 'abcdefg', 'fg')
utest('antemortem', clip_suffix, 'antemortem', 'test', req=False)
utest_exc(ValueError('antemortem'), clip_suffix, 'antemortem', 'test')
# What is the difference between this and clip definition wise, and why does it work like this

utest('nopetest', clip_first_prefix, 'yesnopetest', ['yes','nope'])
utest('yesnopetest', clip_first_prefix, 'yesnopetest', ['nope','wontfind'], req=False)
utest_exc(ValueError('yesnopetest'), clip_first_prefix, 'yesnopetest', ['nope','wontfind'])

utest('', plural_s, 1)
utest('s', plural_s, 9)

utest('abcde', clip_suffix, 'abcdefg', 'fg')
utest_exc(ValueError('antemortem'), clip_suffix, 'antemortem', 'test')

utest('999 s', format_byte_count_dec, 999, abbreviated=False) # Broken.
utest('123.00 B', format_byte_count_dec, 123, small_ints=False)
utest('1000.00 kB', format_byte_count_dec, 999999)
utest('1000.00 MB', format_byte_count_dec, 999999999)
utest('1000.00 GB', format_byte_count_dec, 999999999999)
utest('1000.00 TB', format_byte_count_dec, 999999999999999)
utest('100.000 PB', format_byte_count_dec,   99999999999999999, precision=3)
utest('100.00 EB', format_byte_count_dec,   99999999999999999999)
utest('100.00 ZB', format_byte_count_dec,   99999999999999999999999)
utest('100.00 YB', format_byte_count_dec,   99999999999999999999999999)

