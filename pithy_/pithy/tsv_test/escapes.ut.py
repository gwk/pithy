# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.tsv import esc_tsv, parse_tsv, render_tsv
from utest import utest, utest_seq


utest('a\tb\tc\n1\t2\t3\n', render_tsv, [['a','b','c'], ['1','2','3']])

utest_seq([['a','b','c'], ['1','2','3']], parse_tsv, 'a\tb\tc\n1\t2\t3\n')
utest_seq([['a','b','c'], ['1','2','3']], parse_tsv, ['a\tb\tc\n', '1\t2\t3\n'])
utest_seq([['1','2','3']], parse_tsv, 'a\tb\tc\n1\t2\t3\n', has_header=True)

utest('abc', esc_tsv, 'abc')
utest('␀ ␉ ␊ ␋ ␌ ␍ ␡', esc_tsv, '\0 \t \n \x0b \x0c \r \x7f')

utest_seq([['␀ ␉ ␊ ␋ ␌ ␍ ␡']], parse_tsv, '␀ ␉ ␊ ␋ ␌ ␍ ␡\n')
