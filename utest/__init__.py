'''
utest is a tiny unit testing library.
'''


import atexit as _atexit
import inspect as _inspect
import pathlib as _pathlib
import re as _re
from os import getcwd as _getcwd
from os.path import relpath as _rel_path
from sys import stderr as _stderr
from traceback import format_exc, format_exception as _format_exception
from types import TracebackType
from typing import Any, Callable, Iterable, TypeVar


__all__ = [
  'utest',
  'utest_call',
  'utest_exc',
  'utest_repr',
  'utest_seq',
  'utest_seq_exc',
  'utest_symmetric',
  'utest_val',
  'utest_val_ne',
]


_utest_test_count = 0
_utest_failure_count = 0


_C = TypeVar('_C', bound=Callable)
def utest_call(callable:_C) -> _C:
  'A function decorator to call the defined function immediately. Useful for wrapping test state in a local function scope.'
  callable()
  return callable


def utest(exp:Any, fn:Callable, *args:Any, _exit=False, _utest_depth=0, **kwargs:Any) -> None:
  '''
  Invoke `fn` with `args` and `kwargs`.
  Log a test failure if an exception is raised or the returned value does not equal `exp`.
  '''
  global _utest_test_count
  _utest_test_count += 1
  try: ret = fn(*args, **kwargs)
  except BaseException as exc:
    _utest_failure(_utest_depth, exp_label='value', exp=exp, exc=exc, subj=fn, args=args, kwargs=kwargs)
    if _exit: raise
  else:
    if exp != ret:
      _utest_failure(_utest_depth, exp_label='value', exp=exp, ret_label='value', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_repr(exp_repr:str, fn:Callable, *args:Any, _exit=False, _utest_depth=0, **kwargs:Any) -> None:
  '''
  Invoke `fn` with `args` and `kwargs`.
  Log a test failure if an exception is raised or the returned value's `repr` does not equal `exp_repr`.
  '''
  global _utest_test_count
  _utest_test_count += 1
  try: ret = fn(*args, **kwargs)
  except BaseException as exc:
    _utest_failure(_utest_depth, exp_label='repr', exp=exp_repr, exc=exc, subj=fn, args=args, kwargs=kwargs)
    if _exit: raise
  else:
    if exp_repr != repr(ret):
      _utest_failure(_utest_depth, exp_label='repr', exp=exp_repr, ret_label='value', ret=ret, subj=fn, args=args, kwargs=kwargs)



def utest_exc(exp_exc:Any, fn:Callable, *args:Any, _exit=False, _utest_depth=0, **kwargs:Any) -> None:
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
      if _exit: raise
  else:
    _utest_failure(_utest_depth, exp_label='exception', exp=exp_exc, ret_label='value', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_seq(exp_seq:Iterable[Any], fn:Callable, *args:Any, _exit=False, _utest_depth=0, _sort=False, **kwargs:Any) -> None:
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
    if _exit: raise
    return
  try:
    ret = list(ret_seq)
  except BaseException as exc:
    _utest_failure(_utest_depth, exp_label='sequence', exp=exp, ret_label='value', ret=ret_seq, exc=exc, subj=fn, args=args, kwargs=kwargs)
    return
  if _sort:
    try: ret.sort()
    except BaseException as exc:
      _utest_failure(_utest_depth, exp_label='sequence', exp=exp, ret_label='sort', ret=ret_seq, exc=exc, subj=fn, args=args, kwargs=kwargs)
      return
  if exp != ret:
    _utest_failure(_utest_depth, exp_label='sequence', exp=exp, ret_label='sequence', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_seq_exc(exp_exc:Any, fn:Callable, *args:Any, _exit=False, _utest_depth=0, **kwargs:Any) -> None:
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
      if _exit: raise
  else:
    _utest_failure(_utest_depth, exp_label='exception', exp=exp_exc, ret_label='sequence', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_items(exp_seq:Iterable[Any], fn:Callable, *args:Any, _exit=False, _utest_depth=0, **kwargs:Any) -> None:
  '''
  Invoke `fn` with `args` and `kwargs`, and convert the resulting mapping into a key/value items sequence.
  Log a test failure if an exception is raised,
  or if any items of the returned seqence do not equal the items of `exp`.
  '''
  global _utest_test_count
  _utest_test_count += 1
  exp = list(exp_seq) # convert to a list for referential isolation and consistent string repr.
  try:
    ret_seq = fn(*args, **kwargs)
  except BaseException as exc:
    _utest_failure(_utest_depth, exp_label='items', exp=exp, exc=exc, subj=fn, args=args, kwargs=kwargs)
    if _exit: raise
    return
  try:
    ret = list(ret_seq.items())
  except BaseException as exc:
    _utest_failure(_utest_depth, exp_label='items', exp=exp, ret_label='value', ret=ret_seq, exc=exc, subj=fn, args=args, kwargs=kwargs)
    return
  if exp != ret:
    _utest_failure(_utest_depth, exp_label='items', exp=exp, ret_label='items', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_items_exc(exp_exc:Any, fn:Callable, *args:Any, _exit=False, _utest_depth=0, **kwargs:Any) -> None:
  '''
  Invoke `fn` with `args` and `kwargs`, and convert the resulting iterable into a key/value items sequence.
  Log a test failure if an exception is not raised or if the raised exception type and args not match `exp_exc`.
  '''
  global _utest_test_count
  _utest_test_count += 1
  try:
    ret_seq = fn(*args, **kwargs)
    ret = list(ret_seq.items())
  except BaseException as exc:
    if not _compare_exceptions(exp_exc, exc):
      _utest_failure(_utest_depth, exp_label='exception', exp=exp_exc, exc=exc, subj=fn, args=args, kwargs=kwargs)
      if _exit: raise
  else:
    _utest_failure(_utest_depth, exp_label='exception', exp=exp_exc, ret_label='items', ret=ret, subj=fn, args=args, kwargs=kwargs)


def utest_val(exp_val:Any, act_val:Any, desc='<value>') -> None:
  '''
  Log a test failure if `exp_val` does not equal `act_val`.
  Describe the test with the optional `desc`.
  '''
  global _utest_test_count
  _utest_test_count += 1
  if exp_val != act_val:
    _utest_failure(depth=0, exp_label='value', exp=exp_val, ret_label='value', ret=act_val, subj=repr(desc))


def utest_val_ne(exp_val:Any, act_val:Any, desc='<value>') -> None:
  '''
  Log a test failure if `exp_val` equals `act_val`.
  Describe the test with the optional `desc`.
  '''
  global _utest_test_count
  _utest_test_count += 1
  if exp_val == act_val:
    _utest_failure(depth=0, exp_label='value', exp=exp_val, ret_label='value', ret=act_val, subj=repr(desc))


def utest_symmetric(test_fn:Callable, exp:Any, fn:Callable, *args:Any, _exit=False, _utest_depth=0, **kwargs:Any) -> None:
  '''
  Apply `test_fn` to the provided arguments,
  then again to the same arguments but with the last two positional parameters swapped.
  '''
  head = args[:-2]
  argA, argB = args[-2:]
  args_swapped = head + (argB, argA)
  test_fn(exp, fn, *args, _exit=_exit, _utest_depth=_utest_depth+1, **kwargs)
  test_fn(exp, fn, *args_swapped, _exit=_exit, _utest_depth=_utest_depth+1, **kwargs)


def _utest_failure(depth:int, exp_label:str, exp:Any, ret_label:str|None=None, ret:Any=None, exc:Any=None, subj:Any=None,
 args:tuple[Any,...]=(), kwargs:dict[str,Any]={}) -> None:

  global _utest_failure_count
  assert subj is not None
  _utest_failure_count += 1

  frame_record = _inspect.stack()[2 + depth] # caller of caller.
  frame = frame_record[0]
  info = _inspect.getframeinfo(frame)

  try: name = subj.__qualname__
  except AttributeError: name = str(subj)

  path = _rel_path(info.filename)
  if '/' not in path: path = f'./{path}'
  _errL(f'\n{path}:{info.lineno}: utest failure: {name}')

  for i, el in enumerate(args):
    _errL(f'  arg {i} = {el!r}')

  for name, val, in kwargs.items():
    _errL(f'  arg {name} = {val!r}')

  exp_label_colon = f'expected {exp_label}:'
  if ret_label: # Unexpected value.
    res_label_colon = f'returned {ret_label}:'
    res = ret
  if exc is not None: # Unexpected exception.
    res_label_colon = f'raised exception:'
    res = exc
  width = max(len(exp_label_colon),len(res_label_colon))

  _errL(f'  {exp_label_colon:{width}} {exp!r}')
  _errL(f'  {res_label_colon:{width}} {res!r}')
  if exc is not None: # Unexpected exception.
    for i, arg in enumerate(exc.args):
      _errL(f'    exc arg {i}: {arg!r}')
    _errL()
    _print_exception(exc)
  _errL()


def _compare_exceptions(exp:Any, act:Any) -> bool:
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


def _errL(*items:Any) -> None: print(*items, sep='', file=_stderr)


def _print_exception(exc: BaseException) -> Any:

  messages = _format_exception(type(exc), exc, tb=exc.__traceback__, limit=None, chain=True)
  for msg in messages:
    if m := _exc_msg_re.fullmatch(msg):
      file = m['stack_file']
      line = m['stack_line']
      s_in = m['stack_in'] or ''
      fn = m['stack_fn']
      code = m['stack_code']
      if file.startswith(_starting_work_dir_slash):
        rel_file = file[len(_starting_work_dir_slash):]
        file = ('' if ('/' in rel_file) else './') + rel_file
      elif file.startswith(_home_dir_slash):
        rel_file = file[len(_home_dir_slash):]
        file = '~/' + rel_file
      _stderr.write(f'  File "{file}", line {line}{s_in}{fn}{code}')
    else:
      _stderr.write(msg)



_home_dir = str(_pathlib.Path.home())
_home_dir_slash = _home_dir + ('' if _home_dir.endswith('/') else '/')

_work_dir = _getcwd()
_starting_work_dir_slash = _work_dir + ('' if _work_dir.endswith('/') else '/')

_exc_msg_re = _re.compile(r'''(?sx) # s=Dotall; each message can contain newlines.
\ \ File\ "(?P<stack_file>[^"\n]+)",\ line\ (?P<stack_line>\d+)(?P<stack_in>,\ in\ )?(?P<stack_fn>[^\n]*)(?P<stack_code>.*)
''')
#^ Note: this pattern will fail if the file name contains a '"'.


@_atexit.register
def report() -> None: #!cov-ignore - the call to _exit kills coven before it records anything.
  'At process exit, if any test failures occured, print a summary message and force process to exit with status code 1.'
  from os import _exit
  if _utest_failure_count > 0:
    _errL(f'\nutest ran: {_utest_test_count}; failed: {_utest_failure_count}')
    _stderr.flush()
    _exit(1) # raising SystemExit has no effect in an atexit handler as of 3.5.2.
