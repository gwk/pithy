# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import argparse
import re
import shlex
import time
from ast import literal_eval
from collections import defaultdict
from sys import stderr, stdout
from typing import Pattern
from warnings import filterwarnings

from pithy.ansi import BG, FILL_OUT, gray26, INVERT, is_out_tty, RST_INVERT, sanitize_for_console, sgr, TTY_OUT
from pithy.dict import dict_fan_by_key_pred
from pithy.filenamefmt import FilenameFormatterError, fnf_str_has_formatter, regex_for_fnf_str
from pithy.fs import (copy_path, file_status, find_project_dir, is_dir, is_python_file, list_dir, make_dirs, make_link,
  open_new, path_exists, remove_dir_contents, remove_file_if_exists)
from pithy.io import confirm, errL, errSL, outL, outN, outSL, outZ, read_from_path, write_to_path
from pithy.iterable import fan_by_pred
from pithy.path import (abs_path, norm_path, path_descendants, path_dir, path_dir_or_dot, path_ext, path_exts, path_join,
  path_name_stem_sans_exts, path_rel_to_current_or_abs, path_stem_sans_exts, rel_path, split_dir_name)
from pithy.task import run, runC, TaskLaunchError, Timeout, UnexpectedExit

from ..case import Case, file_expectation_fns, FileExpectation, ParConfig, TestCaseError
from ..ctx import Ctx


filterwarnings('error', category=SyntaxWarning) # Fail on SyntaxWarning.


def main() -> None:
  start_time = time.time()
  arg_parser = argparse.ArgumentParser(description='iotest: a simple file-based test harness.')
  arg_parser.add_argument('paths', nargs='*', default=['test'], help='Test directories to search.')
  arg_parser.add_argument('-build-dir', help='Specify the build directory to use.')
  arg_parser.add_argument('-coverage', action='store_true', help='Use coven to trace test coverage.')
  arg_parser.add_argument('-dbg', action='store_true', help='Debug mode: print extra info; implies -fast.')
  arg_parser.add_argument('-fail-fast',  action='store_true', help='Exit on first error; implied by -dbg.')
  arg_parser.add_argument('-interactive', action='store_true', help='Interactively update failing tests.')
  arg_parser.add_argument('-no-coverage-report', action='store_true', help='Do not report coverage.')
  arg_parser.add_argument('-no-times', action='store_true', help='Do not report test times.')
  arg_parser.add_argument('-parse-only', action='store_true', help='Parse test cases and exit.')
  arg_parser.add_argument('-retest', action='store_true', help='Rerun previously failed tests.')

  args = arg_parser.parse_args()

  if args.dbg: errL('iotest: DEBUG MODE ON.')

  if not args.coverage and args.no_coverage_report:
    exit('iotest error: `-no-coverage-report` is only valid in combination with `-coverage`.')

  proj_dir = find_project_dir()
  if proj_dir is None:
    exit("iotest error: could not find .git or .project-root in current directory or its parents.")

  build_dir = args.build_dir or path_join(proj_dir, dflt_build_dir)

  if args.dbg:
    def fail_fast(e:Exception|None=None) -> None:
      errL('\nfail_fast:')
      raise Exception('iotest: stopping after error (-dbg).') from e
  elif args.fail_fast:
    def fail_fast(e:Exception|None=None) -> None: exit('iotest: stopping after error (-fail-fast).')
  else:
    def fail_fast(e:Exception|None=None) -> None: pass

  ctx = Ctx(
    build_dir=build_dir,
    coverage=args.coverage,
    dbg=args.dbg,
    fail_fast=fail_fast,
    interactive=args.interactive,
    parse_only=args.parse_only,
    proj_dir=proj_dir,
    show_times=(not args.no_times),
    top_paths=tuple(args.paths))

  cases_dict: dict[str, Case] = {} # keyed by actual path stem, as opposed to logical contraction of 'd/_' to 'd'.

  for raw_path in ctx.top_paths:
    path = norm_path(raw_path)
    if '..' in path:
      # because we recreate the dir structure in the results dir, parent dirs are forbidden.
      exit(f"iotest error: argument path cannot contain '..': {path!r}.")
    if is_dir(path, follow=True):
      dir_path = path + '/'
      specified_name_prefix = None
    else:
      dir_path = path_dir_or_dot(path) + '/'
      if not is_dir(dir_path, follow=True):
        exit('iotest error: argument path directory does not exist: {dir_path!r}.')
      specified_name_prefix = path_name_stem_sans_exts(path)
    proto = collect_proto(ctx, dir_path)
    collect_cases(ctx, cases_dict, proto, dir_path, specified_name_prefix)

  cases = sorted(cases_dict.values())
  coverage_cases: list[Case] = []

  # check that there are no overlapping logical stems.
  logical_stems: set[str] = set()
  for case in cases:
    if case.stem in logical_stems:
      exit(f'iotest error: repeated logical stem: {case.stem}')
    logical_stems.add(case.stem)

  count = len(cases)
  if ctx.parse_only:
    outL(f'TESTS PARSED: {count}.')
    exit()

  skipped_count = 0
  failed_count = 0
  for case in cases:
    if case.skip:
      skipped_count += 1
      outL(f'{case.stem:{bar_width}} SKIPPED.')
    elif args.retest and not case.test_failed_previously:
      if args.dbg: outL(f'{case.stem:{bar_width}} PREVIOUSLY PASSED.')
      skipped_count += 1
    else:
      ok = try_case(ctx, coverage_cases, case)
      if not ok:
        failed_count += 1

  outL('\n', '#' * bar_width)

  if failed_count:
    msg = f'TESTS FOUND: {count}; SKIPPED: {skipped_count}; FAILED: {failed_count}.'
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


