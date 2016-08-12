#!/usr/bin/env python3

from utest import utest, utest_exc
from pithy.dict_utils import *

utest({'k': 0}, dict_put, {}, 'k', 0)
utest_exc(KeyError('k'), dict_put, {'k': 0}, 'k', 1)

utest({'k': [0]}, dict_list_append, {}, 'k', 0)
utest({'k': [0, 1]}, dict_list_append, {'k': [0]}, 'k', 1)

utest({'k': []}, dict_list_extend, {}, 'k', [])
utest({'k': [0]}, dict_list_extend, {'k': []}, 'k', [0])
utest({'k': [0, 1, 2]}, dict_list_extend, {'k': [0]}, 'k', [1, 2])

utest({'k': 0, 'l': 2}, dict_set_defaults, {'k': 0}, {'k': 1, 'l': 2})

def dict_filter_map_test(d, seq):
  return list(dict_filter_map(d, seq))

utest([-1, -3], dict_filter_map_test, {1: -1, 3: -3}, [0, 1, 2, 3])

def DefaultByKeyDict_test(factory, test_keys):
  d = DefaultByKeyDict(factory)
  for k in test_keys:
    d[k]
  return d

utest({0: 0, 1: 1}, DefaultByKeyDict_test, lambda k: k, [0, 1])
