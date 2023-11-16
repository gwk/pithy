# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from itertools import permutations

from pithy.string import (append_to_nonempty, clip_common, clip_first_prefix, clip_prefix, clip_suffix, format_byte_count,
  format_nonempty, iter_excluding_str, line_col_0, line_col_1, pluralize, prepend_to_nonempty, render_template, split_camelcase,
  str_tree, str_tree_insert, str_tree_iter)
from utest import utest, utest_exc, utest_seq


utest('abc', render_template, 'a${y}c', y='b')

# Clip functions.

utest('-body', clip_prefix, 'prefix-body', 'prefix')
utest('prefix-body', clip_prefix, 'prefix-body', 'missing', req=False)
utest('body', clip_prefix, 'body', '')
utest_exc(ValueError('prefix-body'), clip_prefix, 'prefix-body', 'missing')

utest('body-', clip_suffix, 'body-suffix', 'suffix')
utest('body-suffix', clip_suffix, 'body-suffix', 'Z', req=False)
utest('body', clip_suffix, 'body', '')
utest_exc(ValueError('body-suffix'), clip_suffix, 'body-suffix', 'missing')

utest('-body', clip_first_prefix, 'prefix-body', ['miss0', 'prefix', 'miss1'])
utest('prefix-body', clip_first_prefix, 'prefix-body', ['miss0', 'miss1'], req=False)
utest_exc(ValueError('prefix-body'), clip_first_prefix, 'prefix-body', ['miss0', 'miss1'])

utest((), clip_common, [])
utest(('', 'a', 'ab', 'b'), clip_common, ['1289', '12a89', '12ab89', '12b89'])


utest_exc(TypeError('iter_excluding_str explictly treats str as non-iterable type'), iter_excluding_str, 'string')
utest_seq([1, 2, 3], iter_excluding_str, [1,2,3])

utest('-1 things',  pluralize, -1, 'thing')
utest('0 things',   pluralize,  0, 'thing')
utest('1 thing',    pluralize,  1, 'thing')
utest('2 things',   pluralize,  2, 'thing')
utest(' 0 oxen',    pluralize,  0, 'ox', 'oxen', spec=' ')
utest(' 1 ox',      pluralize,  1, 'ox', 'oxen', spec=' ')

utest('',     format_nonempty, '({})', '')
utest('(A)',  format_nonempty, '({})', 'A')

utest('',   prepend_to_nonempty,  '#', '')
utest('#1', prepend_to_nonempty,  '#', '1')

utest('',   append_to_nonempty, '', '')
utest('1:', append_to_nonempty, '1', ':')


format_byte_count_test_vals = [
  ('1 B',         '1 byte',             1),
  ('1.000 kB',    '1.000 kilobytes',    1000),
  ('1.000 MB',    '1.000 megabytes',    1000000),
  ('1.000 GB',    '1.000 gigabytes',    999999500),
  ('1.000 TB',    '1.000 terabytes',    999999500000),
  ('1.000 PB',    '1.000 petabytes',    999999500000000),
  ('1.000 EB',    '1.000 exabytes',     999999500000000000),
  ('1.000 ZB',    '1.000 zettabytes',   999999500000000000000),
  ('1.000 YB',    '1.000 yottabytes',   999999500000000000000000),
  ('999 B',       '999 bytes',          999),
  ('999.999 kB',  '999.999 kilobytes',  999999),
  ('999.999 MB',  '999.999 megabytes',  999999499),
  ('999.999 GB',  '999.999 gigabytes',  999999499999),
  ('999.999 TB',  '999.999 terabytes',  999999499999999),
  ('999.999 PB',  '999.999 petabytes',  999999499999999999),
  ('999.999 EB',  '999.999 exabytes',   999999499999999999999),
  ('999.999 ZB',  '999.999 zettabytes', 999999499999999999999999),
  ('999.999 YB',  '999.999 yottabytes', 999999499999999999999999999),
]

for (exp_abbr, exp_full, count) in format_byte_count_test_vals:
  utest(exp_abbr, format_byte_count, count)
  utest(exp_full, format_byte_count, count, abbr=False)

# pluralization special case for zero precision.
utest('1 kilobyte',  format_byte_count, 1499, prec=0, abbr=False)
utest('2 kilobytes', format_byte_count, 1500, prec=0, abbr=False)


utest((0, 0), line_col_0, '', 0)
utest((0, 0), line_col_0, 'a\nb\n', 0)
utest((0, 1), line_col_0, 'a\nb\n', 1)
utest((1, 0), line_col_0, 'a\nb\n', 2)
utest((1, 1), line_col_0, 'a\nb\n', 3)
utest((2, 0), line_col_0, 'a\nb\n', 4)

utest_exc(IndexError(-1), line_col_0, '', -1)
utest_exc(IndexError(1), line_col_0, '', 1)
utest_exc(IndexError(2), line_col_0, 'a', 2)

utest((1, 1), line_col_1, '', 0)


# split_camelcase.

utest([], split_camelcase, '')
utest(['a'], split_camelcase, 'a')
utest(['a', 'B'], split_camelcase, 'aB')
utest(['a', 'Bc'], split_camelcase, 'aBc')
utest(['a', 'BC'], split_camelcase, 'aBC')
utest(['AB'], split_camelcase, 'AB')
utest(['A', 'Bc'], split_camelcase, 'ABc')
utest(['ABC'], split_camelcase, 'ABC')
utest(['AB', 'Cd'], split_camelcase, 'ABCd')

utest(['A1B2'], split_camelcase, 'A1B2')


# str_tree.

str_tree_tests:list[tuple[list[str],dict[str,str|dict|None]]] = [
  ([], {}),
  ([''], {'':None}),
  (['a'], {'a':None}),
  (['', 'a'], {'':None, 'a':None}),
  (['', 'a', 'aa'], {'':None, 'a':{'':None, 'a':None}}),
  (['', 'a', 'aa', 'ab'], {'':None, 'a':{'':None, 'a':None, 'b':None}}),
  (['', 'a', 'aa', 'ab', 'abc'], {'':None, 'a':{'':None, 'a':None, 'b':{'c':None, '':None}}}),
]

for (strs, tree) in str_tree_tests:
  utest_seq(strs, str_tree_iter, tree, _sort=True)
  for p in permutations(strs):
    utest(tree, str_tree, p)
