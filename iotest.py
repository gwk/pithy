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
import time

from itertools import zip_longest
from string import Template
from sys import stdout, stderr

from pithy.ansi import RST, TXT_B, TXT_D, TXT_R
from pithy.immutable import Immutable
from pithy.io import errFL, errL, errSL, fail, failF, outF, outFL, outL, outSL, raiseF, read_from_path, read_first_line_from_path, write_to_path, writeLSSL
from pithy.string_utils import string_contains
from pithy.fs import (abs_path, find_project_dir, is_dir, is_node_not_link, is_python3_file, list_dir, open_new, make_dirs, normalize_path,
  path_descendants, path_dir, path_dir_or_dot, path_exists, path_ext, path_join,
  path_name, path_name_stem, path_rel_to_current_or_abs, path_stem, rel_path, remove_dir_contents, remove_file_if_exists, walk_dirs_up)
from pithy.iterable import fan_by_key_fn
from pithy.task import ProcessExpectation, ProcessTimeout, run, runC
from pithy.type_util import is_bool, is_dict_of_str, is_dict, is_int, is_list, is_pos_int, is_set, is_set_of_str, is_str, is_str_or_list, req_type

bar_width = 64
dflt_build_dir = '_build'
dflt_timeout = 4
coverage_name = '_coverage.cove'

def main():
  start_time = time.time()
  arg_parser = argparse.ArgumentParser(description='iotest: a simple file-based test harness.')
  arg_parser.add_argument('-build-dir')
  arg_parser.add_argument('-parse-only', action='store_true', help='parse test cases and exit.')
  arg_parser.add_argument('-coverage', action='store_true', help='use cove to trace test coverage.')
  arg_parser.add_argument('-no-coverage-report', action='store_true', help='do not report coverage.')
  arg_parser.add_argument('-no-times', action='store_true', help='do not report test times.')
  arg_parser.add_argument('-fail-fast',  action='store_true', help='exit on first error; implied by -dbg.')
  arg_parser.add_argument('-dbg', action='store_true', help='debug mode: print extra info; implies -fast).')
  arg_parser.add_argument('paths', nargs='*', default=['test'], help='test directories to search.')
  args = arg_parser.parse_args()

  if args.dbg: errL('iotest: DEBUG MODE ON.')

  if not args.coverage and args.no_coverage_report:
    failF('iotest error: `-no-coverage-report` is only valid in combination with `-coverage`.')

  proj_dir = find_project_dir()
  if proj_dir is None:
    fail("iotest error: could not find .git or .project-root in current directory or its parents.")

  build_dir = args.build_dir or path_join(proj_dir, dflt_build_dir)

  if args.dbg:
    def fail_fast(e=None):
      errL('\nfail_fast:')
      raise Exception('iotest: stopping after error (-dbg).') from e
  elif args.fail_fast:
    def fail_fast(e=None): fail('iotest: stopping after error (-fail-fast).')
  else:
    def fail_fast(e=None): pass

  ctx = Immutable(
    build_dir=build_dir,
    coverage=args.coverage,
    dbg=args.dbg,
    fail_fast=fail_fast,
    parse_only=args.parse_only,
    proj_dir=proj_dir,
    show_times=(not args.no_times),
    top_paths=args.paths,
    coverage_cases=[],
  )

  cases = []

  for raw_path in ctx.top_paths:
    if not path_exists(raw_path):
      failF('iotest error: argument path does not exist: {!r}.', raw_path)
    path = normalize_path(raw_path)
    if string_contains(path, '..'):
      # because we recreate the dir structure in the results dir, parent dirs are forbidden.
      failF("iotest error: argument path cannot contain '..': {!r}.", path)
    if is_dir(path):
      dir_path = path + '/'
      specified_name_stem = None
    else:
      dir_path = path_dir_or_dot(path) + '/'
      specified_name_stem = path_name_stem(path)
    proto = collect_proto(ctx, dir_path)
    collect_cases(ctx, cases, proto, dir_path, specified_name_stem)

  broken_count = 0
  skipped_count = 0
  failed_count = 0
  for case in cases:
    if case.broken:
      broken_count += 1
    elif case.skip:
      skipped_count += 1
      outFL('{:{bar_width}} SKIPPED.', case.stem, bar_width=bar_width)
    elif ctx.parse_only:
      continue
    else:
      ok = try_case(ctx, case)
      if not ok:
        failed_count += 1

  outL('\n', '#' * bar_width)
  count = len(cases)
  total_time = time.time() - start_time
  if any([broken_count, skipped_count, failed_count]):
    msg = 'TESTS FOUND: {}; BROKEN: {}; SKIPPED: {}; FAILED: {}.'.format(
      count, broken_count, skipped_count, failed_count)
    code = 1
  else:
    msg = 'TESTS {}: {}.'.format('PARSED' if ctx.parse_only else 'PASSED', count)
    code = 0
  if ctx.show_times:
    outFL('{:{bar_width}} {:.2f} sec.', msg, total_time, bar_width=bar_width)
  else:
    outL(msg)
  if args.coverage and not args.no_coverage_report:
    report_coverage(ctx)
  else:
    exit(code)


