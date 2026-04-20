# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from tolkien import Source
from utest import utest_seq


source = Source(name='empty', text='')
utest_seq([], source.line_texts)

source = Source(name='one a', text='a')
utest_seq(['a'], source.line_texts)

source = Source(name='one n', text='\n')
utest_seq(['\n'], source.line_texts)

source = Source(name='abcs', text='a\nb\nc\n')
utest_seq(['a\n', 'b\n', 'c\n'], source.line_texts)
