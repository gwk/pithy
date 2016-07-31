'''
utest is a tiny unit testing library.
'''


import atexit
from sys import stderr


__all__ = ['utest', 'utest_exc']


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
  log_failure('value', exp, ret, exc, fn, args, kwargs)


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
  log_failure('exception', exp_exc, ret, exc, fn, args, kwargs)


def log_failure(exp_prefix, exp, ret, exc, fn, args, kwargs):
  global failure_count
  failure_count += 1
  msg_lines = ['utest failure: ' + fn.__qualname__]
  def msg(fmt, *items): msg_lines.append(('  ' + fmt).format(*items))
  for i, el in enumerate(args):
    msg('arg {}={!r}', i, el)
  for name, val, in sorted(kwargs.items()):
    msg('arg {}={!r}', name, val)
  msg('expected {}: {!r}', exp_prefix, exp)
  if exc is None: # unexpected value.
    msg('returned value: {!r}', ret)
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