def collect_proto(ctx: Ctx, end_dir_path: str) -> Case|None:
  '''
  Assemble the prototype test case information from files named `_default.*`,
  starting at the project root and traversing successive child directories up to `end_dir_path`.
  '''
  proto = None
  for dir_path in path_descendants(ctx.proj_dir, abs_path(end_dir_path), include_end=False):
    file_paths = [path_join(dir_path, name) for name in list_dir(dir_path) if path_stem_sans_exts(name) == '_default']
    cases_dict: dict[str, Case] = {}
    proto = create_cases(ctx, cases_dict, proto, dir_path, file_paths)
    assert not cases_dict, cases_dict
  return proto


def collect_cases(ctx:Ctx, cases_dict:dict[str, Case], proto: Case|None, dir_path: str, specified_name_prefix: str|None) -> None:
  '''
  Recursively find all test cases within the directory tree rooted at `dir_path`,
  and collect them into `cases_dict`.
  '''
  sub_dirs = []
  file_paths = []
  names = list_dir(dir_path)
  trivial: list[str] = [] # Either empty, or contains just the default case stem.
  for name in names:
    path = path_join(dir_path, name)
    if specified_name_prefix is None: # collect dirs.
      if is_dir(path, follow=True):
        sub_dirs.append(path + '/')
      elif path_ext(name):
        file_paths.append(path)
    else: # Look for specified_name_prefix; do not collect dirs.
      stem = path_stem_sans_exts(name)
      if stem == '_default':
        trivial = [path]
      if stem == '_default' or stem.startswith(specified_name_prefix):
        file_paths.append(path)
  sub_proto = create_cases(ctx, cases_dict, proto, dir_path, file_paths)
  if specified_name_prefix is None: # collect dirs.
    for sub_dir in sub_dirs:
      collect_cases(ctx, cases_dict, sub_proto, sub_dir, None)
  elif file_paths == trivial:
    p = dir_path + specified_name_prefix
    exit(f'iotest error: argument path does not match any files: {p!r}.')


def create_proto_case(ctx:Ctx, proto: Case|None, stem: str, config: dict) -> Case|None:
  if not config:
    return proto
  return Case(ctx, proto=proto, stem=stem, config=config, par_configs=[], par_stems_used=set())


