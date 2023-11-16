# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.dict import (ConflictingValues, DefaultByKeyDict, dict_list_append, dict_list_extend, dict_put, dict_set_defaults,
  dict_update_sets, idemput, KeyExistingIncoming)
from utest import utest, utest_exc


utest({'k': 0}, dict_put, {}, 'k', 0)
utest_exc(KeyError('k'), dict_put, {'k': 0}, 'k', 1)

utest({'k': 0}, idemput, {}, 'k', 0)
utest({'k': 0}, idemput, {'k': 0}, 'k', 0)
utest_exc(ConflictingValues(KeyExistingIncoming(key='k', existing=0, incoming=1)), idemput, {'k': 0}, 'k', 1)


utest({'k': [0]}, dict_list_append, {}, 'k', 0)
utest({'k': [0, 1]}, dict_list_append, {'k': [0]}, 'k', 1)

utest({'k': []}, dict_list_extend, {}, 'k', [])
utest({'k': [0]}, dict_list_extend, {'k': []}, 'k', [0])
utest({'k': [0, 1, 2]}, dict_list_extend, {'k': [0]}, 'k', [1, 2])

utest({'k': 0, 'l': 2}, dict_set_defaults, {'k': 0}, {'k': 1, 'l': 2})
utest({'k': 0, 'l': 2}, dict_set_defaults, {'k': 0}, [('k', 1), ('l', 2)])

utest({'k': {1}}, dict_update_sets, {}, {'k':{1}})
utest({'k': {1}}, dict_update_sets, {}, [('k',{1})])

utest({'k': {1, 2}}, dict_update_sets, {'k':{1}}, {'k':{2}})


def DefaultByKeyDict_test(factory, test_keys):
  d = DefaultByKeyDict(factory)
  for k in test_keys:
    d[k]
  return d

utest({0: 0, 1: 1}, DefaultByKeyDict_test, lambda k: k, test_keys=[0, 1])
