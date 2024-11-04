# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import meta_test_consumer
from meta_test_consumer import test_consumer
from meta_test_lib import test_caller_module_info
from pithy.meta import bindings_matching, caller_frame, caller_module_name, caller_src_loc, dispatcher_for_defs
from utest import utest, utest_val


binding_a = 'val_a'
binding_b = 'val_b'

def test_bindings_matching() -> None:
  utest([('a', binding_a), ('b', binding_b)], bindings_matching, prefix='binding_', val_type=str, frame='<module>')


def disp_a(s:str) -> str: return 'A: ' + s

def disp_b(s:str) -> str: return 'B: ' + s


disp = dispatcher_for_defs(prefix='disp_')

utest('A: x', disp, 'a', 'x')
utest('B: y', disp, 'b', 'y')


# Test caller_src_loc. Note that these tests are sensitive to source line numbers.

module_caller_src_loc = caller_src_loc(0)
utest_val((__file__, 30, '<module>'), module_caller_src_loc)


def test_caller_src_loc_reporter() -> tuple:
  '''This is a fake function that makes use of its caller's source location.'''
  return caller_src_loc(1)

test_caller_src_loc_reporter_res = test_caller_src_loc_reporter()

utest_val((__file__, 38, '<module>'), test_caller_src_loc_reporter_res)


# Test caller_module_spec.

test_consumer()
utest_val(1, len(test_caller_module_info))
test_caller_name, test_caller_spec = test_caller_module_info[0]
utest_val('meta_test_consumer', test_caller_name)
utest_val(meta_test_consumer.__file__, test_caller_spec.origin)
