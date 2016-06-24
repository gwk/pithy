#!/usr/bin/env python3
# © 2015 George King.
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import argparse
import ast
import os
import re
import shlex
import signal
import subprocess
import sys

from string import Template
from pithy import *


bar_width = 64
dflt_build_dir = '_build'
dflt_timeout = 4


def main():
  arg_parser = argparse.ArgumentParser(description='iotest: a simple file-based test harness.')
  arg_parser.add_argument('-parse-only', action='store_true', help='parse test cases and exit.'),
  arg_parser.add_argument('-fail-fast',  action='store_true', help='exit on first error; implied by -dbg.'),
  arg_parser.add_argument('-dbg', action='store_true', help='debug mode: print extra info; implies -fast).'),
  arg_parser.add_argument('paths', nargs='*', help='test directories to search.')
  args = arg_parser.parse_args()
  
  if args.dbg: errL('iotest: DEBUG MODE ON.')

  proj_dir = find_proj_dir()
  build_dir = path_join(proj_dir, dflt_build_dir)
  ctx = Ctx(args.parse_only, args.fail_fast, args.dbg, args.paths, proj_dir, build_dir)

  cases = []

  for raw_path in ctx.top_paths:
    if not path_exists(raw_path):
      failF('iotest: {!r}: path argument does not exist.', raw_path)
    if not is_dir(raw_path):
      failF('iotest: {!r}: path argument must be a directory.', raw_path)
    dir_path = norm_path(raw_path) + '/'
    if dir_path.find('..') != -1:
      # because we recreate the dir structure in the results dir, parent dirs are forbidden.
      raiseS("test directory path cannot contain '..':", dir_path)
    proto = collect_proto(ctx, dir_path)
    collect_cases(ctx, cases, proto, dir_path)

  broken_count = 0
  skipped_count = 0
  failed_count = 0
  for case in cases:
    if case.broken:
      broken_count += 1
    elif case.skip:
      skipped_count += 1
    else:
      ok = try_case(ctx, case)
      if not ok:
        failed_count += 1

  outL('\n', '#' * bar_width)
  count = len(cases)
  if not any([broken_count, skipped_count, failed_count]):
    outFL('TESTS PASSED: {}.', count)
    return 0
  else:
    outFL('TESTS FOUND: {}; IGNORED: {}; SKIPPED: {}; FAILED: {}.',
      count, broken_count, skipped_count, failed_count)
    return 1


class Ctx:
  'Ctx is the global test context, holding configuration options.'

  def __init__(self, parse_only, fail_fast, dbg, paths, proj_dir, build_dir):
    self.parse_only = parse_only
    self.should_fail_fast = fail_fast or dbg
    self.dbg = dbg
    self.top_paths = paths
    self.proj_dir = proj_dir
    self.build_dir = build_dir

  def fail_fast(self):
    if self.should_fail_fast:
      fail('iotest: stopping after error (-fail-fast).')


def find_proj_dir():
  '''
  find the project root directory,
  as denoted by the presence of a file/directory named any of the following:
  - .git
  - .project-root
  '''
  # TODO: support relying on .gitignore, .git, or similar?
  for path in walk_dirs_up('.'):
    for name in list_dir(path):
      if name in ('.git', '.project-root'):
        return path
  fail("iotest: could not find .git or .project-root in current directory or its parents.")


def collect_proto(ctx, end_dir_path):
  'assemble the prototype test case information from files named `_default.*`.'
  proto = None
  for dir_path in path_range(ctx.proj_dir, abs_path(end_dir_path)):
    file_paths = [path_join(dir_path, name) for name in list_dir(dir_path) if path_stem(name) == '_default']
    proto = create_default_case(ctx, proto, path_join(dir_path, '_default'), file_paths)
  return proto


