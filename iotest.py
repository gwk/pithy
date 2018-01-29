#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import argparse
import ast
import os
import re
import shlex
import time

from itertools import zip_longest
from string import Template
from sys import stdout, stderr

from pithy.ansi import RST_OUT, TXT_B_OUT, TXT_D_OUT, TXT_R_OUT
from pithy.immutable import Immutable
from pithy.io import errL, errSL, outL, outSL, outZ, read_from_path, read_line_from_path, write_to_path, writeLSSL
from pithy.string import string_contains
from pithy.format import FormatError, format_to_re
from pithy.fs import (abs_path, find_project_dir, is_dir, is_node_not_link, is_python_file, list_dir, open_new, make_dirs, norm_path,
  path_descendants, path_dir, path_dir_or_dot, path_exists, path_ext, path_join,
  path_name, path_name_stem, path_rel_to_current_or_abs, path_stem, rel_path, remove_dir_contents, remove_file_if_exists, walk_dirs_up)
from pithy.iterable import fan_by_key_fn, fan_by_pred
from pithy.task import UnexpectedExit, Timeout, run, runC
from pithy.types import is_bool, is_dict_of_str, is_dict, is_int, is_list, is_pos_int, is_set, is_set_of_str, is_str, is_str_or_list, req_type

bar_width = 64
dflt_build_dir = '_build'
dflt_timeout = 4
coverage_name = '_.coven'

def main():
  start_time = time.time()
  arg_parser = argparse.ArgumentParser(description='iotest: a simple file-based test harness.')
  arg_parser.add_argument('-build-dir')
  arg_parser.add_argument('-parse-only', action='store_true', help='parse test cases and exit.')
  arg_parser.add_argument('-coverage', action='store_true', help='use coven to trace test coverage.')
  arg_parser.add_argument('-no-coverage-report', action='store_true', help='do not report coverage.')
  arg_parser.add_argument('-no-times', action='store_true', help='do not report test times.')
  arg_parser.add_argument('-fail-fast',  action='store_true', help='exit on first error; implied by -dbg.')
  arg_parser.add_argument('-dbg', action='store_true', help='debug mode: print extra info; implies -fast).')
  arg_parser.add_argument('paths', nargs='*', default=['test'], help='test directories to search.')
  args = arg_parser.parse_args()

  if args.dbg: errL('iotest: DEBUG MODE ON.')

  if not args.coverage and args.no_coverage_report:
    exit('iotest error: `-no-coverage-report` is only valid in combination with `-coverage`.')

  proj_dir = find_project_dir()
  if proj_dir is None:
    exit("iotest error: could not find .git or .project-root in current directory or its parents.")

  build_dir = args.build_dir or path_join(proj_dir, dflt_build_dir)

  if args.dbg:
    def fail_fast(e=None):
      errL('\nfail_fast:')
      raise Exception('iotest: stopping after error (-dbg).') from e
  elif args.fail_fast:
    def fail_fast(e=None): exit('iotest: stopping after error (-fail-fast).')
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

  cases_dict = {} # keyed by actual path stem, as opposed to logical contraction of 'd/_' to 'd'.

  for raw_path in ctx.top_paths:
    path = norm_path(raw_path)
    if string_contains(path, '..'):
      # because we recreate the dir structure in the results dir, parent dirs are forbidden.
      exit(f"iotest error: argument path cannot contain '..': {path!r}.")
    if is_dir(path):
      dir_path = path + '/'
      specified_name_prefix = None
    else:
      dir_path = path_dir_or_dot(path) + '/'
      if not is_dir(dir_path):
        exit('iotest error: argument path directory does not exist: {dir_path!r}.')
      specified_name_prefix = path_name_stem(path)
    proto = collect_proto(ctx, dir_path)
    collect_cases(ctx, cases_dict, proto, dir_path, specified_name_prefix)

  cases = sorted(cases_dict.values())
  # check that there are no overlapping logical stems.
  logical_stems = set()
  for case in cases:
    if case.stem in logical_stems:
      exit(f'iotest error: repeated logical stem: {case.stem}')
    logical_stems.add(case.stem)

  broken_count = 0
  skipped_count = 0
  failed_count = 0
  for case in cases:
    if case.broken:
      broken_count += 1
    elif case.skip:
      skipped_count += 1
      outL(f'{case.stem:{bar_width}} SKIPPED.')
    elif ctx.parse_only:
      continue
    else:
      ok = try_case(ctx, case)
      if not ok:
        failed_count += 1

  outL('\n', '#' * bar_width)
  count = len(cases)
  if ctx.parse_only:
    if broken_count:
      msg = f'TESTS FOUND: {count}; BROKEN: {broken_count}.'
      code = 1
    else:
      msg = f'TESTS PARSED: {count}.'
      code = 0
  else:
    if any([broken_count, failed_count]):
      msg = f'TESTS FOUND: {count}; BROKEN: {broken_count}; SKIPPED: {skipped_count}; FAILED: {failed_count}.'
      code = 1
    else:
      msg = f'TESTS FOUND: {count}; SKIPPED: {skipped_count}; PASSED: {count - skipped_count}.'
      code = 0
  total_time = time.time() - start_time
  if ctx.show_times:
    outL(f'{msg:{bar_width}} {total_time:.2f} sec.')
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