def create_cases(ctx:Ctx, cases_dict:dict[str, Case], parent_proto: Case|None, dir_path: str, file_paths: list[str]) -> Case|None:
  '''
  Create Case objects from the paths in the given directory.
  Each case is defined by the collection of file paths that share a common stem (which implies the case name)
  and have one of the designated test case extensions.

  ## Multicases
  A `.iot` file may contain a single case definition, or alternatively a list of definitions.
  A list implies a series of tests which are consecutively named `<stem>.<index>`.

  ## Parameterized files
  A case file may contain `%` formatters and will then be interpreted as a parameterized name
  that applies over multiple cases.
  Each case must have one non-parameterized contributing file; otherwise there is no way to infer its existence.
  '''
  configs = defaultdict[str,dict](dict)
  val_paths, iot_paths = fan_by_pred(file_paths, pred=lambda p: path_ext(p) == '.iot')
  for path in iot_paths:
    add_iot_configs(configs=configs, path=path)
  for path in val_paths:
    stem = case_stem_for_path(path)
    if std_ext := std_file_ext(path):
      add_std_file(config=configs[stem], path=path, std_ext=std_ext)
    else:
      configs[stem].setdefault('.dflt_src_paths', []).append(path)

  case_configs, par_configs_dicts = dict_fan_by_key_pred(configs, pred=fnf_str_has_formatter)

  par_configs: list[ParConfig] = [ParConfig(stem=s, pattern=compile_par_stem_re(s), config=c) for s, c in par_configs_dicts.items()]
  par_stems_used: set[str] = set()

  # default.
  default_stem = path_join(dir_path, '_default')
  proto = create_proto_case(ctx, proto=parent_proto, stem=default_stem, config=case_configs.get(default_stem, {}))
  # cases.
  for stem, config in sorted(case_configs.items()):
    assert stem not in cases_dict
    if stem == default_stem: continue
    if '.test_info_paths' not in config: continue # Not a real case; found only non-test files.
    case = Case(ctx, proto, stem, config, par_configs, par_stems_used)
    cases_dict[stem] = case
  # check that all par paths are used by some case.
  for par_config in par_configs:
    if par_config.stem not in par_stems_used and par_config.config.get('.test_info_paths'):
      outL(f'iotest note: parameterized case template was never used: {par_config.stem}')
      outL(par_config.config)
  return proto


def case_stem_for_path(path:str) -> str:
  stem = path_stem_sans_exts(path)
  dir, name = split_dir_name(stem)
  if name == '_': return dir
  if name.isnumeric(): return f'{dir}.{name}' # Synthesize subcase stem.
  return stem


def add_iot_configs(configs: dict, path: str) -> None:
  stem = case_stem_for_path(path)
  if '.' in stem: exit(f"iotest error: .iot name stem cannot contain '.': {stem!r}; path: {path!r}.")
  text = read_from_path(path)
  if not text or text.isspace():
    configs[stem].setdefault('.test_info_paths', set()).add(path)
    return

  try: val = literal_eval(text)
  except (SyntaxError, ValueError) as e:
    s = str(e)
    if m := re.match(r'malformed node or string on line (\d+):', s): # omit the repr garbage containing object address.
      msg = f'malformed .iot file: {path!r}, line {m.group(1)}.'
    else:
      msg = f'malformed .iot file: {path!r}\n  exception: {s}'
    exit(f'iotest error: {stem}: {msg}')

  if isinstance(val, dict):
    configs[stem].setdefault('.test_info_paths', set()).add(path)
    configs[stem].update(val)
  elif isinstance(val, list):
    if path_name_stem_sans_exts(stem) == '_default':
      exit(f'iotest error: default case cannot specify a multicase (list of subcases): {path!r}')
    for i, el in enumerate(val):
      sub = f'{stem}.{i}' # Synthesize the subcase stem from the multicase stem and the index.
      if isinstance(el, dict):
        configs[sub].setdefault('.test_info_paths', set()).add(path)
        configs[sub].update(el)
      else:
        exit(f'iotest error: {stem}: subcase {el} iot contents is not a dictionary: {path!r}')
  else:
    exit(f'iotest error: {stem}: case iot contents is not a dictionary: {path!r}')


implied_case_exts = frozenset({'.iot', '.out', '.err'})
std_case_exts = frozenset({'.out', '.err'}) # TODO: support '.in.'

