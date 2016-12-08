'''
utest is a tiny unit testing library.
'''


import atexit
import inspect
from os.path import basename as _basename
from sys import stderr


__all__ = [
  'utest',
  'utest_exc',
  'utest_seq',
  'utest_seq_exc',
  'utest_val'
]


test_count = 0
failure_count = 0


def utest(exp, fn, *args, **kwargs):
  '''
  Invoke `fn` with `args` and `kwargs`.
  Log a test failure if an exception is raised or the returned value does not equal `exp`.
  '''
  global test_count
  test_count += 1
  try: ret = fn(*args, **kwargs)
  except BaseException as exc:
    log_failure(exp_label='value', exp=exp, exc=exc, subj=fn, args=args, kwargs=kwargs)
  else:
    if exp != ret:
      log_failure(exp_label='value', exp=exp, ret_label='value', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_exc(exp_exc, fn, *args, **kwargs):
  '''
  Invoke `fn` with `args` and `kwargs`.
  Log a test failure if an exception is not raised or if the raised exception type and args not match `exp_exc`.
  '''
  global test_count
  test_count += 1
  try: ret = fn(*args, **kwargs)
  except BaseException as exc:
    if not exceptions_eq(exp_exc, exc):
      log_failure(exp_label='exception', exp=exp_exc, exc=exc, subj=fn, args=args, kwargs=kwargs)
  else:
    log_failure(exp_label='exception', exp=exp_exc, ret_label='value', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_seq(exp_seq, fn, *args, **kwargs):
  '''
  Invoke `fn` with `args` and `kwargs`, and convert the resulting iterable into a sequence.
  Log a test failure if an exception is raised,
  or if any items of the returned seqence do not equal the items of `exp`.
  '''
  global test_count
  test_count += 1
  exp = list(exp_seq) # convert to a list for referential isolation and consistent string repr.
  try:
    ret_seq = fn(*args, **kwargs)
  except BaseException as exc:
    log_failure(exp_label='sequence', exp=exp, exc=exc, subj=fn, args=args, kwargs=kwargs)
    return
  try:
    ret = list(ret_seq)
  except BaseException as exc:
    log_failure(exp_label='sequence', exp=exp, ret_label='value', ret=ret_seq, exc=exc, subj=fn, args=args, kwargs=kwargs)
    return
  if exp != ret:
    log_failure(exp_label='sequence', exp=exp, ret_label='sequence', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_seq_exc(exp_exc, fn, *args, **kwargs):
  '''
  Invoke `fn` with `args` and `kwargs`, and convert the resulting iterable into a sequence.
  Log a test failure if an exception is not raised or if the raised exception type and args not match `exp_exc`.
  '''
  global test_count
  test_count += 1
  try:
    ret_seq = fn(*args, **kwargs)
    ret = list(ret_seq)
  except BaseException as exc:
    if not exceptions_eq(exp_exc, exc):
      log_failure(exp_label='exception', exp=exp_exc, exc=exc, subj=fn, args=args, kwargs=kwargs)
  else:
    log_failure(exp_label='exception', exp=exp_exc, ret_label='sequence', ret=ret, subj=fn, args=args, kwargs=kwargs)



def utest_val(exp_val, act_val, desc='<value>'):
  '''
  Log a test failure if `exp_val` does not equal `act_val`.
  Describe the test with the optional `desc`.
  '''
  global test_count
  test_count += 1
  if exp_val != act_val:
    log_failure(exp_label='value', exp=exp_val, ret_label='value', ret=act_val, subj=repr(desc))


def log_failure(exp_label, exp, ret_label=None, ret=None, exc=None, subj=None, args=(), kwargs={}):
  global failure_count
  assert subj is not None
  failure_count += 1
  frame_record = inspect.stack()[2] # caller of caller.
  frame = frame_record[0]
  info = inspect.getframeinfo(frame)
  name = subj if isinstance(subj, str) else subj.__qualname__
  msg_lines = ['{}:{}: utest failure: {}'.format(_basename(info.filename), info.lineno, name)]
  def msg(fmt, *items): msg_lines.append(('  ' + fmt).format(*items))
  for i, el in enumerate(args):
    msg('arg {}={!r}', i, el)
  for name, val, in sorted(kwargs.items()):
    msg('arg {}={!r}', name, val)
  msg('expected {}: {!r}', exp_label, exp)
  if ret_label: # unexpected value.
    msg('returned {}: {!r}', ret_label, ret)
  if exc is not None: # unexpected exception.
    msg('raised exception: {!r}', exc)
  print(*msg_lines, sep='\n', end='\n\n', file=stderr)


def exceptions_eq(a, b):
  '''
  Compare two exceptions for approximate value equality.
  Since Python exceptions do not implement value equality; we do our best here.
  '''
  return type(a) == type(b) and a.args == b.args


@atexit.register
def report():
  'At process exit, if any test failures occured, print a summary message and force process to exit with status code 1.'
  from os import _exit
  if failure_count > 0:
    print('\nutest ran: {}; failed: {}'.format(test_count, failure_count), file=stderr)
    _exit(1) # raising SystemExit has no effect in an atexit handler as of 3.5.2.

