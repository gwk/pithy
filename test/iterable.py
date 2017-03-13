#!/usr/bin/env python3

from utest import *
from operator import eq
from pithy.iterable import *


utest(True, is_sorted, [])
utest(True, is_sorted, [0])
utest(True, is_sorted, [0, 0])
utest(True, is_sorted, [0, 1])
utest(False, is_sorted, [1, 0])
utest(True, is_sorted, '')
utest(True, is_sorted, 'aabbcc')
utest(False, is_sorted, 'acb')

utest_exc(ValueError('empty iterable'), first_el, [])
utest(0, first_el, [0])

utest_seq([], iter_from, [], 0)
utest_seq([], iter_from, [], 1)
utest_seq([0], iter_from, [0], 0)
utest_seq([1], iter_from, [0, 1], 1)

utest_seq([], closed_int_intervals, [])
utest_seq([(0,0), (2,3), (5,7)], closed_int_intervals, [0, 2,3, 5,6,7])

utest_seq([], int_tuple_ranges, [])
utest_seq([(0,1), (2,4), (5,9), (10,11)], int_tuple_ranges, [0, (2,4), range(5,7), (7,8), 8, 10])

utest([], fan_by_index_fn, [], index=int)
utest([[], [1]], fan_by_index_fn, [1], index=lambda el: el, min_len=2)
utest([[0, 1, 2]], fan_by_index_fn, range(3), index=lambda el: 0)

utest(([], []), fan_by_pred, [], pred=int)
utest(([0], [1, 2]), fan_by_pred, [0, 1, 2], pred=lambda el: el)

utest({}, fan_by_key_fn, [], key=int)
utest({False: [0], True: [1, 2]}, fan_by_key_fn, range(3), key=lambda el: bool(el))

utest_seq([], group_sorted_by_cmp, [], cmp=eq)
utest_seq([[0], [1, 1], [2]], group_sorted_by_cmp, (0, 1, 1, 2), cmp=eq)

utest_seq_exc(ValueError(0), group_by_heads, [0, 1, 2, 3, 4], is_head=lambda x: x % 2)

utest_seq([[1, 2], [3, 4]], group_by_heads, [0, 1, 2, 3, 4], is_head=lambda x: x % 2, headless=OnHeadless.drop)

utest_seq([[0], [1, 2], [3, 4]], group_by_heads, [0, 1, 2, 3, 4], is_head=lambda x: x % 2, headless=OnHeadless.keep)

utest_seq([], window_iter, [])
utest_seq([(0,1), (1,2), (2,3)], window_iter, range(4))
utest_seq([(0,1,2), (1,2,3)], window_iter, range(4), width=3)
utest_seq([('a','b'), ('b','c')], window_iter, 'abc')

utest_seq([], window_pairs, [])
utest_seq([(0,None)], window_pairs, [0])
utest_seq([(0,1), (1,2), (2,None)], window_pairs, range(3))
utest_seq([(0,1), (1,2), (2,-1)], window_pairs, range(3), tail=-1)
utest_seq([('a','b'), ('b','c'), ('c','_')], window_pairs, 'abc', tail='_')

utest({}, prefix_tree, [])
utest({None:None}, prefix_tree, [''])
utest({'a':{None:None}}, prefix_tree, ['a'])
utest({None:None, 'a':{None:None, 'b':{None:None}}}, prefix_tree, ['', 'a', 'ab'])
utest({'a':{'b':{None:None}, 'c':{None:None}}}, prefix_tree, ['ab', 'ac'])