def collect_cases(ctx, cases, proto, dir_path):
  'find all test cases within the specified directory.'
  sub_dirs = []
  file_paths = []
  names = list_dir(dir_path)
  for name in names:
    if name.startswith('.'): # ignore hidden files.
      continue
    path = path_join(dir_path, name)
    if is_dir(path):
      sub_dirs.append(path + '/')
    else:
      file_paths.append(path)

  default = create_cases(ctx, cases, proto, dir_path, file_paths)

  for sub_dir in sub_dirs:
    collect_cases(ctx, cases, default, sub_dir)


def create_default_case(ctx, proto, stem, file_paths):
  if not file_paths:
    return proto
  default = Case(ctx, stem, file_paths, proto)
  if default.broken: ctx.fail_fast()
  return default


def create_cases(ctx, cases, proto, dir_path, file_paths):
  groups = grouped_seq(file_paths, path_stem)
  # default.
  default_stem = dir_path + '_default'
  default = create_default_case(ctx, proto, default_stem, groups.get(default_stem))
  # cases.
  for (stem, paths) in sorted(groups.items()):
    if stem == default_stem or not is_case_implied(paths): continue
    case = Case(ctx, stem, paths, default)
    if case.broken: ctx.fail_fast()
    cases.append(case)
  return default


def is_case_implied(paths):
  'one of the standard test file extensions must be present to imply a test case.'
  return any(path_ext(p) in ('.iot', '.out', '.err') for p in paths)