def collect_cases(ctx, cases_dict, proto, dir_path, specified_name_prefix):
  'find all test cases within the specified directory.'
  collect_dirs = (specified_name_prefix is None)
  sub_dirs = []
  file_paths = []
  names = list_dir(dir_path)
  trivial = []
  for name in names:
    if name.startswith('.'): # ignore hidden files.
      continue
    path = path_join(dir_path, name)
    if collect_dirs:
      if is_dir(path):
        sub_dirs.append(path + '/')
      else:
        file_paths.append(path)
    else:
      stem = path_stem(name)
      if stem == '_default':
        trivial = [path]
      if stem == '_default' or stem.startswith(specified_name_prefix):
        file_paths.append(path)
  default = create_cases(ctx, cases_dict, proto, dir_path, file_paths)
  if collect_dirs:
    for sub_dir in sub_dirs:
      collect_cases(ctx, cases_dict, default, sub_dir, None)
  elif file_paths == trivial:
    p = dir_path + specified_name_prefix
    exit(f'iotest error: argument path does not match any files: {p!r}.')


def create_proto_case(ctx, proto, stem, file_paths):
  if not file_paths:
    return proto
  default = Case(ctx, proto, stem, file_paths, wild_paths_to_re=[], wild_paths_used=set())
  if default.broken: ctx.fail_fast()
  return default


def create_cases(ctx, cases_dict, parent_proto, dir_path, file_paths):
  # wild paths are those whose name contain a '{', which are interpreted as python format strings.
  regular_paths, wild_paths = fan_by_pred(file_paths, pred=lambda p: '{' in p)
  wild_paths_to_re = dict(filter(None, map(compile_wild_path_re, wild_paths)))
  wild_paths_used = set()
  groups = fan_by_key_fn(regular_paths, key=path_stem)
  # default.
  default_stem = dir_path + '_default'
  proto = create_proto_case(ctx, parent_proto, default_stem, groups.get(default_stem))
  # cases.
  for (stem, paths) in sorted(p for p in groups.items() if p[0] is not None):
    if stem in cases_dict:
      errL(f'iotest note: repeated case stem: {stem}')
      continue
    if stem == default_stem or not is_case_implied(paths): continue
    case = Case(ctx, proto, stem, paths, wild_paths_to_re, wild_paths_used)
    if case.broken: ctx.fail_fast()
    cases_dict[stem] = case
  # check that all wild paths are used by some case.
  for path in wild_paths:
    if path_ext(path) in implied_case_exts and path not in wild_paths_used:
      outL(f'iotest note: wildcard file path was never used: {path}')
  return proto


