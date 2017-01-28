#!/usr/bin/env python3

from utest import utest, utest_exc
from pithy.format import *

utest(re.compile(r'a\-(.*)\-(.*)\.txt'), format_to_re, 'a-{}-{n:{w}}.txt')

utest_exc(FormatError("error: <str>:1:1: invalid format character: '{'"),
  format_to_re, '{')

utest_exc(FormatError("PREFIX: <str>:1:1: invalid format character: '{'"),
  format_to_re, '{', error_prefix='PREFIX')

utest_exc(FormatError("PREFIX: PATH:1:1: invalid format character: '{'"),
  format_to_re, '{', error_prefix='PREFIX', path='PATH')