class Case:
  'Case represents a single test case, or a default.'

  def __init__(self, ctx, stem, file_paths, proto):
    self.stem = stem # path stem to this test case.
    self.name = path_name(stem)
    self.test_dir = path_join(ctx.build_dir, stem)
    # derived properties.
    self.test_info_paths = [] # the files that comprise the test case.
    self.dflt_src_path = None
    self.broken = proto.broken if (proto is not None) else False
    # configurable properties.
    self.args = None # arguments to follow the file under test.
    self.cmd = None # command with which to invoke the test.
    self.code = None # the expected exit code.
    self.desc = None # description.
    self.env = None # environment variables.
    self.err_mode = None # comparison mode for stderr expectation.
    self.err_path = None # file path for stderr expectation.
    self.err_val = None # stderr expectation value (mutually exclusive with err_path).
    self.files = None # additional file expectations.
    self.in_ = None # stdin as text.
    self.links = None # symlinks to be made into the test directory; written as a dict.
    self.out_mode = None # comparison mode for stdout expectation.
    self.out_path = None # file path for stdout expectation.
    self.out_val = None # stdout expectation value (mutually exclusive with out_path).
    self.timeout = None 
    self.skip = None

    try:
      # read in all file info specific to this case.
      for path in sorted(file_paths, key=lambda p: '' if p.endswith('.iot') else p):
        # sorting with custom key fn simply ensures that the .iot file gets added first,
        # for clarity when conflicts arise.
        self.add_file(path)
      # copy any defaults; if the key already exists, it will be a conflict error.
      # TODO: would it make more sense to put this step above the case files?
      if proto is not None:
        for key in case_key_validators:
          val = proto.__dict__[key]
          if val is None: continue
          self.add_val_for_key(key, val)
      # do all additional computations now, so as to fail as quickly as possible.
      self.derive_info(ctx)

    except Exception as e:
      errFL('WARNING: broken test case: {};\n  exception: {}', stem, e)
      self.describe()
      errL()
      if ctx.dbg: raise
      self.broken = True


  def describe(self):
    def stable_repr(val):
      if is_dict(val):
        return '{{{}}}'.format(', '.join('{!r}:{!r}'.format(*p) for p in sorted(val.items())))
      return repr(val)

    items = sorted(self.__dict__.items())
    errLSSL('Case:', *('{}: {}'.format(k, stable_repr(v)) for k, v in items))


  def add_file(self, path):
    ext = path_ext(path)
    if ext == '.iot':   self.add_iot_file(path)
    elif ext == '.in':  self.add_std_file(path, 'in_')
    elif ext == '.out': self.add_std_file(path, 'out')
    elif ext == '.err': self.add_std_file(path, 'err')
    elif self.dflt_src_path is None:
      self.dflt_src_path = abs_path(path)
    else:
      self.dflt_src_path = Ellipsis


  def add_std_file(self, path, key):
    self.test_info_paths.append(path)
    text = read_from_path(path)
    self.add_val_for_key(key + '_val', text)


  def add_iot_file(self, path):
    self.test_info_paths.append(path)
    text = read_from_path(path)
    if not text or text.isspace():
      return
    info = ast.literal_eval(text)
    req_type(info, dict)
    for kv in info.items():
      self.add_iot_val_for_key(*kv)


  def add_val_for_key(self, key, val):
    if self.__dict__[key] is not None:
      raiseF('key has conflicting values: {}', key)
    self.__dict__[key] = val


  def add_iot_val_for_key(self, iot_key, val):
    key = ('in_' if iot_key == 'in' else iot_key.replace('-', '_'))
    try:
      msg, predicate, validator_fn = case_key_validators[key]
    except KeyError:
      raiseF('invalid key in .iot file: {!r}', key)
    if not predicate(val):
      raiseF('key: {}: expected value of type: {}; received: {!r}', iot_key, msg, val)
    if validator_fn:
      validator_fn(key, val)
    self.add_val_for_key(key, val)


  def derive_info(self, ctx):
    if self.name == '_default': return # do not process prototype cases.

    self.test_env = {}
    env = self.test_env # local alias for convenience.
    env.update(self.env or {})
    for key in ('NAME', 'SRC', 'ROOT'):
      if key in env:
        raiseF('specified env contains reserved key: {}', key)
    env['NAME'] = self.name
    env['SRC'] = str(self.dflt_src_path) # may be 'None' or 'Ellipsis'.
    env['PROJ'] = abs_path(ctx.proj_dir)

    def default_to_env(key):
      if key not in env and key in os.environ:
        env[key] = os.environ[key]

    default_to_env('PATH')
    default_to_env('PYTHONPATH')

    def expand_str(val):
      t = Template(val)
      return t.safe_substitute(**env)

    def expand(val):
      if not val:
        return []
      if is_str(val):
        # note: plain strings are expanded first, then split.
        # this behavior matches that of shell commands more closely than split-then-expand,
        # but introduces all the confusion of shell quoting.
        return shlex.split(expand_str(val))
      return [expand_str(v) for v in val]

    args = expand(self.args)

    if self.cmd:
      self.test_cmd = expand(self.cmd)
      if args:
        self.test_cmd += args
      elif self.dflt_src_path not in (None, Ellipsis):
        self.test_cmd += [self.dflt_src_path]
    elif self.dflt_src_path:
      self.test_cmd = [self.dflt_src_path] + (args or [])
    else:
      raiseS('no cmd specified and no default source path found')
    
    self.test_in = expand_str(self.in_) if self.in_ is not None else None

    self.test_expectations = []

    def add_std_exp(name, mode, path, val):
      info = {}
      if mode is not None: info['mode'] = mode
      if path is not None: info['path'] = path
      if val is not None: info['val'] = val
      exp = FileExpectation(name, info, expand_str)
      self.test_expectations.append(exp)

    add_std_exp('err', self.err_mode, self.err_path, self.err_val)
    add_std_exp('out', self.out_mode, self.out_path, self.out_val)

    for path, info in self.files or []:
      exp = FileExpectation(path, info, expand_str)
      self.test_expectations.append(exp)



def validate_exp_mode(key, mode):
  if mode not in file_expectation_fns:
    raiseF('key: {}: invalid file expectation mode: {}', key, mode)

def validate_exp_dict(key, val):
  if not is_dict(val):
    raiseF('file expectation: {}: value must be a dictionary.', key)
  for k in val:
    if k not in ('mode', 'path', 'val'):
      raiseF('file expectation: {}: invalid expectation property: {}', key, k)

