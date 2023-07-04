#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.env import parse_env_lines
from utest import utest, utest_seq, utest_seq_exc


utest_seq([], parse_env_lines, 'test', [])
utest_seq([('a', '1'), ('b', '2')], parse_env_lines, 'test', ['#\n', 'a=1 # Comment.\n', 'export b=2\n'])

utest_seq_exc(ValueError, parse_env_lines, 'test', ['a = 1\n'])
utest_seq_exc(ValueError, parse_env_lines, 'test', ['a= 1\n'])
utest_seq_exc(ValueError, parse_env_lines, 'test', ['a =1\n'])