def collect_proto(ctx, end_dir_path):
  '''
  Assemble the prototype test case information from files named `_default.*`,
  starting at the project root and traversing successive child directories up to `end_dir_path`.
  This function is necessary to collect complete prototypes for a specified subdirectory.
  '''
  proto = None
  for dir_path in path_descendants(ctx.proj_dir, abs_path(end_dir_path), include_end=False):
    file_paths = [path_join(dir_path, name) for name in list_dir(dir_path) if path_stem(name) == '_default']
    proto = create_proto_case(ctx, proto, path_join(dir_path, '_default'), file_paths)
  return proto


def collect_cases(ctx, cases, proto, dir_path, specified_name_stem):
  'find all test cases within the specified directory.'
  collect_dirs = (specified_name_stem is None)
  sub_dirs = []
  file_paths = []
  names = list_dir(dir_path)
  for name in names:
    if name.startswith('.'): # ignore hidden files.
      continue
    path = path_join(dir_path, name)
    if collect_dirs:
      if is_dir(path):
        sub_dirs.append(path + '/')
      else:
        file_paths.append(path)
    elif path_stem(name) in('_default', specified_name_stem):
      file_paths.append(path)
  default = create_cases(ctx, cases, proto, dir_path, file_paths)
  if collect_dirs:
    for sub_dir in sub_dirs:
      collect_cases(ctx, cases, default, sub_dir, specified_name_stem)


def create_proto_case(ctx, proto, stem, file_paths):
  if not file_paths:
    return proto
  default = Case(ctx, stem, file_paths, proto)
  if default.broken: ctx.fail_fast()
  return default


def create_cases(ctx, cases, parent_proto, dir_path, file_paths):
  groups = fan_by_key_fn(file_paths, key=path_stem)
  # default.
  default_stem = dir_path + '_default'
  proto = create_proto_case(ctx, parent_proto, default_stem, groups.get(default_stem))
  # cases.
  for (stem, paths) in sorted(groups.items()):
    if stem == default_stem or not is_case_implied(paths): continue
    case = Case(ctx, stem, paths, proto)
    if case.broken: ctx.fail_fast()
    cases.append(case)
  return proto


def is_case_implied(paths):
  'one of the standard test file extensions must be present to imply a test case.'
  return any(path_ext(p) in ('.iot', '.out', '.err') for p in paths)


def report_coverage(ctx):
  if not ctx.coverage_cases:
    exit('No coverage generated by tests.')
  cmd = ['cove', '-coalesce'] + [path_join(case.test_dir, case.coverage_path) for case in ctx.coverage_cases]
  if ctx.dbg: errSL('#', *cmd)
  outL()
  stdout.flush()
  exit(runC(cmd))


class IotParseError(Exception): pass


