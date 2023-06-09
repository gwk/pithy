#!/usr/bin/env python3

import re

from pithy.filenamefmt import (count_fnf_str_formatters, FilenameFormatterError, fnf_str_has_formatter, format_fnf_str,
  regex_for_fnf_str)
from utest import utest, utest_exc, utest_seq


utest(False, fnf_str_has_formatter, '')
utest(False, fnf_str_has_formatter, 'a')
utest(False, fnf_str_has_formatter, '%%')
utest(True, fnf_str_has_formatter, '%s')

utest_exc(FilenameFormatterError("<str>:1:2: expected type char; received: ''"),
  fnf_str_has_formatter, '%')

utest(0, count_fnf_str_formatters, 'a b')
utest(2, count_fnf_str_formatters, 'a %s b %d c')

utest('0-a', format_fnf_str, '%d-%s', (0, 'a'))

utest('01', format_fnf_str, '%2d', (1,))

utest(re.compile(r'(.+)\-([0-9]+)\-([0-9]{2,})\.txt'),
  regex_for_fnf_str, '%s-%d-%2d.txt', allow_empty=False)

utest(re.compile(r'([0-9]+)'),
  regex_for_fnf_str, '%d', allow_empty=False)
