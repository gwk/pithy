# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.sequence import dl_edit_distance
from utest import utest


utest(0, dl_edit_distance, '', '')
utest(1, dl_edit_distance, 'a', '')
utest(1, dl_edit_distance, '', 'a')
utest(1, dl_edit_distance, 'a', 'b')
utest(1, dl_edit_distance, 'a', 'ab')
utest(1, dl_edit_distance, 'ab', 'a')
utest(1, dl_edit_distance, 'ab', 'b')
utest(1, dl_edit_distance, 'ab', 'ba')
utest(2, dl_edit_distance, 'ab', 'cd')

utest(1, dl_edit_distance, 'abcd', 'acbd')