class Case:
  'Case represents a single test case, or a default.'

  def __init__(self, ctx, stem, file_paths, proto):
    self.stem = stem # path stem to this test case.
    self.name = path_name(stem)
    # derived properties.
    self.test_info_paths = [] # the files that comprise the test case.
    self.dflt_src_paths = []
    self.broken = proto.broken if (proto is not None) else False
    self.coverage_targets = None
    self.test_dir = None
    self.test_dir_suffix = None
    self.test_cmd = None
    self.test_env = None
    self.test_in = None
    self.test_expectations = None
    self.test_links = None # sequence of (orig-name, link-name) pairs.
    # configurable properties.
    self.args = None # arguments to follow the file under test.
    self.cmd = None # command string/list with which to invoke the test.
    self.coverage = None # list of string/list of names to include in code coverage analysis.
    self.code = None # the expected exit code.
    self.compile = None # the optional list of compile commands, each a string or list of strings.
    self.compile_timeout = None
    self.desc = None # description.
    self.dir = None # optional directory that allows multiple tests to be run over same directory contents.
    self.env = None # environment variables.
    self.err_mode = None # comparison mode for stderr expectation.
    self.err_path = None # file path for stderr expectation.
    self.err_val = None # stderr expectation value (mutually exclusive with err_path).
    self.files = None # additional file expectations.
    self.in_ = None # stdin as text.
    self.links = None # symlinks to be made into the test directory; written as a str, set or dict.
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
      outFL('WARNING: broken test case: {}', stem)
      outFL('  exception: {}: {}.', type(e).__name__, e)
      # not sure if it makes sense to describe cases for some exceptions;
      # for now, just carve out the ones for which it is definitely useless.
      if not isinstance(e, IotParseError):
        self.describe(stdout)
        outL()
      ctx.fail_fast(e)
      self.broken = True

  @property
  def is_isolated(self): return self.dir is None

  def std_name(self, std):
    return std if self.is_isolated else '{}.{}'.format(self.test_dir_suffix, std)

  @property
  def coverage_path(self):
    return self.std_name(coverage_name)

  @property
  def cove_cmd_prefix(self):
    cove_cmd = ['cove', '-output', self.coverage_path]
    if self.coverage_targets:
      cove_cmd += ['-targets'] + self.coverage_targets
    cove_cmd.append('--')
    return cove_cmd

  def describe(self, file):
    def stable_repr(val):
      if is_dict(val):
        return '{{{}}}'.format(', '.join('{!r}:{!r}'.format(*p) for p in sorted(val.items())))
      return repr(val)

    items = sorted(self.__dict__.items())
    writeLSSL(file, 'Case:', *('{}: {}'.format(k, stable_repr(v)) for k, v in items))


  def add_file(self, path):
    ext = path_ext(path)
    if ext == '.iot':   self.add_iot_file(path)
    elif ext == '.in':  self.add_std_file(path, 'in_')
    elif ext == '.out': self.add_std_file(path, 'out')
    elif ext == '.err': self.add_std_file(path, 'err')
    else: self.dflt_src_paths.append(path)


  def add_std_file(self, path, key):
    self.test_info_paths.append(path)
    text = read_from_path(path)
    self.add_val_for_key(key + '_val', text)


  def add_iot_file(self, path):
    self.test_info_paths.append(path)
    text = read_from_path(path)
    if not text or text.isspace():
      return
    try:
      info = ast.literal_eval(text)
    except ValueError as e:
      msg = str(e)
      if msg.startswith('malformed node or string:'): # omit the repr garbage containing address.
        msg = 'malformed .iot file: {!r}'.format(path)
      raise IotParseError(msg) from e
    req_type(info, dict)
    for kv in info.items():
      self.add_iot_val_for_key(*kv)


  def add_val_for_key(self, key, val):
    existing = self.__dict__[key]
    if existing is not None:
      raiseF('conflicting values for key: {!r};\n  existing: {!r};\n  incoming: {!r}',
        key, existing, val)
    self.__dict__[key] = val


  def add_iot_val_for_key(self, iot_key, val):
    key = ('in_' if iot_key == 'in' else iot_key.replace('-', '_'))
    try:
      msg, predicate, validator_fn = case_key_validators[key]
    except KeyError:
      raiseF('invalid key in .iot file: {!r}', key)
    if not predicate(val):
      raiseF('key: {!r}: expected value of type: {}; received: {!r}', iot_key, msg, val)
    if validator_fn:
      validator_fn(key, val)
    self.add_val_for_key(key, val)


  def derive_info(self, ctx):
    if self.name == '_default': return # do not process prototype cases.

    if self.dir and not self.stem.startswith(self.dir):
      raiseF("test directory specified in 'dir' is not a case stem prefix: {!r}", self.dir)
    self.test_dir = path_join(ctx.build_dir, self.dir or self.stem)
    if self.dir:
      self.test_dir_suffix = self.stem[len(self.dir):].strip('/')
    else:
      self.test_dir_suffix = None

    self.test_env = {}
    env = self.test_env # local alias for convenience.
    env['BUILD'] = ctx.build_dir
    env['NAME'] = self.name
    env['PROJ'] = abs_path(ctx.proj_dir)
    env['SRC'] = self.dflt_src_paths[0] if len(self.dflt_src_paths) == 1 else 'NONE'
    env['STEM'] = self.stem

    def default_to_env(key):
      if key not in env and key in os.environ:
        env[key] = os.environ[key]

    default_to_env('LANG') # necessary to make std file handles unicode-aware.
    default_to_env('PATH')
    default_to_env('PYTHONPATH')
    default_to_env('SDKROOT')

    def expand_str(val):
      t = Template(val)
      return t.safe_substitute(**env)

    def expand(val):
      if val is None:
        return []
      if is_str(val):
        # note: plain strings are expanded first, then split.
        # this behavior matches that of shell commands more closely than split-then-expand,
        # but introduces all the confusion of shell quoting.
        return shlex.split(expand_str(val))
      if is_list(val):
        return [expand_str(el) for el in val]
      raise ValueError(val)

    # add the case env one item at a time.
    # sorted because we want expansion to be deterministic;
    # TODO: should probably expand everything with just the builtins;
    # otherwise would need some dependency resolution between vars.
    if self.env:
      for key, val in sorted(self.env.items()):
        if key in env:
          raiseF('specified env contains reserved key: {}', key)
        env[key] = expand_str(val)

    self.compile_cmds = [expand(cmd) for cmd in self.compile] if self.compile else []

    args = expand(self.args)
    if self.cmd:
      self.test_cmd = expand(self.cmd) + (args or [])
    elif self.compile_cmds:
      self.test_cmd = ['./' + self.name] + (args or [])
    elif len(self.dflt_src_paths) > 1:
      raiseF('no `cmd` specified and multiple default source paths found: {}', self.dflt_src_paths)
    elif len(self.dflt_src_paths) < 1:
      raiseF('no `cmd` specified and no default source path found')
    else:
      dflt_path = self.dflt_src_paths[0]
      self.test_cmd = [abs_path(dflt_path)] + (args or [])

    if not self.is_isolated and self.links:
      raiseF("non-isolated tests ('dir' specified) cannot also specify 'links'")
    if self.links is None:
      self.test_links = []
    elif is_str(self.links):
      link = expand_str(self.links)
      self.test_links = [(link, path_name(link))]
    elif is_set(self.links):
      self.test_links = sorted((n, path_name(n)) for n in map(expand_str, self.links))
    elif is_dict(self.links):
      self.test_links = sorted((expand_str(orig), expand_str(link)) for orig, link in self.links.items())
    else:
      raise ValueError(self.links)

    self.coverage_targets = expand(self.coverage)

    self.test_in = expand_str(self.in_) if self.in_ is not None else None

    self.test_expectations = []

    def add_std_exp(name, mode, path, val):
      info = {}
      if mode is not None: info['mode'] = mode
      if path is not None: info['path'] = path
      if val is not None: info['val'] = val
      exp = FileExpectation(self.std_name(name), info, expand_str)
      self.test_expectations.append(exp)

    add_std_exp('err', self.err_mode, self.err_path, self.err_val)
    add_std_exp('out', self.out_mode, self.out_path, self.out_val)

    for path, info in (self.files or {}).items():
      exp = FileExpectation(path, info, expand_str)
      self.test_expectations.append(exp)



