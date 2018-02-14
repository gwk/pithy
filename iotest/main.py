# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import argparse
import shlex
import time

from sys import stdout, stderr
from typing import *

from .pithy.ansi import RST_OUT, TXT_B_OUT, TXT_D_OUT, TXT_R_OUT
from .pithy.io import errL, errSL, outL, outSL, outZ, read_from_path, read_line_from_path, write_to_path, writeLSSL
from .pithy.string import string_contains
from .pithy.format import FormatError, format_to_re
from .pithy.fs import *
from .pithy.iterable import fan_by_key_fn, fan_by_pred
from .pithy.task import TaskLaunchError, UnexpectedExit, Timeout, run, runC
from .pithy.types import is_bool, is_dict_of_str, is_dict, is_int, is_list, is_pos_int, is_set, is_set_of_str, is_str, is_str_or_list, req_type

from .case import Case, FileExpectation, TestCaseError, file_expectation_fns
from .ctx import Ctx


bar_width = 64
dflt_build_dir = '_build'
dflt_timeout = 4


def main() -> None:
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
    def fail_fast(e:Exception=None) -> None:
      errL('\nfail_fast:')
      raise Exception('iotest: stopping after error (-dbg).') from e
  elif args.fail_fast:
    def fail_fast(e:Exception=None) -> None: exit('iotest: stopping after error (-fail-fast).')
  else:
    def fail_fast(e:Exception=None) -> None: pass

  ctx = Ctx(
    build_dir=build_dir,
    coverage=args.coverage,
    dbg=args.dbg,
    fail_fast=fail_fast,
    parse_only=args.parse_only,
    proj_dir=proj_dir,
    show_times=(not args.no_times),
    top_paths=tuple(args.paths))

  cases_dict: Dict[str, Case] = {} # keyed by actual path stem, as opposed to logical contraction of 'd/_' to 'd'.

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
  coverage_cases: List[Case] = []

  # check that there are no overlapping logical stems.
  logical_stems: Set[str] = set()
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
      ok = try_case(ctx, coverage_cases, case)
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
    report_coverage(coverage_cases)
  else:
    exit(code)


def collect_proto(ctx: Ctx, end_dir_path: str) -> Optional[Case]:
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


def collect_cases(ctx:Ctx, cases_dict:Dict[str, Case], proto: Optional[Case], dir_path: str, specified_name_prefix: Optional[str]) -> None:
  '''
  Recursively find all test cases within the directory tree rooted at `dir_path`,
  and collect them into `cases_dict`.
  '''
  sub_dirs = []
  file_paths = []
  names = list_dir(dir_path)
  trivial: List[str] = [] # Either empty, or contains just the default case stem.
  for name in names:
    if name.startswith('.'): # ignore hidden files.
      continue
    path = path_join(dir_path, name)
    if specified_name_prefix is None: # collect dirs.
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
  if specified_name_prefix is None: # collect dirs.
    for sub_dir in sub_dirs:
      collect_cases(ctx, cases_dict, default, sub_dir, None)
  elif file_paths == trivial:
    p = dir_path + specified_name_prefix
    exit(f'iotest error: argument path does not match any files: {p!r}.')


def create_proto_case(ctx:Ctx, proto: Optional[Case], stem: str, file_paths: List[str]) -> Optional[Case]:
  if not file_paths:
    return proto
  default = Case(ctx, proto, stem, file_paths, wild_paths_to_re={}, wild_paths_used=set())
  if default.broken: ctx.fail_fast()
  return default


def create_cases(ctx:Ctx, cases_dict:Dict[str, Case], parent_proto: Optional[Case], dir_path: str, file_paths: List[str]) -> Optional[Case]:
  '''
  Create Case objects from the paths in the given directory.
  Each case is defined by the collection of file paths that share a common stem (which implies the case name)
  and have one of the designated test case extensions.

  ## Multicases (NOT YET IMPLEMENTED!)
  A `.iot` file may contain a single case definition, or alternatively a list of definitions.
  A list implies a series of tests which are consecutively named `<stem>.<index>`.

  ## Parameterized files
  A case file may contain `{` (indicating a python format string) and will then be interpreted as a parameterized name
  that applies over multiple cases.
  Each case must have one non-parameterized contributing file; otherwise there is no way to infer its existence.
  '''
  # Note: "wild" as written in the code means parameterized paths.
  regular_paths, wild_paths = fan_by_pred(file_paths, pred=lambda p: '{' in p)
  wild_paths_to_re: Dict[str, Pattern[str]] = dict(filter(None, map(compile_wild_path_re, wild_paths)))
  wild_paths_used: Set[str] = set()
  groups = fan_by_key_fn(regular_paths, key=path_stem)
  # default.
  default_stem = dir_path + '_default'
  proto = create_proto_case(ctx, proto=parent_proto, stem=default_stem, file_paths=groups.get(default_stem, []))
  # cases.
  for (stem, paths) in sorted(groups.items()):
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


def compile_wild_path_re(path: str) -> Optional[Tuple[str, Pattern[str]]]:
  try: return (path, format_to_re(path_stem(path)))
  except FormatError as e:
    outL(f'iotest WARNING: invalid format path will be ignored: {path}')
    outL('  NOTE: ', e)
    return None


implied_case_exts = ('.iot', '.out', '.err')

