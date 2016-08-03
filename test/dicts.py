#!/usr/bin/env python3

from utest import utest, utest_exc
from pithy.dicts import *

def dict_put_test(d, k, v):
  dict_put(d, k, v)
  return d

utest({1:2}, dict_put_test, {}, 1,2)
utest_exc(KeyError(1), dict_put_test, {1:0}, 1,2)

def dict_append_test(d, k, v):
  dict_append(d, k, v)
  return d

utest({'k': [0]}, dict_append_test, {}, 'k', 0)
utest({'k': [0,1]}, dict_append_test, {'k':[0]}, 'k', 1)

def dict_extend_test(d, k, v):
  dict_extend(d, k, v)
  return d

utest({'k': []},dict_extend_test, {}, 'k', [])
utest({'k': [1]},dict_extend_test, {}, 'k', [1])
utest({'k': [0,1,2]}, dict_extend_test,{'k': [0]}, 'k', [1,2])

def dict_set_defaults_test(d, defaults):
  dict_set_defaults(d, defaults)
  return d

utest({'k': 0, 'l': 2}, dict_set_defaults_test, {'k': 0}, {'k': 1, 'l': 2})

def dict_filter_map_test(d, seq):
  return list(dict_filter_map(d, seq))

utest(['new-value'], dict_filter_map_test, {'find-this': 'new-value'}, ['dont-find-this', 'find-this', 'dont-find-this-either'])

def DefaultByKeyDict_test(dict, testkey):
  testdict = DefaultByKeyDict(dict)
  testdict[testkey]
  return testdict

utest({'testkey and value':'testkey and value'}, DefaultByKeyDict_test, lambda k: k, 'testkey and value')