def is_int_or_ellipsis(val):
  return val is Ellipsis or is_int(val)

def is_compile_cmd(val):
  return is_list(val) and all(is_str_or_list(el) for el in val)

def is_valid_links(val):
  return is_str(val) or is_set_of_str(val) or is_dict_of_str(val)

def validate_dir(key, dir):
  if not dir: raiseF('key: {}: custom directory is empty: {!r}', key, dir)
  if '.' in dir: raiseF("key: {}: custom directory cannot contain '.': {!r}", key, dir)

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
  if not is_dict(val):
    raiseF('file expectation: {}: value must be a dictionary.', key)
  for k, exp_dict in val.items():
    if k in ('out', 'err'):
      raiseF('key: {}: {}: use the standard properties instead ({}_mode, {}_path, {}_val).',
        key, k, k, k, k)
    validate_exp_dict(k, exp_dict)

def validate_links_dict(key, val):
  if is_str(val):
    items = [(val, val)]
  elif is_set(val):
    items = [(p, p) for p in val]
  elif is_dict(val):
    items = val.items()
  else: raise AssertionError('`validate_links_dict` types inconsistent with `is_valid_links`.')
  for orig, link in items:
    if orig.find('..') != -1: raiseF("key: {}: link original contains '..': {}", key, src)
    if link.find('..') != -1: raiseF("key: {}: link location contains '..': {}", key, dst)