def std_file_ext(path:str) -> str|None:
  '''
  If `path` looks like it has a standard file extension, return that extension.
  Standard files can have any number of extensions, e.g. 'some-test-stem.out.svg'.
  We expect the first (innerrmost) extension to be one of the standard case extensions.
  The outer extension is tolerated to support syntax highlighting, viewing with standard tools, etc.
  '''
  exts = path_exts(path) # May have a compound extension, e.g. '.out.svg'.
  if not exts: return None
  ext0 = exts[0]
  return ext0 if ext0 in std_case_exts else None


def add_std_file(config:dict, path:str, std_ext:str) -> None:
  'Add a standard file (i.e. `.in`, `.out`, `.err`, possibly with additional extensions).'
  if std_ext in config: # TODO: this check should occur in add_iot_configs.
    exit(f'iotest error: {path}: test case configuration contains reserved key: {std_ext!r}')
  assert std_ext in ('.in', '.out', '.err'), std_ext
  config.setdefault('.test_info_paths', set()).add(path)
  config[std_ext] = path


def compile_par_stem_re(stem: str) -> Pattern[str]:
  try: return regex_for_fnf_str(stem, allow_empty=False)
  except FilenameFormatterError as e:
    exit(f'iotest error: invalid parameterized case stem: {stem}\n  {e}')


def report_coverage(coverage_cases: list[Case]) -> None:
  if not coverage_cases:
    exit('No coverage generated by tests.')
  def cov_path(case: Case) -> str:
    return path_rel_to_current_or_abs(path_join(case.test_dir, case.coverage_path))
  cmd = ['coven', '-coalesce'] + [cov_path(case) for case in coverage_cases]
  outL()
  outSL('#', *cmd)
  stdout.flush()
  exit(runC(cmd))


def try_case(ctx:Ctx, coverage_cases:list[Case], case: Case) -> bool:
  try:
    ok = run_case(ctx, coverage_cases, case)
  except TestCaseError as e:
    t = type(e)
    outL(f'\niotest: could not run test case: {case.stem}.\n  exception: {t.__module__}.{t.__qualname__}: {e}')
    ok = False

  if not ok:
    if case.desc: outSL('description:', case.desc)
    outL('=' * bar_width, '\n')

    # Touch the .failed marker file.
    try: open(case.test_failed_path, 'w').close()
    except OSError as e: errL(f'iotest: could not touch failed file: {case.test_failed_path!r}\n  exception: {e}')

    ctx.fail_fast()

  return ok


def run_case(ctx:Ctx, coverage_cases:list[Case], case: Case) -> bool:
  if ctx.dbg: errL()
  _bar_width = (bar_width if ctx.show_times else 1)
  outZ(f'{case.stem:{_bar_width}}', flush=True)
  if ctx.dbg:
    outL() # terminate previous line.
    case.describe(stderr)

  # set up directory.
  test_dir_status = file_status(case.test_dir, follow=False)
  if test_dir_status:
    if not test_dir_status.is_dir: # Could be a symlink; do not want to remove contents of link destination.
      raise TestCaseError(f'test directory already exists as a non-directory: {case.test_dir}')
    if not case.multi_index: # None or 0 (lead subcase of a multicase).
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
      raise TestCaseError(f'symlink must be a name, not a path: {link}') # TODO: make parent dirs for link_path?
    if path_exists(link_path, follow=False):
      raise TestCaseError(f'desired symlink path already exists: {link_path}')
    try: make_link(orig=orig_path, link=link_path)
    except FileNotFoundError as e: raise TestCaseError(f'link original source does not exist: {orig_path}') from e


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
        cat_file(compile_out_path)
        cat_file(compile_err_path)
      return False

  if case.in_ is not None:
    # TODO: if specified as a .in file, just read from that location instead of reading/writing the expected text from/to disk.
    in_path = path_join(case.test_dir, 'in')
    write_to_path(in_path, case.in_)
  else:
    in_path = '/dev/null'
  if ctx.dbg: errSL('input path:', in_path)

  if case.code is None:
    exp_code = 1 if (case.err_val or case.err_path) else 0
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
  exps_ok = all([check_file_exp(ctx=ctx, case=case, exp=exp) for exp in case.test_expectations])
  return status and exps_ok