def compile_wild_path_re(path):
  try: return (path, format_to_re(path_stem(path)))
  except FormatError as e:
    outL(f'iotest WARNING: invalid format path will be ignored: {path}')
    outL('  NOTE: ', e)
    return None


implied_case_exts = ('.iot', '.out', '.err')

def is_case_implied(paths):
  'one of the standard test file extensions must be present to imply a test case.'
  for p in paths:
    if path_ext(p) in implied_case_exts: return True
  return False


def report_coverage(ctx):
  if not ctx.coverage_cases:
    exit('No coverage generated by tests.')
  def cov_path(case):
    return path_rel_to_current_or_abs(path_join(case.test_dir, case.coverage_path))
  cmd = ['coven', '-coalesce'] + [cov_path(case) for case in ctx.coverage_cases]
  outL()
  outSL('#', *cmd)
  stdout.flush()
  exit(runC(cmd))


class IotParseError(Exception): pass


class Case:
  'Case represents a single test case, or a default.'

  def __init__(self, ctx, proto, stem, file_paths, wild_paths_to_re, wild_paths_used):
    self.stem = path_dir(stem) if path_name(stem) == '_' else stem # TODO: better naming for 'logical stem' (see code in main).
    self.name = path_name(self.stem)
    # derived properties.
    self.test_info_exts = set()
    self.test_info_paths = [] # the files that comprise the test case.
    self.dflt_src_paths = []
    self.broken = proto.broken if (proto is not None) else False
    self.coverage_targets = None
    self.test_dir = None
    self.test_cmd = None
    self.test_env = None
    self.test_in = None
    self.test_expectations = None
    self.test_links = None # sequence of (orig-name, link-name) pairs.
    self.test_wild_args = {} # the match groups that resulted from applying the regex.
    # configurable properties.
    self.args = None # arguments to follow the file under test.
    self.cmd = None # command string/list with which to invoke the test.
    self.coverage = None # list of string/list of names to include in code coverage analysis.
    self.code = None # the expected exit code.
    self.compile = None # the optional list of compile commands, each a string or list of strings.
    self.compile_timeout = None
    self.desc = None # description.
    self.env = None # environment variables.
    self.err_mode = None # comparison mode for stderr expectation.
    self.err_path = None # file path for stderr expectation.
    self.err_val = None # stderr expectation value (mutually exclusive with err_path).
    self.files = None # additional file expectations.
    self.in_ = None # stdin as text.
    self.interpreter = None # interpreter to prepend to cmd.
    self.interpreter_args = None # interpreter args.
    self.lead = None # specifies a 'lead' test; allows multiple tests to be run over same directory contents.
    self.links = None # symlinks to be made into the test directory; written as a str, set or dict.
    self.out_mode = None # comparison mode for stdout expectation.
    self.out_path = None # file path for stdout expectation.
    self.out_val = None # stdout expectation value (mutually exclusive with out_path).
    self.skip = None
    self.timeout = None

    def sorted_iot_first(paths):
      # Ensure that .iot files get added first, for clarity when conflicts arise.
      return sorted(paths, key=lambda p: '' if p.endswith('.iot') else p)

    try:
      if proto is not None:
        for key in case_key_validators:
          val = proto.__dict__[key]
          if val is None: continue
          self.add_val_for_key(ctx, key, val)

      # read in all file info specific to this case.
      for path in sorted_iot_first(file_paths):
        self.add_file(ctx, path)
      for wild_path in sorted_iot_first(wild_paths_to_re):
        ext = path_ext(wild_path)
        if ext in self.test_info_exts: continue
        wild_re = wild_paths_to_re[wild_path]
        m = wild_re.fullmatch(stem)
        if m:
          self.add_file(ctx, wild_path)
          self.test_wild_args[wild_path] = m.groups()
          wild_paths_used.add(wild_path)
      # do all additional computations now, so as to fail as quickly as possible.
      self.derive_info(ctx)

    except Exception as e:
      outL(f'WARNING: broken test case: {stem}')
      outL(f'  exception: {type(e).__name__}: {e}.')
      # not sure if it makes sense to describe cases for some exceptions;
      # for now, just carve out the ones for which it is definitely useless.
      if not isinstance(e, IotParseError):
        self.describe(stdout)
        outL()
      ctx.fail_fast(e)
      self.broken = True

  def __repr__(self): return f'Case(stem={self.stem!r}, ...)'

  def __lt__(self, other): return self.stem < other.stem

  @property
  def is_lead(self): return self.lead is None or self.lead == self.stem

  @property
  def coverage_path(self):
    'Returned path is relative to self.test_dir.'
    return self.std_name(coverage_name)

  @property
  def coven_cmd_prefix(self):
    coven_cmd = ['coven', '-output', self.coverage_path]
    if self.coverage_targets:
      coven_cmd += ['-targets'] + self.coverage_targets
    coven_cmd.append('--')
    return coven_cmd

  def std_name(self, std: str) -> str: return f'{self.name}.{std}'

  def describe(self, file):
    def stable_repr(val):
      if is_dict(val):
        return '{{{}}}'.format(', '.join('{!r}:{!r}'.format(*p) for p in sorted(val.items())))
      return repr(val)

    items = sorted(self.__dict__.items())
    writeLSSL(file, 'Case:', *('{}: {}'.format(k, stable_repr(v)) for k, v in items))


  def add_file(self, ctx, path):
    ext = path_ext(path)
    if ext == '.iot':   self.add_iot_file(ctx, path)
    elif ext == '.in':  self.add_std_file(ctx, path, 'in_')
    elif ext == '.out': self.add_std_file(ctx, path, 'out')
    elif ext == '.err': self.add_std_file(ctx, path, 'err')
    else:
      self.dflt_src_paths.append(path)
      return # other extensions are not part of info collections.
    self.test_info_paths.append(path)
    self.test_info_exts.add(ext)


  def add_std_file(self, ctx, path, key):
    text = read_from_path(path)
    self.add_val_for_key(ctx, key + '_val', text)


  def add_iot_file(self, ctx, path):
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
      self.add_iot_val_for_key(ctx, *kv)


  def add_val_for_key(self, ctx, key, val):
    if ctx.dbg:
      existing = self.__dict__[key]
      if existing is not None:
        errL(f'note: {self.stem}: overriding value for key: {key!r};\n  existing: {existing!r};\n  incoming: {val!r}')
    self.__dict__[key] = val


  def add_iot_val_for_key(self, ctx, iot_key, val):
    key = ('in_' if iot_key == 'in' else iot_key.replace('-', '_'))
    try:
      exp_desc, predicate, validator_fn = case_key_validators[key]
    except KeyError:
      raise Exception(f'invalid key in .iot file: {iot_key!r}')
    if not predicate(val):
      raise Exception(f'key: {iot_key!r}: expected value of type: {exp_desc}; received: {val!r}')
    if validator_fn:
      validator_fn(key, val)
    self.add_val_for_key(ctx, key, val)


  def derive_info(self, ctx):
    if self.name == '_default': return # do not process prototype cases.
    if self.lead is None: # simple, isolated test.
      rel_dir = self.stem
    elif self.lead == self.stem: # this test is the leader.
      rel_dir = path_dir(self.stem)
    else: # this test is a follower.
      rel_dir = path_dir(self.stem)
      if path_dir(self.lead) != rel_dir:
        raise Exception(f'test specifies lead test in different directory: {rel_dir} != {path_dir(self.lead)}')
    self.test_dir = path_join(ctx.build_dir, rel_dir)
    self.test_env = {}
    env = self.test_env # local alias for convenience.
    env['BUILD'] = ctx.build_dir
    env['NAME'] = self.name
    env['PROJ'] = abs_path(ctx.proj_dir)
    env['SRC'] = self.dflt_src_paths[0] if len(self.dflt_src_paths) == 1 else 'NONE'
    env['STEM'] = self.stem
    env['DIR'] = path_dir(self.stem)

    def default_to_env(key):
      if key not in env and key in os.environ:
        env[key] = os.environ[key]

    default_to_env('HOME') # otherwise git fails with "error: Could not expand include path '~/.gitcinclude'".
    default_to_env('LANG') # necessary to make std file handles unicode-aware.
    default_to_env('NODE_PATH')
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
          raise Exception(f'specified env contains reserved key: {key}')
        env[key] = expand_str(val)

    self.compile_cmds = [expand(cmd) for cmd in self.compile] if self.compile else []

    cmd = []
    if self.interpreter:
      cmd += expand(self.interpreter)
    if self.interpreter_args:
      if not self.interpreter: raise Exception('interpreter_args specified without interpreter')
      cmd += expand(self.interpreter_args)

    self.test_links = []

    if self.cmd:
      cmd += expand(self.cmd)
    elif self.compile_cmds:
      cmd += ['./' + self.name]
    elif len(self.dflt_src_paths) > 1:
      raise Exception(f'no `cmd` specified and multiple default source paths found: {self.dflt_src_paths}')
    elif len(self.dflt_src_paths) < 1:
      raise Exception('no `cmd` specified and no default source path found')
    else:
      dflt_path = self.dflt_src_paths[0]
      dflt_name = path_name(dflt_path)
      self.test_links.append((dflt_path, dflt_name))
      prefix = '' if cmd else './'
      cmd.append(prefix + dflt_name)
      if self.args is None:
        wild_args = list(self.test_wild_args.get(dflt_path, ()))
        cmd += wild_args

    if self.args:
      cmd += expand(self.args) or []

    self.test_cmd = cmd

    if not self.is_lead and self.links:
      raise Exception("non-lead tests ('lead' specified and not equal to stem) cannot also specify 'links'")
    elif is_str(self.links):
      link = expand_str(self.links)
      self.test_links += [(link, path_name(link))]
    elif is_set(self.links):
      self.test_links += sorted((n, path_name(n)) for n in map(expand_str, self.links))
    elif is_dict(self.links):
      self.test_links += sorted((expand_str(orig), expand_str(link)) for orig, link in self.links.items())
    elif self.links is not None:
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