case_key_validators = { # key => msg, validator_predicate, validator_fn.
  'args':     ('string or list of strings', is_str_or_list,     None),
  'cmd':      ('string or list of strings', is_str_or_list,     None),
  'code':     ('int or `...`',              is_int_or_ellipsis, None),
  'compile':  ('list of (str | list of str)', is_compile_cmd,   None),
  'compile_timeout': ('positive int',       is_pos_int,         None),
  'coverage': ('string or list of strings', is_str_or_list,     None),
  'dir':      ('str',                       is_str,             validate_dir),
  'desc':     ('str',                       is_str,             None),
  'env':      ('dict of strings',           is_dict_of_str,     None),
  'err_mode': ('str',                       is_str,             validate_exp_mode),
  'err_path': ('str',                       is_str,             None),
  'err_val':  ('str',                       is_str,             None),
  'files':    ('dict',                      is_dict,            validate_files_dict),
  'in_':      ('str',                       is_str,             None),
  'links':    ('string or (dict | set) of strings', is_valid_links, validate_links_dict),
  'out_mode': ('str',                       is_str,             validate_exp_mode),
  'out_path': ('str',                       is_str,             None),
  'out_val':  ('str',                       is_str,             None),
  'skip':     ('bool',                      is_bool,            None),
  'timeout':  ('positive int',              is_pos_int,         None),
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
    if self.mode == 'match':
      self.match_pattern_pairs = self.compile_match_lines(self.val)
    else:
      self.match_pattern_pairs = None
    self.match_error = None


  def compile_match_lines(self, text):
    return [self.compile_match_line(i, line) for i, line in enumerate(text.splitlines(True), 1)]


  def compile_match_line(self, i, line):
    prefix = line[:2]
    contents = line[2:]
    valid_prefixes = ('|', '|\n', '| ', '~', '~\n', '~ ')
    if prefix not in valid_prefixes:
      raise ValueError("test expectation: {!r};\nmatch line {}: must begin with one of: {}\n{!r}".format(
        self.path, i, ', '.join(repr(p) for p in valid_prefixes), line))
    if prefix.endswith('\n'):
      # these two cases exist to be lenient about empty lines,
      # where otherwise the pattern line would consist of the symbol and a single space.
      # since trailing space is highlighted by `git diff` and often considered bad style,
      # we allow it to be omitted, since there is no loss of generality for the patterns.
      contents = '\n'
    try:
      return (line, re.compile(contents if prefix == '~ ' else re.escape(contents)))
    except Exception as e:
      raise ValueError('test expectation: {!r};\nmatch line {}: pattern is invalid regex:\n{!r}\n{}'.format(
        self.path, i, contents, e)) from e


  def __repr__(self):
    return 'FileExpectation({!r}, {!r}, {!r})'.format(self.path, self.mode, self.val)


def try_case(ctx, case):
  try:
    ok = run_case(ctx, case)
  except Exception as e:
    t = type(e)
    outFL('\niotest: could not run test case: {}.\n  exception: {}.{}: {}',
      case.stem, t.__module__, t.__qualname__, e)
    ctx.fail_fast(e)
    ok = False
  if not ok:
    if case.desc: outSL('description:', case.desc)
    outL('=' * bar_width, '\n')
  if not ok: ctx.fail_fast()
  return ok


def run_case(ctx, case):
  outF('{:{bar_width}}', case.stem, flush=True, bar_width=(bar_width if ctx.show_times else 1))
  if ctx.dbg:
    errL()
    case.describe(stderr)

  # set up directory.
  if path_exists(case.test_dir):
    if not is_dir(case.test_dir): # could be a symlink; do not want to remove contents of link destination.
      raiseF('test directory already exists as a non-directory: {}', case.test_dir)
    if case.is_isolated:
      remove_dir_contents(case.test_dir)
    else: # remove just the known outputs.
      for std_path in [path_join(case.test_dir, case.std_name(n)) for n in ('err', 'out')]:
        remove_file_if_exists(std_path)
      # otherwise this test is assumed to depend on state from previous tests.
  else:
    make_dirs(case.test_dir)

  for orig, link in case.test_links:
    orig_path = path_join(ctx.proj_dir, orig)
    link_path = path_join(case.test_dir, link)
    if path_dir(link):
      raiseF('symlink is a path: {}', link) # TODO: make parent dirs for link_path?
    if is_node_not_link(link_path): # do not allow symlinks to overwrite previous contents in test dir.
      raiseF('non-symlink already exists at desired symlink path: {}', link_path)
    os.symlink(orig_path, link_path)

  compile_time = 0
  compile_time_start = time.time()
  for i, compile_cmd in enumerate(case.compile_cmds):
    compile_out_path = path_join(case.test_dir, case.std_name('compile-out-{:02}'.format(i)))
    compile_err_path = path_join(case.test_dir, case.std_name('compile-err-{:02}'.format(i)))
    status = run_cmd(ctx,
      case=case,
      label='compile',
      cmd=compile_cmd,
      cwd=case.test_dir,
      env=case.test_env,
      in_path='/dev/null',
      out_path=compile_out_path,
      err_path=compile_err_path,
      timeout=(case.compile_timeout or dflt_timeout),
      exp_code=0)
    compile_time = time.time() - compile_time_start
    if not status:
      outFL('\ncompile step {} failed: `{}`', i, shell_cmd_str(compile_cmd))
      if status is not None: # not aborted; output is interesting.
        cat_file(compile_out_path, color=TXT_R)
        cat_file(compile_err_path, color=TXT_R)
      return False

  if case.in_ is not None:
    # TODO: if specified as a .in file, just read from that location,
    # instead of reading/writing text from/to disk.
    in_path = path_join(case.test_dir, 'in')
    write_to_path(in_path, case.in_)
  else:
    in_path = '/dev/null'
  if ctx.dbg: errSL('input path:', in_path)

  if case.code is None:
    exp_code = 1 if case.err_val else 0
  else:
    exp_code = case.code

  test_time_start = time.time()
  status = run_cmd(ctx,
    case=case,
    label='test',
    cmd=case.test_cmd,
    cwd=case.test_dir,
    env=case.test_env,
    in_path=in_path,
    out_path=path_join(case.test_dir, case.std_name('out')),
    err_path=path_join(case.test_dir, case.std_name('err')),
    timeout=(case.timeout or dflt_timeout),
    exp_code=exp_code)
  test_time = time.time() - test_time_start
  if not status:
    outFL('test command failed: `{}`', shell_cmd_str(case.test_cmd))

  if ctx.show_times:
    compile_time_msg = '; compile: {:.2f}'.format(compile_time) if compile_time else ''
    outFL(' {:.2f} sec{}.', test_time, compile_time_msg)
  else:
    outL()

  if status is None:
    return False

  # use a list comprehension to ensure that we always report all failed expectations.
  exps_ok = all([check_file_exp(ctx, case.test_dir, exp) for exp in case.test_expectations])
  return status and exps_ok


def run_cmd(ctx, case, label, cmd, cwd, env, in_path, out_path, err_path, timeout, exp_code):
  'returns True for success, False for failure, and None for abort.'
  cmd_head = cmd[0]
  is_cmd_installed = not path_dir(cmd_head) # command is a name, presumably a name on the PATH (or else a mistake).
  if ctx.coverage and not is_cmd_installed and is_python3_file(cmd_head): # interpose the coverage harness.
    ctx.coverage_cases.append(case)
    cmd = case.cove_cmd_prefix + cmd
    msg_cmd = None # do not offer possible test fixes while in coverage mode.
  elif is_cmd_installed:
    msg_cmd = None
  else: # command is a path, either local or absolute.
    msg_cmd = path_rel_to_current_or_abs(cmd_head)

  if ctx.dbg:
    cmd_str = '{} <{} # 1>{} 2>{}'.format(shell_cmd_str(cmd),
      shlex.quote(in_path), shlex.quote(out_path), shlex.quote(err_path))
    errSL(label, 'cwd:', cwd)
    errSL(label, 'cmd:', cmd_str)

  with open(in_path, 'r') as i, open_new(out_path) as o, open_new(err_path) as e:
    try:
      run(cmd, cwd=cwd, env=env, stdin=i, out=o, err=e, timeout=timeout, exp=exp_code)
    except PermissionError:
      outFL('\n{} process permission error; make sure that you have proper ownership and permissions to execute set.', label)
      if msg_cmd: outFL('possible fix: `chmod +x {}`', shlex.quote(msg_cmd))
      return None
    except OSError as e:
      first_line = read_first_line_from_path(cmd_head, default=None)
      if e.strerror == 'Exec format error':
        outFL('\n{} process file format is not executable.', label)
        if msg_cmd and first_line is not None and not first_line.startswith('#!'):
          outFL('note: the test script does not start with a hash-bang line, e.g. `#!/usr/bin/env [INTERPRETER]`.')
      elif e.strerror.startswith('No such file or directory:'):
        if first_line is None: # really does not exist.
          outFL('\n{} command path does not exist: {}', label, (msg_cmd or cmd_head))
        elif is_cmd_installed: # exists but not referred to as a path.
          outFL("\n{} command path exists but is missing a leading './'.", label)
        else:
          outFL('\n{} command path exists but failed, possibly due to a bad hashbang line.', label)
          outFL('first line: {!r}', first_line.rstrip('\n'))
      else:
        outFL('\n{} process OS error {}: {}.', label, e.errno, e.strerror)
      return None
    except ProcessTimeout:
      outFL('\n{} process timed out ({} sec) and was killed.', label, timeout)
      return None
    except ProcessExpectation as e:
      outFL('\n{} process was expected to return code: {}; actual code: {}.', label, e.exp, e.act)
      return False
    else:
      return True
    assert False # protect against missing return above.


def check_file_exp(ctx, test_dir, exp):
  'return True if expectation is met.'
  if ctx.dbg: errFL('check_file_exp: {}', exp)
  path = path_join(test_dir, exp.path)
  try:
    with open(path) as f:
      act_val = f.read()
  except Exception as e:
    outFL('\niotest: could not read test output file: {}\n  exception: {!r}', path, e)
    ctx.fail_fast(e)
    outSL('-' * bar_width)
    return False
  if file_expectation_fns[exp.mode](exp, act_val):
    return True
  outFL('\noutput file does not {} expectation. actual value:', exp.mode)
  cat_file(path, color=TXT_B)
  if not exp.val:
    outFL('Expected empty file.')
    return False
  if exp.mode == 'equal': # show a diff.
    path_expected = path + '-expected'
    write_to_path(path_expected, exp.val)
    cmd = diff_cmd + [rel_path(path_expected), rel_path(path)]
    outSL(*cmd)
    run(cmd, exp=None)
  elif exp.mode == 'match':
    act_lines = act_val.splitlines(True)
    i, exp_pattern, act_line = exp.match_error
    outFL('match failed at line {}:\npattern:   {!r}\nactual text: {!r}',
      i, exp_pattern, act_line)
  outSL('-' * bar_width)
  return False


diff_cmd = 'git diff --no-index --no-prefix --no-renames --exit-code --histogram --ws-error-highlight=old,new'.split()


def cat_file(path, color='', limit=-1):
  outL(TXT_D, 'cat ', rel_path(path), RST)
  rst = RST if color else ''
  with open(path) as f:
    line = None
    for i, line in enumerate(f, 1):
      l = line.rstrip('\n')
      outL(color, l, rst)
      if i == limit: return
    if line is not None and not line.endswith('\n'):
      outL('(missing final newline)')


# file expectation functions.

def compare_equal(exp, val):
  return exp.val == val

def compare_contain(exp, val):
  return val.find(exp.val) != -1

def compare_match(exp, val):
  pairs = exp.match_pattern_pairs # pairs of pattern, regex.
  lines = val.splitlines(True)
  for i, (pair, line) in enumerate(zip_longest(pairs, lines), 1):
    if pair is None:
      exp.match_error = (i, None, line)
      return False
    (pattern, regex) = pair
    if line is None or not regex.fullmatch(line):
      exp.match_error = (i, pattern, line)
      return False
  return True


def compare_ignore(exp, val):
  return True


file_expectation_fns = {
  'equal'   : compare_equal,
  'contain' : compare_contain,
  'match'   : compare_match,
  'ignore'  : compare_ignore,
}


def shell_cmd_str(cmd): return ' '.join(shlex.quote(word) for word in cmd)

if __name__ == '__main__': main()