def is_case_implied(paths: Iterable[str]) -> bool:
  'one of the standard test file extensions must be present to imply a test case.'
  for p in paths:
    if path_ext(p) in implied_case_exts: return True
  return False


def report_coverage(coverage_cases: List[Case]) -> None:
  if not coverage_cases:
    exit('No coverage generated by tests.')
  def cov_path(case: Case) -> str:
    return path_rel_to_current_or_abs(path_join(case.test_dir, case.coverage_path))
  cmd = ['coven', '-coalesce'] + [cov_path(case) for case in coverage_cases]
  outL()
  outSL('#', *cmd)
  stdout.flush()
  exit(runC(cmd))


def try_case(ctx:Ctx, coverage_cases:List[Case], case: Case) -> bool:
  try:
    ok = run_case(ctx, coverage_cases, case)
  except TestCaseError as e:
    t = type(e)
    outL(f'\niotest: could not run test case: {case.stem}.\n  exception: {t.__module__}.{t.__qualname__}: {e}')
    ctx.fail_fast(e)
    ok = False
  if not ok:
    if case.desc: outSL('description:', case.desc)
    outL('=' * bar_width, '\n')
  if not ok: ctx.fail_fast()
  return ok


def run_case(ctx:Ctx, coverage_cases:List[Case], case: Case) -> bool:
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
    make_link(orig=orig_path, link=link_path)

  compile_time = 0.0
  compile_time_start = time.time()
  for i, compile_cmd in enumerate(case.compile_cmds):
    compile_out_path = path_join(case.test_dir, case.std_name('compile-out-{:02}'.format(i)))
    compile_err_path = path_join(case.test_dir, case.std_name('compile-err-{:02}'.format(i)))
    status = run_cmd(ctx,
      coverage_cases=None, # compile commands do not run via coverage harness.
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
    coverage_cases=coverage_cases,
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


def run_cmd(ctx:Ctx, coverage_cases: Optional[List[Case]], case: Case, label: str, cmd: List[str], cwd: str, env: Dict[str, str], in_path: str, out_path: str, err_path: str, timeout: int, exp_code: int) -> Optional[bool]:
  'returns True for success, False for failure, and None for abort.'
  cmd_head = cmd[0]
  cmd_path = path_rel_to_current_or_abs(cmd_head) # For diagnostics.
  is_cmd_installed = not path_dir(cmd_head) # command is a name, presumably a name on the PATH (or else a mistake).

  if ctx.coverage and coverage_cases is not None and not is_cmd_installed and is_python_file(cmd_head): # interpose the coverage harness.
    coverage_cases.append(case)
    cmd = case.coven_cmd_prefix + cmd

  if ctx.dbg:
    cmd_str = '{} <{} # 1>{} 2>{}'.format(shell_cmd_str(cmd),
      shlex.quote(in_path), shlex.quote(out_path), shlex.quote(err_path))
    errSL(label, 'cwd:', cwd)
    errSL(label, 'cmd:', cmd_str)

  with open(in_path, 'rb') as i, open_new(out_path) as o, open_new(err_path) as e:
    try:
      run(cmd, cwd=cwd, env=env, stdin=i, out=o, err=e, timeout=timeout, exp=exp_code)
      return True
    except UnexpectedExit as e:
      outL(f'\n{label} process was expected to return code: {e.exp}; actual code: {e.act}.')
      return False
    except TaskLaunchError as e:
      outL(f'\n{label} process launch failed; {e.diagnosis}')
#        outL(f'note: is the command installed?')
#          outL(f'note: command path refers to a {status.type_desc}.')
#          outL(f'note: permission error; make sure that you have set proper ownership and executable permissions.')
#          outL(f'note: possible fix: `chmod +x {shlex.quote(cmd_path)}`')
#        outL('note: test script does not start with a hash-bang line, e.g. `#!/usr/bin/env [INTERPRETER]`.')
#       outL(f'note: test script has a hash-bang line; is it mistyped?')
    except Timeout:
      outL(f'\n{label} process timed out ({timeout} sec) and was killed.')
    return None


def check_file_exp(ctx:Ctx, test_dir: str, exp: FileExpectation) -> bool:
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
  is_empty = not act_val
  outL(f'\noutput file does not {exp.mode} expectation. actual value:', (" ''" if is_empty else ''))
  if not is_empty: cat_file(path, color=TXT_B_OUT)
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
    assert exp.match_error is not None
    i, exp_pattern, act_line = exp.match_error
    outL(f'match failed at line {i}:\npattern:   {exp_pattern!r}\nactual text: {act_line!r}')
  outSL('-' * bar_width)
  return False


diff_cmd = 'git diff --no-index --no-prefix --no-renames --exit-code --histogram --ws-error-highlight=old,new'.split()


def cat_file(path: str, color: str, limit=-1) -> None:
  outL(TXT_D_OUT, 'cat ', rel_path(path), RST_OUT)
  with open(path) as f:
    line = None
    for i, line in enumerate(f, 1):
      l = line.rstrip('\n')
      outL(color, l, RST_OUT)
      if i == limit: return #!cov-ignore.
    if line is not None and not line.endswith('\n'):
      outL('(missing final newline)') #!cov-ignore.


def shell_cmd_str(cmd: List[str]) -> str: return ' '.join(shlex.quote(word) for word in cmd)
