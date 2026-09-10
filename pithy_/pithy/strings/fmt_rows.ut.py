# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.strings import fmt_rows, fmt_tabbed_rows
from utest import utest_seq


utest_seq([], fmt_rows, [])

utest_seq(['1    22  ', '333  4444'], fmt_rows, [(1, 22), (333, 4444)])
utest_seq(['  1    22', '333  4444'], fmt_rows, [(1, 22), (333, 4444)], rjust=True)

# Widths limit padding; longer cell contents remain intact.
rows = [('a', 'b', 'c'), ('aaaa', 'bbbb', 'cccc')]
utest_seq(['a   b   c ', 'aaaa  bbbb  cccc'], fmt_rows, rows, max_col_width=2)
utest_seq(['a  b   c  ', 'aaaa  bbbb  cccc'], fmt_rows, rows, max_col_width=[1, 2, 3])
utest_seq(['a  b   c ', 'aaaa  bbbb  cccc'], fmt_rows, rows, max_col_width=[1, 2])
utest_seq(['a  b   c ', 'aaaa  bbbb  cccc'], fmt_rows, rows, max_col_width=iter([1, 2]))
utest_seq(['a  b   c  ', 'aaaa  bbbb  cccc'], fmt_rows, rows, max_col_width=[1, 2, 3, 4])
utest_seq(['a     b     c   ', 'aaaa  bbbb  cccc'], fmt_rows, rows, max_col_width=[])
utest_seq(['a' + ' ' * 65 + 'b', 'x' * 70 + '  c'], fmt_rows, [('a', 'b'), ('x' * 70, 'c')], max_col_width=[])
utest_seq(['a   b   c', 'aaaa  bbbb  cccc'], fmt_rows, rows, max_col_width=[1, 2], rjust=True)
utest_seq(['A  BB  CCC', 'a  b   c  '], fmt_rows, [('a', 'b', 'c')], head=['A', 'BB', 'CCC'], max_col_width=[1, 2, 3])
utest_seq(['A  BB'], fmt_rows, [], head=['A', 'BB'], max_col_width=[1])
utest_seq([], fmt_rows, [], max_col_width=[])
utest_seq(['a  b ', 'aaaa  bbbb'], fmt_tabbed_rows, ['a\tb', 'aaaa\tbbbb'], max_col_width=[1, 2])