def validate_path(key, path):
  if not path: raise Exception(f'key: {key}: path is empty: {path!r}')
  if '.' in path: raise Exception(f"key: {key}: path cannot contain '.': {path!r}")

def validate_exp_mode(key, mode):
  if mode not in file_expectation_fns:
    raise Exception(f'key: {key}: invalid file expectation mode: {mode}')

def validate_exp_dict(key, val):
  if not is_dict(val):
    raise Exception(f'file expectation: {key}: value must be a dictionary.')
  for k in val:
    if k not in ('mode', 'path', 'val'):
      raise Exception(f'file expectation: {key}: invalid expectation property: {k}')


def validate_files_dict(key, val):
  if not is_dict(val):
    raise Exception(f'file expectation: {key}: value must be a dictionary.')
  for k, exp_dict in val.items():
    if k in ('out', 'err'):
      raise Exception(f'key: {key}: {k}: use the standard properties instead ({k}_mode, {k}_path, {k}_val).')
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
    if orig.find('..') != -1: raise Exception(f"key: {key}: link original contains '..': {src}")
    if link.find('..') != -1: raise Exception(f"key: {key}: link location contains '..': {dst}")


case_key_validators = { # key => msg, validator_predicate, validator_fn.
  'args':     ('string or list of strings', is_str_or_list,     None),
  'cmd':      ('string or list of strings', is_str_or_list,     None),
  'code':     ('int or `...`',              is_int_or_ellipsis, None),
  'compile':  ('list of (str | list of str)', is_compile_cmd,   None),
  'compile_timeout': ('positive int',       is_pos_int,         None),
  'coverage': ('string or list of strings', is_str_or_list,     None),
  'desc':     ('str',                       is_str,             None),
  'env':      ('dict of strings',           is_dict_of_str,     None),
  'err_mode': ('str',                       is_str,             validate_exp_mode),
  'err_path': ('str',                       is_str,             None),
  'err_val':  ('str',                       is_str,             None),
  'files':    ('dict',                      is_dict,            validate_files_dict),
  'in_':      ('str',                       is_str,             None),
  'interpreter': ('string or list of strings', is_str_or_list,  None),
  'interpreter_args': ('string or list of strings', is_str_or_list,  None),
  'lead':     ('str',                       is_str,             None),
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
      raise Exception(f"file expectation {path}: cannot contain '..'")
    self.path = path
    self.mode = info.get('mode', 'equal')
    validate_exp_mode(path, self.mode)
    try:
      exp_path = info['path']
    except KeyError:
      val = info.get('val', '')
    else:
      if 'val' in info:
        raise Exception(f'file expectation {path}: cannot specify both `path` and `val` properties')
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
    outL(f'\niotest: could not run test case: {case.stem}.\n  exception: {t.__module__}.{t.__qualname__}: {e}')
    ctx.fail_fast(e)
    ok = False
  if not ok:
    if case.desc: outSL('description:', case.desc)
    outL('=' * bar_width, '\n')
  if not ok: ctx.fail_fast()
  return ok


def run_case(ctx, case):
  if ctx.dbg: errL()
  _bar_width = (bar_width if ctx.show_times else 1)
  outZ(f'{case.stem:{_bar_width}}', flush=True)
  if ctx.dbg:
    outL() # terminate previous line.
    case.describe(stderr)

  # set up directory.
  if path_exists(case.test_dir):
    if not is_dir(case.test_dir): # could be a symlink; do not want to remove contents of link destination.
      raise Exception(f'test directory already exists as a non-directory: {case.test_dir}')
    if case.is_lead:
      remove_dir_contents(case.test_dir)
    else:
      # remove just the known outputs; test is assumed to depend on state from previous tests.
      for std_path in [path_join(case.test_dir, case.std_name(n)) for n in ('err', 'out')]:
        remove_file_if_exists(std_path)
  else:
    make_dirs(case.test_dir)

  for orig, link in case.test_links:
    orig_path = path_join(ctx.proj_dir, orig)
    link_path = path_join(case.test_dir, link)
    if path_dir(link):
      raise Exception(f'symlink is a path: {link}') # TODO: make parent dirs for link_path?
    if is_node_not_link(link_path): # do not allow symlinks to overwrite previous contents in test dir.
      raise Exception(f'non-symlink already exists at desired symlink path: {link_path}')
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
      outL(f'\ncompile step {i} failed: `{shell_cmd_str(compile_cmd)}`')
      if status is not None: # not aborted; output is interesting.
        cat_file(compile_out_path, color=TXT_R_OUT)
        cat_file(compile_err_path, color=TXT_R_OUT)
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
    outL(f'test command failed: `{shell_cmd_str(case.test_cmd)}`')

  if ctx.show_times:
    compile_time_msg = f'; compile: {compile_time:.2f}' if compile_time else ''
    outL(f' {test_time:.2f} sec{compile_time_msg}.')
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
  if ctx.coverage and not is_cmd_installed and is_python_file(cmd_head): # interpose the coverage harness.
    ctx.coverage_cases.append(case)
    cmd = case.coven_cmd_prefix + cmd
    cmd_path = None # do not offer possible test fixes while in coverage mode.
  elif is_cmd_installed:
    cmd_path = None
  else: # command is a path, either local or absolute.
    cmd_path = path_rel_to_current_or_abs(cmd_head)

  if ctx.dbg:
    cmd_str = '{} <{} # 1>{} 2>{}'.format(shell_cmd_str(cmd),
      shlex.quote(in_path), shlex.quote(out_path), shlex.quote(err_path))
    errSL(label, 'cwd:', cwd)
    errSL(label, 'cmd:', cmd_str)

  with open(in_path, 'r') as i, open_new(out_path) as o, open_new(err_path) as e:
    try:
      run(cmd, cwd=cwd, env=env, stdin=i, out=o, err=e, timeout=timeout, exp=exp_code)
    except PermissionError:
      outL(f'\n{label} process permission error; make sure that you have proper ownership and permissions to execute set.')
      if cmd_path: outL(f'possible fix `chmod +x {shlex.quote(cmd_path)}`')
      return None
    except OSError as e:
      first_line = read_line_from_path(cmd_head, default=None)
      if e.strerror == 'Exec format error':
        outL(f'\n{label} process file format is not executable.')
        if cmd_path and first_line is not None and not first_line.startswith('#!'):
          outL('note: the test script does not start with a hash-bang line, e.g. `#!/usr/bin/env [INTERPRETER]`.')
      elif e.strerror.startswith('No such file or directory:'):
        if first_line is None: # really does not exist.
          outL(f'\n{label} command path does not exist: {(cmd_path or cmd_head)}')
        elif is_cmd_installed: # exists but not referred to as a path.
          outL(f"\n{label} command path exists but is missing a leading './'.")
        else:
          outL(f'\n{label} command path exists but failed, possibly due to a bad hashbang line.')
          outSL('first line:', repr(first_line.rstrip('\n')))
      else:
        outL(f'\n{label} process OS error {e.errno}: {e.strerror}.')
      return None
    except Timeout:
      outL(f'\n{label} process timed out ({timeout} sec) and was killed.')
      return None
    except UnexpectedExit as e:
      outL(f'\n{label} process was expected to return code: {e.exp}; actual code: {e.act}.')
      return False
    else:
      return True
    assert False # protect against missing return above.


def check_file_exp(ctx, test_dir, exp):
  'return True if expectation is met.'
  if ctx.dbg: errL(f'check_file_exp: {exp}')
  path = path_join(test_dir, exp.path)
  # TODO: support binary files by getting read mode from test case.
  # Expected read mode could alse be indicated by using a bytes value for the expectation.
  try:
    with open(path, errors='replace') as f:
      act_val = f.read()
  except FileNotFoundError as e:
    outL(f'\niotest: test did not output expected file: {path}')
    return False
  except Exception as e:
    outL(f'\niotest: could not read test output file: {path}\n  exception: {e!r}')
    ctx.fail_fast(e)
    return False
  if file_expectation_fns[exp.mode](exp, act_val):
    return True
  outL(f'\noutput file does not {exp.mode} expectation. actual value:')
  cat_file(path, color=TXT_B_OUT)
  if not exp.val:
    outL('Expected empty file.')
    return False
  if exp.mode == 'equal': # show a diff.
    path_expected = path + '.expected'
    write_to_path(path_expected, exp.val)
    cmd = diff_cmd + [rel_path(path_expected), rel_path(path)]
    outL(TXT_D_OUT, ' '.join(cmd), RST_OUT)
    run(cmd, exp=None)
  elif exp.mode == 'match':
    act_lines = act_val.splitlines(True)
    i, exp_pattern, act_line = exp.match_error
    outL(f'match failed at line {i}:\npattern:   {exp_pattern!r}\nactual text: {act_line!r}')
  outSL('-' * bar_width)
  return False


diff_cmd = 'git diff --no-index --no-prefix --no-renames --exit-code --histogram --ws-error-highlight=old,new'.split()


def cat_file(path, color, limit=-1):
  outL(TXT_D_OUT, 'cat ', rel_path(path), RST_OUT)
  with open(path) as f:
    line = None
    for i, line in enumerate(f, 1):
      l = line.rstrip('\n')
      outL(color, l, RST_OUT)
      if i == limit: return #!cov-ignore.
    if line is not None and not line.endswith('\n'):
      outL('(missing final newline)') #!cov-ignore.


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
