# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pyrrhus.str_utils import repeat
from utest import utest, utest_exc


utest('', repeat, 'ab', 0)
utest('ababab', repeat, 'ab', 3)
utest('ab-ab', repeat, 'ab', 2, sep='-')
utest_exc(ValueError('count must be nonnegative'), repeat, 'ab', -1)