def validate_files_dict(key, val):
  for k, exp_dict in val:
    if k == 'out' or k == 'err':
      raiseF('key: {}: {}: use the standard properties instead ({}-mode, {}-path, {}-val).',
        key, k, k, k, k)
    validate_exp_dict(k, v)

def validate_links_dict(key, val):
  for src, dst in val.items():
    if src.find('..') != -1: raiseF("key: {}: link source contains '..': {}", key, src)
    if dst.find('..') != -1: raiseF("key: {}: link destination contains '..': {}", key, dst)


case_key_validators = { # key => msg, validator_predicate, validator_fn.
  'args':     ('string or list of strings', is_str_or_list, None),
  'cmd':      ('string or list of strings', is_str_or_list, None),
  'code':     ('int',                       is_int,         None),
  'desc':     ('str',                       is_str,         None),
  'env':      ('dict of strings',           is_dict_of_str, None),
  'err_mode': ('str',                       is_str,         validate_exp_mode),
  'err_path': ('str',                       is_str,         None),
  'err_val':  ('str',                       is_str,         None),
  'files':    ('dict',                      is_dict,        validate_files_dict),
  'in_':      ('str',                       is_str,         None),
  'links':    ('dict of strings',           is_dict_of_str, validate_links_dict),
  'out_mode': ('str',                       is_str,         validate_exp_mode),
  'out_path': ('str',                       is_str,         None),
  'out_val':  ('str',                       is_str,         None),
  'skip':     ('bool',                      is_bool,        None),
  'timeout':  ('positive int',              is_pos_int,     None),
}


class FileExpectation:

  def __init__(self, path, info, expand_str_fn):
    if path.find('..') != -1:
      raiseF("file expectation {}: cannot contain '..'", path)
    self.path = path

    self.mode = info.get('mode', 'equal')
    validate_exp_mode(path, self.mode)

    try:
      exp_path = info['path']
    except KeyError:
      val = info.get('val', '')
    else:
      if 'val' in info:
        raiseF('file expectation {}: cannot specify both `path` and `val` properties', path)
      exp_path_expanded = expand_str_fn(exp_path)
      val = read_from_path(exp_path_expanded)
    self.val = expand_str_fn(val)

  def __repr__(self):
    return 'FileExpectation({!r}, {!r}, {!r})'.format(self.path, self.mode, self.val)


def try_case(ctx, case):
  try:
    ok = run_case(ctx, case)
  except Exception as e:
    s = str(e)
    errFL('ERROR: could not run test case: {};\n  exception: {}', case.stem, e)
    if s == '[Errno 8] Exec format error':
      errFL("  note: is the test script missing its hash-bang line? e.g. '#!/usr/bin/env [INTERPRETER]'")
    elif s == '[Errno 13] Permission denied':
      errFL("  note: is the test script executable permission not set?\n"
        "  possible fix: `chmod +x {}`", case.test_cmd[0])
    if ctx.dbg: raise
    ctx.fail_fast()
    ok = False
  if not ok:
    if case.desc: outSL('description:', case.desc)
    outL('=' * bar_width, '\n')
  if ctx.dbg: errL()
  if not ok: ctx.fail_fast()
  return ok


def run_case(ctx, case):
  outSL('executing:', case.stem)
  if ctx.dbg: case.describe()

  # set up directory.
  if path_exists(case.test_dir):
    try:
      remove_dir_contents(case.test_dir)
    except NotADirectoryError:
      failF('error: {}: test directory already exists as a file; please remove it and try again.',
       case.test_dir)
  else:
    make_dirs(case.test_dir)
  
  if case.links is not None:
    for link_path, dst_path in case.links.items():
      link = path_join(case.test_dir, link_path)
      dst = path_join(ctx.proj_dir, dst_path)
      os.symlink(dst, link)

  if case.in_ is not None:
    in_path = path_join(case.test_dir, 'in')
    write_to_path(in_path, case.in_)
  else:
    in_path = '/dev/null'
  if ctx.dbg: errSL('input path:', in_path)

  if case.code is None:
    exp_code = 1 if case.err_val else 0
  else:
    exp_code = case.code

  code_ok = run_cmd(ctx,
    cmd=case.test_cmd,
    cwd=case.test_dir,
    env=case.test_env,
    in_path=in_path,
    out_path=path_join(case.test_dir, 'out'),
    err_path=path_join(case.test_dir, 'err'),
    timeout=(case.timeout or dflt_timeout),
    exp_code=exp_code)

  # use a list comprehension to ensure that we always report all failed expectations.
  exps_ok = all([check_file_exp(ctx, case.test_dir, exp) for exp in case.test_expectations])
  return code_ok and exps_ok


