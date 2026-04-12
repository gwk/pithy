# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from tolkien import Source
from utest import utest, utest_exc


source = Source(name='empty', text='')
utest(0, source.get_line_index, 0)
utest_exc(IndexError(1), source.get_line_index, 1)

source = Source(name='one a', text='a')
utest(0, source.get_line_index, 0)
utest(0, source.get_line_index, 1)
utest_exc(IndexError(2), source.get_line_index, 2)

source = Source(name='one n', text='\n')
utest(0, source.get_line_index, 0)
utest(0, source.get_line_index, 1) # EOF after newline is a special case.
utest_exc(IndexError(2), source.get_line_index, 2)


source = Source(name='abcs', text='a\nb\nc\n')

for chr_idx, line_idx in enumerate([0, 0, 1, 1, 2, 2, 2]):
  utest(line_idx, source.get_line_index, chr_idx)
