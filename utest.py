'''
utest is a tiny unit testing library.

Set the UTEST_SHOW_EXC environment variable to truthful to print unexpected exception tracebacks.
'''


import atexit as _atexit
import inspect as _inspect
from os.path import basename as _basename
from sys import stderr as _stderr
from traceback import print_exception as _print_exception


__all__ = [
  'utest',
  'utest_exc',
  'utest_seq',
  'utest_seq_exc',
  'utest_val',
  'usymmetric',
]


_utest_test_count = 0
_utest_failure_count = 0


def utest(exp, fn, *args, _utest_depth=0, **kwargs):
  '''
  Invoke `fn` with `args` and `kwargs`.
  Log a test failure if an exception is raised or the returned value does not equal `exp`.
  '''
  global _utest_test_count
  _utest_test_count += 1
  try: ret = fn(*args, **kwargs)
  except BaseException as exc:
    _utest_failure(_utest_depth, exp_label='value', exp=exp, exc=exc, subj=fn, args=args, kwargs=kwargs)
  else:
    if exp != ret:
      _utest_failure(_utest_depth, exp_label='value', exp=exp, ret_label='value', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_exc(exp_exc, fn, *args, _utest_depth=0, **kwargs):
  '''
  Invoke `fn` with `args` and `kwargs`.
  Log a test failure if an exception is not raised or if the raised exception type and args not match `exp_exc`.
  '''
  global _utest_test_count
  _utest_test_count += 1
  try: ret = fn(*args, **kwargs)
  except BaseException as exc:
    if not _compare_exceptions(exp_exc, exc):
      _utest_failure(_utest_depth, exp_label='exception', exp=exp_exc, exc=exc, subj=fn, args=args, kwargs=kwargs)
  else:
    _utest_failure(_utest_depth, exp_label='exception', exp=exp_exc, ret_label='value', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_seq(exp_seq, fn, *args, _utest_depth=0, **kwargs):
  '''
  Invoke `fn` with `args` and `kwargs`, and convert the resulting iterable into a sequence.
  Log a test failure if an exception is raised,
  or if any items of the returned seqence do not equal the items of `exp`.
  '''
  global _utest_test_count
  _utest_test_count += 1
  exp = list(exp_seq) # convert to a list for referential isolation and consistent string repr.
  try:
    ret_seq = fn(*args, **kwargs)
  except BaseException as exc:
    _utest_failure(_utest_depth, exp_label='sequence', exp=exp, exc=exc, subj=fn, args=args, kwargs=kwargs)
    return
  try:
    ret = list(ret_seq)
  except BaseException as exc:
    _utest_failure(_utest_depth, exp_label='sequence', exp=exp, ret_label='value', ret=ret_seq, exc=exc, subj=fn, args=args, kwargs=kwargs)
    return
  if exp != ret:
    _utest_failure(_utest_depth, exp_label='sequence', exp=exp, ret_label='sequence', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_seq_exc(exp_exc, fn, *args, _utest_depth=0, **kwargs):
  '''
  Invoke `fn` with `args` and `kwargs`, and convert the resulting iterable into a sequence.
  Log a test failure if an exception is not raised or if the raised exception type and args not match `exp_exc`.
  '''
  global _utest_test_count
  _utest_test_count += 1
  try:
    ret_seq = fn(*args, **kwargs)
    ret = list(ret_seq)
  except BaseException as exc:
    if not _compare_exceptions(exp_exc, exc):
      _utest_failure(_utest_depth, exp_label='exception', exp=exp_exc, exc=exc, subj=fn, args=args, kwargs=kwargs)
  else:
    _utest_failure(_utest_depth, exp_label='exception', exp=exp_exc, ret_label='sequence', ret=ret, subj=fn, args=args, kwargs=kwargs)



def utest_val(exp_val, act_val, desc='<value>'):
  '''
  Log a test failure if `exp_val` does not equal `act_val`.
  Describe the test with the optional `desc`.
  '''
  global _utest_test_count
  _utest_test_count += 1
  if exp_val != act_val:
    _utest_failure(depth=0, exp_label='value', exp=exp_val, ret_label='value', ret=act_val, subj=repr(desc))


def usymmetric(test_fn, exp, fn, *args, _utest_depth=0, **kwargs):
  '''
  Apply `test_fn` to the provided arguments,
  then again to the same arguments but with the last two positional parameters swapped.
  '''
  head = args[:-2]
  argA, argB = args[-2:]
  args_swapped = head + (argB, argA)
  test_fn(exp, fn, *args, _utest_depth=_utest_depth+1, **kwargs)
  test_fn(exp, fn, *args_swapped, _utest_depth=_utest_depth+1, **kwargs)


def _utest_failure(depth, exp_label, exp, ret_label=None, ret=None, exc=None, subj=None, args=(), kwargs={}):
  global _utest_failure_count
  assert subj is not None
  _utest_failure_count += 1
  frame_record = _inspect.stack()[2 + depth] # caller of caller.
  frame = frame_record[0]
  info = _inspect.getframeinfo(frame)
  try: name = subj.__qualname__
  except AttributeError: name = str(subj)
  _errL(f'{_basename(info.filename)}:{info.lineno}: utest failure: {name}')
  for i, el in enumerate(args):
    _errL(f'  arg {i} = {el!r}')
  for name, val, in kwargs.items():
    _errL(f'  arg {name} = {val!r}')
  _errL(f'  expected {exp_label}: {exp!r}')
  if ret_label: # unexpected value.
    _errL(f'  returned {ret_label}: {ret!r}')
  if exc is not None: # unexpected exception.
    _errL(f'  raised exception:   {exc!r}')
    for i, arg in enumerate(exc.args):
      _errL(f'    exc arg {i}: {arg!r}')
    _print_exception(etype=type(exc), value=exc, tb=exc.__traceback__, file=_stderr)
  _errL()


def _compare_exceptions(exp, act):
  '''
  Compare two exceptions for approximate value equality.
  Since Python exceptions do not implement value equality, we offer several methods of comparison:
  * if `exp` is a string, then compare it to the repr of `act`.
  * if `exp` is a type, then test if `act` is an instance of `exp`.
  * otherwise, compare the types and args of `act` (which must be an exception instance) to `exp`.
  '''
  if isinstance(exp, str): return exp == repr(act)
  if isinstance(exp, type): return isinstance(act, exp)
  return type(exp) == type(act) and exp.args == act.args


def _errL(*items): print(*items, sep='', file=_stderr)


@_atexit.register
def report(): #!cov-ignore - the call to _exit kills coven before it records anything.
  'At process exit, if any test failures occured, print a summary message and force process to exit with status code 1.'
  from os import _exit
  if _utest_failure_count > 0:
    _errL(f'\nutest ran: {_utest_test_count}; failed: {_utest_failure_count}')
    _stderr.flush()
    _exit(1) # raising SystemExit has no effect in an atexit handler as of 3.5.2.