def run_cmd(ctx, cmd, cwd, env, in_path, out_path, err_path, timeout, exp_code):
  # print verbose command info formatted as shell commands for manual repro.
  if ctx.dbg:
    errSL('cwd:', cwd)
    errSL('cmd:', *(cmd + ['<{} # 1>{} 2>{}'.format(in_path, out_path, err_path)]))
    errSL('env:', *['{}={};'.format(*p) for p in sorted(env.items())])

  with open(in_path, 'r') as i, open(out_path, 'w') as o, open(err_path, 'w') as e:
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=i, stdout=o, stderr=e)
    # timeout alarm handler.
    # since signal handlers carry reentrancy concerns, do not do any IO within the handler.
    timed_out = False
    def alarm_handler(signum, current_stack_frame):
      nonlocal timed_out
      timed_out = True
      proc.kill()

    signal.signal(signal.SIGALRM, alarm_handler) # set handler.
    signal.alarm(timeout) # set alarm.
    code = proc.wait() # wait for process to complete; TODO: change to communicate() for stdin support.
    signal.alarm(0) # disable alarm.
    
    if timed_out:
      outFL('process timed out ({} sec) and was killed', timeout)
      return False
    if code != exp_code:
      outFL('process returned code: {}; expected {}', code, exp_code)
      return False
    return True


def check_file_exp(ctx, test_dir, exp):
  'return True if expectation is met.'
  if ctx.dbg: errFL('check_file_exp: {}', exp)
  path = path_join(test_dir, exp.path)
  try:
    with open(path) as f:
      act_val = f.read()
  except Exception as e:
    outFL('ERROR: could not read test output file: {}\n  exception: {!r}', path, e)
    if ctx.dbg: raise
    ctx.fail_fast()
    outSL('-' * bar_width)
    return False
  if file_expectation_fns[exp.mode](exp.val, act_val):
    return True
  outFL('output file {!r} does not {} expected value:', path, exp.mode)
  for line in exp.val.splitlines():
    outL('\x1B[0;34m', line, '\x1B[0m') # blue text.
  if exp.val and not exp.val.endswith('\n'):
    outL('(missing final newline)')
  if exp.mode == 'equal': # show a diff.
    path_expected = path + '-expected'
    write_to_path(path_expected, exp.val)
    cmd = diff_cmd + [path_expected, path]
    outSL(*cmd)
    runC(cmd, exp=None)
  else:
    outSL('cat', path)
    with open(path) as f:
      line = None
      for line in f:
        l = line.rstrip('\n')
        outL('\x1B[0;41m', l, '\x1B[0m') # red background.
      if line is not None and not line.endswith('\n'):
        outL('(missing final newline)')
  outSL('-' * bar_width)
  return False


diff_cmd = 'git diff --histogram --no-index --no-prefix --no-renames --exit-code --color'.split()


# file expectation functions.

def compare_equal(exp, val):
  return exp == val

def compare_contain(exp, val):
  return val.find(exp) != -1

def compare_match(exp, val):
  return re.fullmatch(exp, val)

def compare_ignore(exp, val):
  return True


file_expectation_fns = {
  'equal'   : compare_equal,
  'contain' : compare_contain,
  'match'   : compare_match,
  'ignore'  : compare_ignore,
}


if __name__ == '__main__':
  exit(main())