def run_cmd(ctx:Ctx, coverage_cases:list[Case]|None, case:Case, label:str, cmd:list[str], cwd:str, env:dict[str, str],
 in_path:str, out_path:str, err_path:str, timeout:int, exp_code:int) -> bool|None:

  'returns True for success, False for failure, and None for abort.'

  cmd_head = cmd[0]
  #cmd_path = path_rel_to_current_or_abs(cmd_head) # For diagnostics.
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
    except Timeout:
      outL(f'\n{label} process timed out ({timeout} sec) and was killed.')
    return None


def check_file_exp(ctx:Ctx, case:Case, exp:FileExpectation) -> bool:
  'return True if expectation is met.'
  if ctx.dbg: errL(f'check_file_exp: {exp}')
  path = rel_path(path_join(case.test_dir, exp.path))
  # TODO: support binary files by getting read mode from test case.
  # Expected read mode could also be indicated by using a bytes value for the expectation.
  try:
    with open(path, errors='replace') as f:
      act_val = f.read()
  except FileNotFoundError:
    outL(f'\niotest: test did not output expected file: {exp.path}')
    return False
  except Exception as e:
    outL(f'\niotest: could not read test output file: {path}\n  exception: {e!r}')
    ctx.fail_fast(e)
    return False
  if file_expectation_fns[exp.mode](exp, act_val):
    return True

  is_empty = not act_val
  outL(f'\noutput file does not {exp.mode} expectation. actual value:', (" ''" if is_empty else ''))
  if not is_empty: cat_file(path)

  if not exp.val:
    outL('Expected empty file.')
  elif exp.mode == 'equal': # show a diff.
    path_expected = path + '.expected'
    write_to_path(path_expected, exp.val) # TODO: only write out if it is not already in a file.
    cmd = diff_cmd + [rel_path(path_expected), rel_path(path)]
    outL(QUOTE, ' '.join(cmd), FILL_OUT)
    run(cmd, exp=None)
    outL(QUOTE_END, FILL_OUT)
  elif exp.mode == 'match':
    assert exp.match_error is not None
    i, exp_pattern, act_line = exp.match_error
    outL(f'match failed at line {i}:\npattern:   {exp_pattern!r}\nactual text: {act_line!r}')

  if ctx.interactive:
    if exp.src_path:
      if confirm(f'update expectation to match result ({path} -> {exp.src_path})'):
        copy_path(path, exp.src_path)
    else:
      outSL('note: cannot update expectation:', exp)
  outSL('-' * bar_width)
  return False


diff_cmd = 'git diff --exit-code --no-index --no-prefix --no-renames --histogram --color=auto --ws-error-highlight=old,new'.split()


def cat_file(path: str, limit=-1) -> None:
  outL(QUOTE, 'cat ', rel_path(path), FILL_OUT)
  line:str|None = None
  with open(path) as f:
    for i, line in enumerate(f):
      if i == limit: return #!cov-ignore.
      outN(*sanitize_for_console(line, allow_sgr=is_out_tty, escape=ESCAPE_OUT, unescape=UNESCAPE_OUT))
  if line is None:
    outL(QUOTE_END, '(empty)', FILL_OUT) # type: ignore[unreachable] # Spurious 'Statement is unreachable'.
  elif not line.endswith('\n'):
    outL(QUOTE_END, '(missing final newline)', FILL_OUT) #!cov-ignore.
  else:
    outL(QUOTE_END, FILL_OUT)


sanitize_re = re.compile(r'(?P<vis>[\n\x1b -~]+)|.')
escape_reprs = {
  '\r': '\\r',
  '\t': '\\t',
}

def shell_cmd_str(cmd: list[str]) -> str: return ' '.join(shlex.quote(word) for word in cmd)


# Constants.

bar_width = 64
dflt_build_dir = '_build'
dflt_timeout = 4

# Colors.
QUOTE = TTY_OUT and sgr(BG, gray26(6))
QUOTE_END = TTY_OUT and sgr(BG, gray26(4))
ESCAPE_OUT = TTY_OUT and INVERT
UNESCAPE_OUT = TTY_OUT and RST_INVERT
