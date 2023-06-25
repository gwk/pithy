# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
import re
import shlex
from itertools import zip_longest
from string import Template
from typing import Any, Callable, cast, NamedTuple, Optional, Pattern, TextIO, Union

from pithy.fs import abs_path, path_dir, path_exists, path_join, path_name
from pithy.io import errL, outL, read_from_path, stdout, writeLSSL
from pithy.path import path_stem
from pithy.types import (is_bool, is_dict, is_dict_of_str, is_int, is_list, is_list_of_str, is_pos_int, is_set, is_set_of_str,
  is_str, is_str_or_list)

from .ctx import Ctx


#from pithy.types import *



coverage_name = '_.coven'


class TestCaseError(Exception): pass

class IotParseError(TestCaseError): pass


class FileExpectation:

  def __init__(self, path: str, info: dict[str, str], expand_str_fn: Callable):
    if path.find('..') != -1:
      raise TestCaseError(f"file expectation {path}: cannot contain '..'")
    self.path = expand_str_fn(path)
    self.mode = info.get('mode', 'equal')
    validate_exp_mode(path, self.mode)
    try:
      exp_path = info['path']
    except KeyError:
      val = info.get('val', '')
    else:
      if 'val' in info:
        raise TestCaseError(f'file expectation {path}: cannot specify both `path` and `val` properties')
      exp_path_expanded = expand_str_fn(exp_path)
      val = read_from_path(exp_path_expanded)
    self.val = expand_str_fn(val)
    self.src_path = info.get('path') # Do not yet have capability to update the value within an iot file.
    if self.mode == 'match':
      self.match_pattern_pairs = self.compile_match_lines(self.val)
    else:
      self.match_pattern_pairs = []
    self.match_error: Optional[tuple[int,Pattern|None, str]] = None


  def compile_match_lines(self, text: str) -> list[tuple[str, Pattern]]:
    return [self.compile_match_line(i, line) for i, line in enumerate(text.splitlines(True), 1)]


  def compile_match_line(self, i: int, line: str) -> tuple[str, Pattern]:
    prefix = line[:2]
    contents = line[2:]
    valid_prefixes = ('|', '|\n', '| ', '~', '~\n', '~ ')
    if prefix not in valid_prefixes:
      raise TestCaseError("test expectation: {!r};\nmatch line {}: must begin with one of: {}\n{!r}".format(
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
      raise TestCaseError('test expectation: {!r};\nmatch line {}: pattern is invalid regex:\n{!r}\n{}'.format(
        self.path, i, contents, e)) from e


  def __repr__(self) -> str:
    val_repr = repr(self.val) if len(self.val) < 64 else repr(self.val[:64]) + '…'
    return f'FileExpectation({self.path!r}, {self.mode!r}, {val_repr})'.format(self.path, self.mode, self.val)


class ParConfig(NamedTuple):
  '''
  Parameterized case configuration data.
  '''
  stem: str
  pattern: Pattern[str]
  config: dict


class Case:
  'Case represents a single test case, or a default.'

  def __init__(self, ctx:Ctx, proto: Optional['Case'], stem: str, config: dict, par_configs: list[ParConfig],
   par_stems_used: set[str]) -> None:
    self.dir: str = path_dir(stem)
    self.stem: str = self.dir if path_name(stem) == '_' else stem # TODO: better naming for 'logical stem' (see code in main).
    self.name: str = path_name(self.stem)
    # derived properties.
    self.multi_index: Optional[int] = None
    self.test_info_paths: set[str] = set() # the files that comprise the test case.
    self.dflt_src_paths: list[str] = []
    self.coverage_targets: list[str] = []
    self.test_dir: str = ''
    self.test_cmd: list[str] = []
    self.test_env: dict[str, str] = {}
    self.test_failed_previously: bool = False
    self.test_in: Optional[str] = None
    self.test_expectations: list[FileExpectation] = []
    self.test_links: list[tuple[str, str]] = [] # sequence of (orig-name, link-name) pairs.
    self.test_par_args: dict[str, tuple[str, ...]] = {} # the match groups that resulted from applying the regex for the given parameterized stem.
    # configurable properties.
    self.args: Optional[list[str]] = None # arguments to follow the file under test.
    self.cmd: Optional[list[str]] = None # command string/list with which to invoke the test.
    self.coverage: Optional[list[str]] = None # list of names to include in code coverage analysis.
    self.code: Optional[int] = None # the expected exit code.
    self.compile: Optional[list[Any]] = None # the optional list of compile commands, each a string or list of strings.
    self.compile_timeout: Optional[int] = None
    self.desc: Optional[str] = None # description.
    self.env: Optional[dict[str, str]] = None # environment variables.
    self.err_mode: Optional[str] = None # comparison mode for stderr expectation.
    self.err_path: Optional[str] = None # file path for stderr expectation.
    self.err_val: Optional[str] = None # stderr expectation value (mutually exclusive with err_path).
    self.files: Optional[dict[str, dict[str, str]]] = None # additional file expectations.
    self.in_: Optional[str] = None # stdin as text.
    self.interpreter: Optional[str] = None # interpreter to prepend to cmd.
    self.interpreter_args: Optional[list[str]] = None # interpreter args.
    self.links: Union[None, str, set[str], dict[str, str]] = None # symlinks to be made into the test directory.
    #^ Written as a str, set or dict.
    self.out_mode: Optional[str] = None # comparison mode for stdout expectation.
    self.out_path: Optional[str] = None # file path for stdout expectation.
    self.out_val: Optional[str] = None # stdout expectation value (mutually exclusive with out_path).
    self.skip: Optional[str] = None
    self.timeout: Optional[int] = None

    try:
      if proto is not None:
        for key in case_key_validators:
          setattr(self, key, getattr(proto, key))

      for par_stem, par_re, par_config in par_configs:
        m = par_re.fullmatch(stem)
        if not m: continue
        for key, val in par_config.items():
          self.add_val_for_key(ctx, key, val)
        self.test_par_args[par_stem] = cast(tuple[str, ...], m.groups()) # Save the strings matching the parameters to use as arguments.
        par_stems_used.add(par_stem) # Mark this parameterized config as used.

      for key, val in config.items():
        self.add_val_for_key(ctx, key, val)

      # do all additional computations now, so as to fail as quickly as possible.
      self.derive_info(ctx)

    except Exception as e:
      outL(f'iotest error: broken test case: {stem}')
      outL(f'  exception: {type(e).__name__}: {e}.')
      # not sure if it makes sense to describe cases for some exceptions;
      # for now, just carve out the ones for which it is definitely useless.
      if not isinstance(e, IotParseError):
        self.describe(stdout)
        outL()
      exit(1)


  def __repr__(self) -> str: return f'Case(stem={self.stem!r}, ...)'

  def __lt__(self, other: 'Case') -> bool: return self.stem < other.stem

  @property
  def coverage_path(self) -> str:
    'Returned path is relative to self.test_dir.'
    return self.std_name(coverage_name)

  @property
  def coven_cmd_prefix(self) -> list[str]:
    coven_cmd = ['coven', '-output', self.coverage_path]
    if self.coverage_targets:
      coven_cmd += ['-targets'] + self.coverage_targets
    coven_cmd.append('--')
    return coven_cmd

  def std_name(self, std: str) -> str: return f'{self.name}.{std}'


  def describe(self, file: TextIO) -> None:
    def stable_repr(val: Any) -> str:
      if is_dict(val):
        return '{{{}}}'.format(', '.join(f'{k!r}:{v!r}' for k, v in sorted(val.items()))) # sort dict representations. TODO: factor out.
      return repr(val)

    items = sorted(self.__dict__.items())
    writeLSSL(file, 'Case:', *('{}: {}'.format(k, stable_repr(v)) for k, v in items))


  def add_val_for_key(self, ctx:Ctx, key:str, val:Any) -> None:
    try: name = iot_key_subs[key]
    except KeyError: name = key.replace('-', '_')
    try:
      exp_desc, predicate, validator_fn = case_key_validators[name]
    except KeyError as e:
      raise TestCaseError(f'invalid config key: {key!r}') from e
    if not predicate(val):
      raise TestCaseError(f'key: {key!r}: expected value of type: {exp_desc}; received: {val!r}')
    if validator_fn:
      validator_fn(name, val)
    if ctx.dbg:
      existing = getattr(self, name)
      if existing is not None and existing != val:
        errL(f'note: {self.stem}: overriding value for key: {name!r};\n  existing: {existing!r}\n  incoming: {val!r}')
    setattr(self, name, val)


  def derive_info(self, ctx: Ctx) -> None:
    if self.name == '_default': return # do not process prototype cases.
    rel_dir, _, multi_index = self.stem.partition('.')
    self.multi_index = int(multi_index) if multi_index else None
    self.test_dir = path_join(ctx.build_dir, rel_dir)
    self.test_failed_path = path_join(self.test_dir, self.name + '.failed')
    self.test_failed_previously = path_exists(self.test_failed_path, follow=False)

    env = self.test_env # local alias for convenience.
    env['BUILD'] = ctx.build_dir
    env['NAME'] = self.name
    env['PROJ'] = abs_path(ctx.proj_dir)
    env['SRC'] = self.dflt_src_paths[0] if len(self.dflt_src_paths) == 1 else 'NONE'
    env['STEM'] = self.stem
    env['DIR'] = self.dir

    def default_to_env(key: str) -> None:
      if key not in env and key in os.environ:
        env[key] = os.environ[key]

    default_to_env('HOME') # otherwise git fails with "error: Could not expand include path '~/.gitcinclude'".
    default_to_env('LANG') # necessary to make std file handles unicode-aware.
    default_to_env('NODE_PATH')
    default_to_env('PATH')
    default_to_env('PYTHONPATH')
    default_to_env('SDKROOT')

    def expand_str(val: Any) -> str:
      t = Template(val)
      return t.safe_substitute(env)

    def expand(val: Any) -> list[str]:
      if val is None:
        return []
      if is_str(val):
        # note: plain strings are expanded first, then split.
        # this behavior matches that of shell commands more closely than split-then-expand,
        # but introduces all the confusion of shell quoting.
        return shlex.split(expand_str(val))
      if is_list(val):
        return [expand_str(el) for el in val]
      raise TestCaseError(f'expand received unexpected value: {val}')

    # add the case env one item at a time.
    # sorted because we want expansion to be deterministic;
    # TODO: should probably expand everything with just the builtins;
    # otherwise would need some dependency resolution between vars.
    if self.env:
      for key, val in sorted(self.env.items()):
        if key in env:
          raise TestCaseError(f'specified env contains reserved key: {key}')
        env[key] = expand_str(val)

    self.compile_cmds = [expand(cmd) for cmd in self.compile] if self.compile else []

    cmd: list[str] = []
    if self.interpreter:
      cmd += expand(self.interpreter)
    if self.interpreter_args:
      if not self.interpreter: raise TestCaseError('interpreter_args specified without interpreter')
      cmd += expand(self.interpreter_args)

    if self.cmd is not None:
      cmd += expand(self.cmd)
    elif self.compile_cmds:
      cmd += ['./' + self.name]
    elif len(self.dflt_src_paths) > 1:
      raise TestCaseError(f'no `cmd` specified and multiple default source paths found: {self.dflt_src_paths}')
    elif len(self.dflt_src_paths) < 1:
      raise TestCaseError('no `cmd` specified and no default source path found')
    else:
      dflt_path = self.dflt_src_paths[0]
      dflt_name = path_name(dflt_path)
      self.test_links.append((dflt_path, dflt_name))
      prefix = '' if cmd else './'
      cmd.append(prefix + dflt_name)
      if self.args is None:
        par_args = list(self.test_par_args.get(path_stem(dflt_path), ()))
        cmd += par_args

    if self.args:
      cmd += expand(self.args) or []

    self.test_cmd = cmd

    if self.multi_index and self.links:
      raise TestCaseError("non-lead subcase of a multicase cannot specify 'links'")
    elif isinstance(self.links, str):
      link = expand_str(self.links)
      self.test_links += [(link, path_name(link))]
    elif isinstance(self.links, set):
      self.test_links += sorted((n, path_name(n)) for n in map(expand_str, self.links))
    elif isinstance(self.links, dict):
      self.test_links += sorted((expand_str(orig), expand_str(link)) for orig, link in self.links.items())
    elif self.links is not None:
      raise TestCaseError(self.links)

    self.coverage_targets = expand(self.coverage)

    self.test_in = expand_str(self.in_) if self.in_ is not None else None

    def add_std_exp(name:str, mode:Optional[str], path:Optional[str], val:Optional[str]) -> None:
      info = {}
      if mode is not None: info['mode'] = mode
      if path is not None: info['path'] = path
      if val is not None: info['val'] = val
      exp = FileExpectation(self.std_name(name), info, expand_str)
      self.test_expectations.append(exp)

    add_std_exp('err', mode=self.err_mode, path=self.err_path, val=self.err_val)
    add_std_exp('out', mode=self.out_mode, path=self.out_path, val=self.out_val)

    for path, info in (self.files or {}).items():
      exp = FileExpectation(path, info, expand_str)
      self.test_expectations.append(exp)


iot_key_subs = {
  '.in' : 'in_',
  '.err' : 'err_path',
  '.out' : 'out_path',
  '.dflt_src_paths' : 'dflt_src_paths',
  '.test_info_paths' : 'test_info_paths',
  'in' : 'in_',
}

def is_int_or_ellipsis(val: Any) -> bool:
  return val is Ellipsis or is_int(val)

def is_compile_cmd(val: Any) -> bool:
  return is_list(val) and all(is_str_or_list(el) for el in val)

def is_valid_links(val: Any) -> bool:
  return is_str(val) or is_set_of_str(val) or is_dict_of_str(val)

def validate_path(key: str, path: Any) -> None:
  if not path: raise TestCaseError(f'key: {key}: path is empty: {path!r}')
  if '.' in path: raise TestCaseError(f"key: {key}: path cannot contain '.': {path!r}")

def validate_exp_mode(key: str, mode: str) -> None:
  if mode not in file_expectation_fns:
    raise TestCaseError(f'key: {key}: invalid file expectation mode: {mode}')

def validate_exp_dict(key: str, val: Any) -> None:
  if not is_dict(val):
    raise TestCaseError(f'file expectation: {key}: value must be a dictionary; recieved {val!r}')
  for k in val:
    if k not in ('mode', 'path', 'val'):
      raise TestCaseError(f'file expectation: {key}: invalid expectation property: {k}')


def validate_files_dict(key: str, val: Any) -> None:
  if not is_dict(val):
    raise TestCaseError(f'file expectation: {key}: value must be a dictionary; recieved {val!r}')
  for k, exp_dict in val.items():
    if k in ('out', 'err'):
      raise TestCaseError(f'key: {key}: {k}: use the standard properties instead ({k}_mode, {k}_path, {k}_val)')
    validate_exp_dict(k, exp_dict)

def validate_links_dict(key: str, val: Any) -> None:
  if is_str(val):
    items = [(val, val)]
  elif is_set(val):
    items = [(p, p) for p in val]
  elif is_dict(val):
    items = val.items()
  else: raise AssertionError('`validate_links_dict` types inconsistent with `is_valid_links`.')
  for orig, link in items:
    if orig.find('..') != -1: raise TestCaseError(f"key: {key}: link original contains '..': {orig}")
    if link.find('..') != -1: raise TestCaseError(f"key: {key}: link location contains '..': {link}")


case_key_validators: dict[str, tuple[str, Callable[[Any], bool], Optional[Callable[[str, Any], None]]]] = {
  # key => msg, validator_predicate, validator_fn.
  'args':     ('string or list of strings', is_str_or_list,     None),
  'cmd':      ('string or list of strings', is_str_or_list,     None),
  'code':     ('int or `...`',              is_int_or_ellipsis, None),
  'compile':  ('list of (str | list of str)', is_compile_cmd,   None),
  'compile_timeout': ('positive int',       is_pos_int,         None),
  'coverage': ('string or list of strings', is_str_or_list,     None),
  'desc':     ('str',                       is_str,             None),
  'dflt_src_paths': ('list of str',         is_list_of_str,     None),
  'env':      ('dict of strings',           is_dict_of_str,     None),
  'err_mode': ('str',                       is_str,             validate_exp_mode),
  'err_path': ('str',                       is_str,             None),
  'err_val':  ('str',                       is_str,             None),
  'files':    ('dict',                      is_dict,            validate_files_dict),
  'in_':      ('str',                       is_str,             None),
  'interpreter': ('string or list of strings', is_str_or_list,  None),
  'interpreter_args': ('string or list of strings', is_str_or_list,  None),
  'links':    ('string or (dict | set) of strings', is_valid_links, validate_links_dict),
  'out_mode': ('str',                       is_str,             validate_exp_mode),
  'out_path': ('str',                       is_str,             None),
  'out_val':  ('str',                       is_str,             None),
  'skip':     ('bool',                      is_bool,            None),
  'test_info_paths': ('set of str',         is_set_of_str,      None),
  'timeout':  ('positive int',              is_pos_int,         None),
}


# file expectation functions.

def compare_equal(exp: FileExpectation, val: str) -> bool:
  return exp.val == val # type: ignore[no-any-return]

def compare_contain(exp: FileExpectation, val: str) -> bool:
  return val.find(exp.val) != -1

def compare_match(exp: FileExpectation, val: str) -> bool:
  lines: list[str] = val.splitlines(True)
  for i, (pair, line) in enumerate(zip_longest(exp.match_pattern_pairs, lines), 1):
    if pair is None:
      exp.match_error = (i, None, line)
      return False
    (pattern, regex) = pair
    if line is None or not regex.fullmatch(line):
      exp.match_error = (i, pattern, line) # type: ignore[assignment]
      return False
  return True


def compare_ignore(exp: FileExpectation, val: str) -> bool:
  return True


file_expectation_fns = {
  'equal'   : compare_equal,
  'contain' : compare_contain,
  'match'   : compare_match,
  'ignore'  : compare_ignore,
}
