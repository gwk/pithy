#!/usr/bin/env python3

from utest import utest, utest_exc
from pithy.strings import *


utest(True, string_contains, '', '') # strange, but simply the behavior of string.find.
utest(True, string_contains, 'a', '')
utest(True, string_contains, 'a', 'a')
utest(False, string_contains, '', 'a')
