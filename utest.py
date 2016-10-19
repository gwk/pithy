'''
utest is a tiny unit testing library.
'''


import atexit
from sys import stderr


__all__ = ['utest', 'utest_exc', 'utest_seq', 'utest_val']


test_count = 0
failure_count = 0


def utest(exp, fn, *args, **kwargs):
  '''
  Invoke `fn` with `args` and `kwargs`,
  and log a test failure if an exception is raised or the returned value does not equal `exp`.
  '''
  global test_count
  test_count += 1
  try:
    ret = fn(*args, **kwargs)
    exc = None
  except BaseException as e:
    ret = None
    exc = e
  else:
    if exp == ret: return
  log_failure(exp_label='value', exp=exp, ret=ret, exc=exc, name=fn.__qualname__, args=args, kwargs=kwargs)


def utest_exc(exp_exc, fn, *args, **kwargs):
  '''
  Invoke `fn` with `args` and `kwargs`,
  and log a test failure if an exception is not raised or the raised exception type and args not match `exp_exc`.
  '''
  global test_count
  test_count += 1
  try:
    ret = fn(*args, **kwargs)
    exc = None
  except BaseException as e:
    if exceptions_eq(exp_exc, e): return
    ret = None
    exc = e
  log_failure(exp_label='exception', exp=exp_exc, ret=ret, exc=exc, name=fn.__qualname__, args=args, kwargs=kwargs)


def utest_seq(exp_seq, fn, *args, **kwargs):
  '''
  Invoke `fn` with `args` and `kwargs`,
  and log a test failure if an exception is raised
  or items of the returned seqence value does not equal the items of `exp`.
  '''
  global test_count
  test_count += 1
  exp = list(exp_seq) # convert to a list for referential isolation and consistent string repr.
  try:
    ret_seq = fn(*args, **kwargs)
  except BaseException as e:
    log_failure(exp_label='sequence', exp=exp, exc=e, name=fn.__qualname__, args=args, kwargs=kwargs)
    return
  try:
    ret = list(ret_seq)
  except BaseException as e:
    log_failure(exp_label='sequence', exp=exp, ret=ret_seq, name=fn.__qualname__, args=args, kwargs=kwargs)
    return
  if exp == ret: return
  log_failure(exp_label='sequence', exp=exp, ret_label='sequence', ret=ret, name=fn.__qualname__, args=args, kwargs=kwargs)


def utest_val(exp_val, act_val, name):
  '''
  Log a test failure if `exp_val` does not equal `act_val`.
  '''
  global test_count
  test_count += 1
  if exp_val == act_val:
    return
  log_failure(exp_label='value', exp=exp_val, ret=act_val, exc=None, name=repr(name))


def log_failure(exp_label, exp, ret_label='value', ret=None, exc=None, name=None, args=(), kwargs={}):
  global failure_count
  assert name is not None
  failure_count += 1
  msg_lines = ['utest failure: ' + name]
  def msg(fmt, *items): msg_lines.append(('  ' + fmt).format(*items))
  for i, el in enumerate(args):
    msg('arg {}={!r}', i, el)
  for name, val, in sorted(kwargs.items()):
    msg('arg {}={!r}', name, val)
  msg('expected {}: {!r}', exp_label, exp)
  if exc is None: # unexpected value.
    msg('returned {}: {!r}', ret_label, ret)
  else: # unexpected exception.
    msg('raised exception: {!r}', exc)
  print(*msg_lines, sep='\n', end='\n\n', file=stderr)


def exceptions_eq(a, b):
  'Compare two exceptions; since Python exceptions do not implement value equality; we do our best here.'
  if type(a) != type(b): return False
  return a.args == b.args


@atexit.register
def report():
  'At process exit, if any test failures occured, print a summary message and cause process to exit with status code 1.'
  from os import _exit
  if failure_count > 0:
    print('\nutest ran: {}; failed: {}'.format(test_count, failure_count), file=stderr)
    _exit(1) # raising SystemExit has no effect in an atexit handler as of 3.5.2.

