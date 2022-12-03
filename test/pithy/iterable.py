#!/usr/bin/env python3

from utest import *
from pithy.iterable import *
from operator import eq


utest(True, is_sorted, [])
utest(True, is_sorted, [0])
utest(True, is_sorted, [0, 0])
utest(True, is_sorted, [0, 1])
utest(False, is_sorted, [1, 0])
utest(True, is_sorted, '')
utest(True, is_sorted, 'aabbcc')
utest(False, is_sorted, 'acb')

utest_exc(NoElements, first_el, [])
utest(0, first_el, [0])

utest_seq([], iter_from, [], 0)
utest_seq([], iter_from, [], 1)
utest_seq([0], iter_from, [0], 0)
utest_seq([1], iter_from, [0, 1], 1)

utest_seq([], closed_int_intervals, [])
utest_seq([(0,0), (2,3), (5,7)], closed_int_intervals, [0, 2,3, 5,6,7])

utest_seq([], int_tuple_ranges, [])
utest_seq([(0,1), (2,4), (5,9), (10,11)], int_tuple_ranges, [0, (2,4), range(5,7), (7,8), 8, 10])

utest_seq([-1, -3], filtermap_with_mapping, [0, 1, 2, 3], {1: -1, 3: -3})

utest([], fan_by_index_fn, [], index=int)
utest([[], [1]], fan_by_index_fn, [1], index=lambda el: el, min_len=2)
utest([[0, 1, 2]], fan_by_index_fn, range(3), index=lambda el: 0)

utest(([], []), fan_by_pred, [], pred=int)
utest(([0], [1, 2]), fan_by_pred, [0, 1, 2], pred=lambda el: el)

utest({}, fan_by_key_fn, [], key=int)
utest({False: [0], True: [1, 2]}, fan_by_key_fn, range(3), key=lambda el: bool(el))

utest_seq([], group_by_cmp, [], cmp=eq)
utest_seq([[0], [1, 1], [2]], group_by_cmp, (0, 1, 1, 2), cmp=eq)

utest_seq_exc(ValueError(0), group_by_heads, [0, 1, 2, 3, 4], is_head=lambda x: x % 2)

utest_seq([[1, 2], [3, 4]], group_by_heads, [0, 1, 2, 3, 4], is_head=lambda x: x % 2, headless=OnHeadless.drop)

utest_seq([[0], [1, 2], [3, 4]], group_by_heads, [0, 1, 2, 3, 4], is_head=lambda x: x % 2, headless=OnHeadless.keep)

utest({0, 1}, set_from, iter([(0,), (0, 1)]))

utest(frozenset({0, 1}), frozenset_from, iter([(0,), (0, 1)]))

F2 = Tuple[float, float]
def split_pair(pair:F2) -> Optional[Tuple[F2, F2]]:
  s, e = pair
  assert s <= e
  si = int(s)
  m = float(si + 1)
  if e <= m: return None
  return ((s, m), (m, e))


utest_seq([(0.0, 0.1), (0.9, 1.0), (1.9, 2.0), (2.0, 2.1), (2.9, 3.0), (3.0, 4.0), (4.0, 4.1)],
  split_els, [(0.0, 0.1), (0.9, 1.0), (1.9, 2.1), (2.9, 4.1)], split=split_pair)


def is_zero(i): return i == 0
def is_one(i): return i == 1

utest_seq([], split_by_preds, [], is_zero)
utest_seq([(False, [0, 0])], split_by_preds, [0, 0], is_zero, is_one)
utest_seq([(True, [0, 1])], split_by_preds, [0, 1], is_zero, is_one)

utest_seq([(False, [0]), (True, [0, 1]), (False, [0])],
  split_by_preds, [0, 0, 1, 0], is_zero, is_one)

utest_seq([], transpose, [])
utest_seq([], transpose, [[]])
utest_seq([[0, 1], [2, 3]], transpose, [[0, 2], [1, 3]])
utest_seq([[0, 1], [2, 3], [4, 5]], transpose, [[0, 2, 4], [1, 3, 5]])

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
