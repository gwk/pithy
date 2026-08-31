# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Declarative command line parsing.

A command is a subclass of `Cmd` whose fields declare positional arguments, named options and flags.
Subclasses are turned into keyword-only dataclasses, so a parsed command is simply a well-typed structure.
Every field must be declared with one of the field specifiers: `pos`, `remainder`, `opt`, `flag`, `sub` or `group`.

Commands compose in two ways:
* A `group` field embeds another `Cmd` subclass, flattening its arguments into the enclosing command.
  This is how sets of common options are shared between commands.
* A `sub` field declares subcommands; its type is a `Cmd` subclass or a union of them,
  and the parsed subcommand instance is stored in the field.

The grammar is deliberately rigid, so that dispatch to subcommands is never ambiguous:
* A token beginning with `-` is always an option; `--` ends option parsing for the current command.
* Option names are declared with a single dash. Multi-character names also accept a double-dash spelling automatically.
  Names are otherwise matched exactly; they are never abbreviated or guessed.
* Every command provides `-h` and `-help`; these names are reserved and may not be declared as options.
* An option that takes a value is written `-name=value` or `-name value`;
  in the latter form the value may not itself begin with `-`.
* Bare tokens fill the declared positionals in declaration order.
* A command that declares subcommands may only declare required, non-variadic positionals.
  The next bare token after those positionals selects a subcommand,
  and every remaining token belongs to that subcommand.
  As a consequence, the options of a parent command must precede the subcommand name.

Short option clustering, such as interpreting `-xvf` as `-x -v -f`, is deliberately not supported.
Because multi-character single-dash option names are first-class, `-xvf` always names one option.
This explicit tradeoff removes ambiguity and keeps the parser implementation simple.

# Zsh completion

`Cmd.parse_or_exit` and `Cmd.main` supports dynamic zsh completion, selected by the `PITHY_CMDPARSE_MODE` environment variable.
`PITHY_CMDPARSE_MODE=print-zsh-completion prog` prints a completion script for the executable `prog`.

To use completions, `zsh/pithy-cmdparse-completion.zsh` must be sourced in `~/.zshrc`.

For completion of `python -m module` invocations, source `zsh/pithy-cmdparse-module-completion.zsh` as well
and register modules with `pithy_cmdparse_module_completion <module_names> ...`.

Program completion scripts should be placed somewhere on the zsh fpath, typically `~/.zfunc`.
If this not on the fpath, add `fpath=(~/.zfunc $fpath)` to `~/.zshrc` before `compinit` runs.

For a given cmdparse based python program `prog`, emit the script as `_prog` into ~/.zfunc:
  emit-cmdparse-completion prog

This helper is defined in the sourced zsh file and is equivalent to:
  PITHY_CMDPARSE_MODE=print-zsh-completion prog > ~/.zfunc/_prog

The generated scripts call `_pithy_cmdparse_complete_request`.

Then start a new shell; if completion does not immediately work, delete compinit's `~/.zcompdump` cache file.
'''

import re
from dataclasses import dataclass, field, Field, fields, MISSING
from os import environ
from os.path import basename
from sys import argv as sys_argv, exit as sys_exit, stderr
from textwrap import dedent
from types import NoneType, UnionType
from typing import (Annotated, Any, Callable, cast, ClassVar, dataclass_transform, get_args, get_origin, get_type_hints,
  Literal, Self, Sequence, Union)

from . import ansi
from .type_utils import normalize_type_form, unwrap_type_alias


_arg_key = 'pithy.cmdparse' # Key under which an ArgSpec is stored in dataclass field metadata.
_help_flags = frozenset(('-h', '-help', '--help'))
_option_name_re = re.compile(r'-[A-Za-z0-9_-]+\Z')
_option_prefix_re = re.compile(r'[A-Za-z0-9_-]+\Z')


class CmdDeclError(Exception):
  'A command class is malformed. This indicates a programming error, not bad user input.'


class CmdError(Exception):
  'The command line arguments are invalid.'

  def __init__(self, msg:str, cmd:'type[Cmd]|None'=None, prog:str='') -> None:
    super().__init__(msg)
    self.msg = msg
    self.cmd = cmd
    self.prog = prog


class CmdHelp(Exception):
  'Help was requested for the command that is being parsed.'

  def __init__(self, cmd:'type[Cmd]', prog:str) -> None:
    super().__init__(prog)
    self.cmd = cmd
    self.prog = prog

  @property
  def text(self) -> str: return format_help(self.cmd, self.prog)



type ArgKind = Literal['pos','remainder','opt','flag','sub','group']
type CmdMode = Literal['parse','complete']


class _PathCompletion: pass


type Path = Annotated[str, _PathCompletion]


@dataclass(frozen=True)
class ArgSpec:
  'The declaration attached to a command field by one of the field specifier functions.'
  kind:ArgKind
  flags:tuple[str,...] = ()
  doc:str = ''
  parse:Callable[[str],Any]|None = None
  metavar:str = ''
  prefix:str = ''


def _spec_field(spec:ArgSpec, default:Any, default_factory:Any) -> Any:
  kwargs:dict[str,Any] = {'metadata':{_arg_key:spec}}
  if default is not MISSING: kwargs['default'] = default
  if default_factory is not MISSING: kwargs['default_factory'] = default_factory
  return field(**kwargs)


def pos(*, default:Any=MISSING, default_factory:Any=MISSING, doc:str='', parse:Callable[[str],Any]|None=None,
 metavar:str='') -> Any:
  '''
  Declare a positional argument.
  A `list[T]` field is variadic; it consumes all remaining bare tokens and must be declared last.
  A field with no default is required.
  Use the `Path` annotation for path completion while retaining a parsed `str` value.
  '''
  return _spec_field(ArgSpec('pos', doc=doc, parse=parse, metavar=metavar), default, default_factory)


def remainder(*, default_factory:Any=list, doc:str='', parse:Callable[[str],Any]|None=None, metavar:str='') -> Any:
  '''
  Declare a positional argument that captures every token after it begins, including option-looking tokens and `--`.
  The field must be typed as `list[T]` and must be the last positional argument.
  Before capture begins, declared options are still parsed normally.
  Capture begins at the first token that is not a declared option; If a `--` separator is encountered, it is consumed.
  To pass a literal leading `--` through to the remainder, write it twice.
  An empty remainder defaults to an empty list.
  Use the `Path` annotation for path completion while retaining parsed `str` values.
  '''
  return _spec_field(ArgSpec('remainder', doc=doc, parse=parse, metavar=metavar), MISSING, default_factory)


def opt(*flags:str, default:Any=MISSING, default_factory:Any=MISSING, doc:str='', parse:Callable[[str],Any]|None=None,
 metavar:str='') -> Any:
  '''
  Declare a named option that takes a value.
  `flags` defaults to the single-dash name derived from the field name.
  Pass one or more single-dash names to declare aliases; abbreviated names such as `-f` are never inferred.
  A `list[T]` field accumulates one value per occurrence; otherwise repeating the option is an error.
  Use the `Path` annotation for path completion while retaining a parsed `str` value.
  '''
  return _spec_field(ArgSpec('opt', flags=flags, doc=doc, parse=parse, metavar=metavar), default, default_factory)


def flag(*flags:str, default:bool=False, doc:str='') -> Any:
  '''
  Declare a boolean flag, which takes no separate value.
  The primary (first) flag name also gets a negating form such as `-no-name`.
  Double-dash spellings of multi-character names and their negated forms are accepted automatically.
  A positive name may be assigned an explicit boolean value with `-name=VALUE`; negated names take no value.
  Pass `default` explicitly when the command is also constructed in code,
  because type checkers only recognize defaults that are passed to a field specifier, not those built into it.
  '''
  return _spec_field(ArgSpec('flag', flags=flags, doc=doc), default, MISSING)


def sub(*, default:Any=MISSING, doc:str='') -> Any:
  '''
  Declare a subcommand field, whose type is a `Cmd` subclass or a union of them.
  Add `|None` and `default=None` to make the subcommand optional.
  '''
  return _spec_field(ArgSpec('sub', doc=doc), default, MISSING)


def group(*, prefix:str='', doc:str='') -> Any:
  '''
  Declare a group field, whose type is a `Cmd` subclass whose arguments are flattened into the enclosing command.
  `prefix` is prepended to every option name in the group; nested group prefixes are joined with dashes.
  '''
  return _spec_field(ArgSpec('group', doc=doc, prefix=prefix), MISSING, MISSING)


@dataclass
class Entry:
  'A single parsable argument, resolved from a command field.'
  path:tuple[str,...] # The field path from the root command instance; longer than one element for grouped fields.
  spec:ArgSpec
  T:Any # The element type, i.e. with `list` and `None` stripped off.
  convert:Callable[[str],Any]
  is_list:bool
  has_default:bool
  flags:tuple[str,...]
  metavar:str
  is_path:bool

  @property
  def name(self) -> str: return self.path[-1]

  @property
  def label(self) -> str: return self.flags[0] if self.flags else self.metavar


@dataclass
class CmdSchema:
  'The parsable structure of a command class, with group fields flattened in.'
  cmd:'type[Cmd]'
  positionals:list[Entry]
  opts:list[Entry] # Options and flags, in declaration order, for help formatting.
  entries:dict[tuple[str,...],Entry] # All entries, keyed by field path.
  flag_entries:dict[str,tuple[Entry,bool]] # Maps each flag string to its entry and a negation bit.
  sub_path:tuple[str,...]
  sub_cmds:dict[str,'type[Cmd]']
  sub_has_default:bool


type CompletionGroup = Literal['commands','options','values']


@dataclass(frozen=True)
class Completion:
  'A completion candidate, its description, and the display group it belongs to.'
  value:str
  doc:str = ''
  group:CompletionGroup = 'values'


@dataclass(frozen=True)
class CompletionResult:
  'Completion candidates for a partial command line, with an optional request for native path completion.'
  candidates:tuple[Completion,...] = ()
  path_prefix:str|None = None


@dataclass
class _WalkState:
  'The mutable grammar state shared by parsing and completion.'
  cmd:'type[Cmd]'
  prog:str
  schema:CmdSchema
  mode:CmdMode
  values:dict[tuple[str,...],Any]
  seen:set[tuple[str,...]]
  pos_idx:int = 0
  end_opts:bool = False
  pending_opt:Entry|None = None
  remainder:Entry|None = None


_bool_words = {'true':True, 'false':False, 'yes':True, 'no':False, '1':True, '0':False}


def _parse_bool(s:str) -> bool:
  try: return _bool_words[s.lower()]
  except KeyError: raise ValueError(f'expected one of {sorted(_bool_words)}') from None


_converters:dict[Any,Callable[[str],Any]] = {str:str, int:int, float:float, bool:_parse_bool}


def _has_path_annotation(T:Any) -> bool:
  T = unwrap_type_alias(T)
  origin = get_origin(T)
  if origin is Annotated:
    args = get_args(T)
    return _PathCompletion in args[1:] or _has_path_annotation(args[0])
  if origin is list or isinstance(T, UnionType) or origin is Union:
    return any(_has_path_annotation(arg) for arg in get_args(T) if arg is not NoneType)
  return False


def _analyze_type(T:Any) -> tuple[Any,bool,bool]:
  'Return the element type of a field, whether it is a list, and whether it is optional.'
  T = normalize_type_form(T)
  is_optional = False
  if isinstance(T, UnionType) or get_origin(T) is Union:
    members = [normalize_type_form(m) for m in get_args(T)]
    non_none = [m for m in members if m is not NoneType]
    is_optional = len(non_none) < len(members)
    if len(non_none) != 1: raise CmdDeclError(f'unsupported union type: {T}')
    T = non_none[0]
  is_list = get_origin(T) is list
  if is_list:
    args = get_args(T)
    if len(args) != 1: raise CmdDeclError(f'unsupported list type: {T}')
    T = normalize_type_form(args[0])
  return T, is_list, is_optional


def _default_flags(name:str) -> tuple[str,...]: return ('-' + name.replace('_', '-'),)


def _default_metavar(name:str, kind:ArgKind) -> str:
  n = name.replace('_', '-')
  return n.upper() if kind == 'pos' else f'<{n}>'


def _check_flag(flag_str:str, cmd:'type[Cmd]', name:str) -> None:
  if not flag_str.startswith('-'):
    raise CmdDeclError(f'{cmd.__name__}.{name}: flag must begin with a dash: {flag_str!r}')
  if flag_str.startswith('--'):
    raise CmdDeclError(f'{cmd.__name__}.{name}: flag declarations must use a single dash: {flag_str!r}')
  if len(flag_str) == 1:
    raise CmdDeclError(f'{cmd.__name__}.{name}: invalid flag: {flag_str!r}')
  if _option_name_re.fullmatch(flag_str) is None:
    raise CmdDeclError(
      f'{cmd.__name__}.{name}: flag may contain only ASCII letters, digits, hyphens and underscores: {flag_str!r}')


def _flag_spellings(flag_str:str) -> tuple[str,...]:
  'Return the accepted spellings of an option name, adding a double dash for multi-character names.'
  return (flag_str, '-' + flag_str) if len(flag_str) > 2 else (flag_str,)


def _make_entry(cmd:'type[Cmd]', f:Any, spec:ArgSpec, T:Any, path:tuple[str,...], prefixes:tuple[str,...]) -> Entry:
  name = f.name
  is_path = _has_path_annotation(T)
  elem_T, is_list, is_optional = _analyze_type(T)
  if spec.kind == 'flag' and (elem_T is not bool or is_list):
    raise CmdDeclError(f'{cmd.__name__}.{name}: a flag field must be typed `bool`.')
  literal_values = get_args(elem_T) if get_origin(elem_T) is Literal else ()
  if literal_values and not all(isinstance(value, str) for value in literal_values):
    raise CmdDeclError(f'{cmd.__name__}.{name}: Literal arguments must contain only strings.')
  base_convert = spec.parse or (str if literal_values else _converters.get(elem_T))
  convert:Callable[[str],Any]|None
  if literal_values:
    def parse_literal(s:str) -> Any:
      assert base_convert is not None
      value = base_convert(s)
      if value not in literal_values: raise ValueError(f'expected one of: {", ".join(literal_values)}')
      return value
    convert = parse_literal
  else:
    convert = base_convert
  if convert is None:
    raise CmdDeclError(f'{cmd.__name__}.{name}: no converter for type {elem_T}; pass an explicit `parse` function.')
  flags = spec.flags or (() if spec.kind == 'pos' else _default_flags(name))
  for flag_str in flags: _check_flag(flag_str, cmd, name)
  if flags and prefixes:
    prefix = '-'.join(prefixes) + '-'
    flags = tuple('-' + prefix + flag_str[1:] for flag_str in flags)
  has_default = f.default is not MISSING or f.default_factory is not MISSING or is_optional
  literal_metavar = '{' + ','.join(literal_values) + '}' if literal_values else ''
  return Entry(path=path, spec=spec, T=elem_T, convert=convert, is_list=is_list, has_default=has_default, flags=flags,
    metavar=spec.metavar or literal_metavar or _default_metavar(name, spec.kind), is_path=is_path)


def _register_flag(schema:CmdSchema, flag_str:str, entry:Entry, negated:bool) -> None:
  if flag_str in _help_flags:
    raise CmdDeclError(f'{schema.cmd.__name__}: option name is reserved for help: {flag_str!r}')
  existing = schema.flag_entries.get(flag_str)
  if existing is not None:
    if existing == (entry, negated): return
    raise CmdDeclError(f'{schema.cmd.__name__}: ambiguous option spelling: {flag_str!r}')
  schema.flag_entries[flag_str] = (entry, negated)


def _collect_sub_cmds(cmd:'type[Cmd]', f:Any, T:Any) -> tuple[dict[str,'type[Cmd]'],bool]:
  members = get_args(T) if (isinstance(T, UnionType) or get_origin(T) is Union) else (T,)
  has_default = f.default is not MISSING or f.default_factory is not MISSING
  sub_cmds:dict[str,type[Cmd]] = {}
  for m in members:
    m = normalize_type_form(m)
    if m is NoneType:
      has_default = True
      continue
    if not (isinstance(m, type) and issubclass(m, Cmd)):
      raise CmdDeclError(f'{cmd.__name__}.{f.name}: a sub field must be typed as a Cmd subclass or a union of them.')
    name = m.cmd_name or _derive_cmd_name(m)
    if name in sub_cmds: raise CmdDeclError(f'{cmd.__name__}.{f.name}: duplicate subcommand name: {name!r}')
    sub_cmds[name] = m
  if not sub_cmds: raise CmdDeclError(f'{cmd.__name__}.{f.name}: sub field declares no commands.')
  return sub_cmds, has_default


def _cmd_fields(cmd:'type[Cmd]') -> tuple[Field[Any],...]:
  'The dataclass fields of a command class. `Cmd` itself is not a dataclass; only its subclasses are.'
  if getattr(cmd, '__dataclass_fields__', None) is None:
    raise CmdDeclError(f'{cmd.__name__} is not a command dataclass; subclass Cmd instead of using it directly.')
  return fields(cast(Any, cmd))


def _collect(cmd:'type[Cmd]', path:tuple[str,...], schema:CmdSchema, prefixes:tuple[str,...]=()) -> None:
  'Recursively collect the entries of `cmd` into `schema`, flattening group fields.'
  hints = get_type_hints(cmd, include_extras=True)
  for f in _cmd_fields(cmd):
    spec = f.metadata.get(_arg_key)
    if spec is None:
      raise CmdDeclError(
        f'{cmd.__name__}.{f.name}: field must be declared with pos, remainder, opt, flag, sub or group.')
    assert isinstance(spec, ArgSpec)
    T = hints[f.name]
    fpath = path + (f.name,)

    if spec.kind == 'group':
      G = normalize_type_form(T)
      if not (isinstance(G, type) and issubclass(G, Cmd)):
        raise CmdDeclError(f'{cmd.__name__}.{f.name}: a group field must be typed as a Cmd subclass.')
      normalized_prefix = spec.prefix.replace('_', '-')
      if normalized_prefix and (normalized_prefix.startswith('-') or normalized_prefix.endswith('-')):
        raise CmdDeclError(f'{cmd.__name__}.{f.name}: group prefix must not begin or end with a dash: {spec.prefix!r}')
      if spec.prefix and _option_prefix_re.fullmatch(spec.prefix) is None:
        raise CmdDeclError(
          f'{cmd.__name__}.{f.name}: group prefix may contain only ASCII letters, digits, hyphens and underscores: '
          f'{spec.prefix!r}')
      child_prefixes = prefixes + ((normalized_prefix,) if normalized_prefix else ())
      _collect(G, fpath, schema, child_prefixes)
      continue

    if spec.kind == 'sub':
      if path: raise CmdDeclError(f'{cmd.__name__}.{f.name}: sub fields are not allowed inside of a group.')
      if schema.sub_path: raise CmdDeclError(f'{cmd.__name__}: multiple sub fields are not allowed.')
      schema.sub_cmds, schema.sub_has_default = _collect_sub_cmds(cmd, f, normalize_type_form(T))
      schema.sub_path = fpath
      continue

    entry = _make_entry(cmd, f, spec, T, fpath, prefixes)
    schema.entries[fpath] = entry
    if spec.kind in ('pos', 'remainder'):
      schema.positionals.append(entry)
      continue

    schema.opts.append(entry)
    for flag_str in entry.flags:
      for spelling in _flag_spellings(flag_str):
        _register_flag(schema, spelling, entry, negated=False)
    if spec.kind == 'flag':
      primary = entry.flags[0]
      for spelling in _flag_spellings('-no-' + primary[1:]):
        _register_flag(schema, spelling, entry, negated=True)


def _build_schema(cmd:'type[Cmd]') -> CmdSchema:
  schema = CmdSchema(cmd=cmd, positionals=[], opts=[], entries={}, flag_entries={}, sub_path=(), sub_cmds={},
    sub_has_default=False)
  _collect(cmd, (), schema)

  for idx, entry in enumerate(schema.positionals):
    is_last = (idx == len(schema.positionals) - 1)
    if entry.spec.kind == 'remainder' and not entry.is_list:
      raise CmdDeclError(f'{cmd.__name__}.{entry.name}: a remainder field must be typed `list[T]`.')
    if entry.is_list and not is_last:
      raise CmdDeclError(f'{cmd.__name__}.{entry.name}: a variadic positional must be declared last.')
    if entry.has_default and not is_last and not schema.positionals[idx+1].has_default:
      raise CmdDeclError(f'{cmd.__name__}.{entry.name}: an optional positional cannot precede a required one.')
    if schema.sub_cmds and (entry.is_list or entry.has_default):
      raise CmdDeclError(
        f'{cmd.__name__}.{entry.name}: a command with subcommands can declare only required, non-variadic positionals.')

  return schema


def _is_option_token(token:str) -> bool: return len(token) > 1 and token[0] == '-'


def _convert(entry:Entry, label:str, s:str, cmd:'type[Cmd]', prog:str) -> Any:
  try: return entry.convert(s)
  except Exception as e: raise CmdError(f'{label}: invalid value: {s!r}; {e}', cmd, prog) from e


def _store(values:dict[tuple[str,...],Any], entry:Entry, label:str, val:Any, cmd:'type[Cmd]', prog:str) -> None:
  if entry.is_list: values.setdefault(entry.path, []).append(val)
  elif entry.path in values: raise CmdError(f'{label}: specified more than once.', cmd, prog)
  else: values[entry.path] = val


def _consume_value(state:_WalkState, entry:Entry, label:str, token:str) -> None:
  state.seen.add(entry.path)
  if state.mode == 'parse':
    _store(state.values, entry, label, _convert(entry, label, token, state.cmd, state.prog), state.cmd, state.prog)


def _consume_tokens(state:_WalkState, tokens:Sequence[str]) -> tuple['type[Cmd]|None',int]:
  '''
  Consume complete tokens and update grammar state.
  Return a selected subcommand and the index of its first argument, or `(None, len(tokens))`.
  In complete mode, a final option awaiting a value is recorded in `pending_opt` instead of raising an error.
  '''
  idx = 0
  while idx < len(tokens):
    token = tokens[idx]
    idx += 1

    if state.pos_idx < len(state.schema.positionals):
      remainder_entry = state.schema.positionals[state.pos_idx]
      if remainder_entry.spec.kind == 'remainder' and (
       state.pos_idx > 0 or state.end_opts or not _is_option_token(token) or token == '--'):
        start = idx if token == '--' else idx - 1
        for remainder_token in tokens[start:]:
          _consume_value(state, remainder_entry, remainder_entry.metavar, remainder_token)
        state.remainder = remainder_entry
        state.pos_idx = len(state.schema.positionals)
        return None, len(tokens)

    if not state.end_opts and token == '--':
      state.end_opts = True
      continue

    if not state.end_opts and _is_option_token(token):
      name, eq, inline_val = token.partition('=')
      if name in _help_flags:
        if state.mode == 'parse': raise CmdHelp(state.cmd, state.prog)
        continue
      try: entry, negated = state.schema.flag_entries[name]
      except KeyError:
        if state.mode == 'parse': raise CmdError(f'unrecognized option: {name}', state.cmd, state.prog) from None
        continue

      if entry.spec.kind == 'flag':
        if eq:
          if negated:
            if state.mode == 'parse': raise CmdError(f'{name}: negated flag takes no value.', state.cmd, state.prog)
            continue
          _consume_value(state, entry, name, inline_val)
        else:
          state.seen.add(entry.path)
          if state.mode == 'parse': _store(state.values, entry, name, not negated, state.cmd, state.prog)
      elif eq:
        _consume_value(state, entry, name, inline_val)
      else:
        if idx == len(tokens):
          if state.mode == 'complete':
            state.pending_opt = entry
            return None, len(tokens)
          raise CmdError(f'{name}: option requires a value.', state.cmd, state.prog)
        next_token = tokens[idx]
        if _is_option_token(next_token):
          if state.mode == 'parse':
            raise CmdError(f'{name}: option requires a value; for a value beginning with a dash, use {name}=VALUE.',
              state.cmd, state.prog)
          continue
        idx += 1
        _consume_value(state, entry, name, next_token)
      continue

    if state.pos_idx < len(state.schema.positionals):
      entry = state.schema.positionals[state.pos_idx]
      if not entry.is_list: state.pos_idx += 1
      _consume_value(state, entry, entry.metavar, token)
      continue

    if state.schema.sub_cmds:
      try: sub_cmd = state.schema.sub_cmds[token]
      except KeyError:
        if state.mode == 'parse': raise CmdError(f'unrecognized command: {token!r}', state.cmd, state.prog) from None
        continue
      return sub_cmd, idx

    if state.mode == 'parse': raise CmdError(f'unexpected argument: {token!r}', state.cmd, state.prog)

  return None, len(tokens)


def _parse_cmd(cmd:'type[Cmd]', tokens:Sequence[str], prog:str) -> 'Cmd':
  '''
  Parse `tokens` as a single command, returning the constructed command instance.
  Values are collected by field path, which is flat except for group fields.
  A subcommand token causes all remaining tokens to be parsed recursively, ending this level.
  '''
  schema = cmd._schema()
  state = _WalkState(cmd=cmd, prog=prog, schema=schema, mode='parse', values={}, seen=set())
  sub_cmd, sub_idx = _consume_tokens(state, tokens)
  if sub_cmd is not None:
    sub_name = tokens[sub_idx-1]
    state.values[schema.sub_path] = _parse_cmd(sub_cmd, tokens[sub_idx:], f'{prog} {sub_name}')
  return _construct(cmd, (), state.values, schema, prog)


def _default_none(kwargs:dict[str,Any], f:Field[Any]) -> None:
  'Pass None for an optional field that has no dataclass default of its own.'
  if f.default is MISSING and f.default_factory is MISSING: kwargs[f.name] = None


def _construct(cmd:'type[Cmd]', path:tuple[str,...], values:dict[tuple[str,...],Any], schema:CmdSchema, prog:str) -> 'Cmd':
  '''
  Build the instance for `cmd` from the values collected for a single command level.
  `path` is the field path of `cmd` within that level; it is nonempty when constructing a group.
  '''
  hints = get_type_hints(cmd, include_extras=True)
  kwargs:dict[str,Any] = {}
  children:list[Cmd] = []

  for f in _cmd_fields(cmd):
    spec = f.metadata[_arg_key]
    fpath = path + (f.name,)

    if spec.kind == 'group':
      G:Any = normalize_type_form(hints[f.name])
      child = _construct(G, fpath, values, schema, prog)
    elif spec.kind == 'sub':
      sub_cmd = values.get(fpath)
      if sub_cmd is None:
        if not schema.sub_has_default: raise CmdError('missing command.', cmd, prog)
        _default_none(kwargs, f)
        continue
      assert isinstance(sub_cmd, Cmd)
      child = sub_cmd
    else:
      if fpath in values:
        kwargs[f.name] = values[fpath]
      else:
        entry = schema.entries[fpath]
        if not entry.has_default: raise CmdError(f'missing required argument: {entry.label}', cmd, prog)
        _default_none(kwargs, f)
      continue

    children.append(child)
    kwargs[f.name] = child

  obj = cmd(**kwargs)
  for child in children: child._cmd_parent = obj
  return obj


def _entry_completions(entry:Entry, prefix:str, *, value_prefix:str='') -> CompletionResult:
  literal_values = get_args(entry.T) if get_origin(entry.T) is Literal else ()
  if literal_values:
    return CompletionResult(tuple(Completion(value_prefix + value) for value in literal_values if value.startswith(prefix)))
  if entry.T is bool:
    return CompletionResult(tuple(
      Completion(value_prefix + value) for value in _bool_words if value.startswith(prefix)))
  if entry.is_path: return CompletionResult(path_prefix=value_prefix)
  return CompletionResult()


def _option_completions(state:_WalkState, prefix:str) -> tuple[Completion,...]:
  'Offer only single-dash spellings unless the user has already typed a double dash; the aliases are redundant noise.'
  offer_double = prefix.startswith('--')
  completions:list[Completion] = []
  for spelling, (entry, negated) in state.schema.flag_entries.items():
    if spelling.startswith('--') != offer_double: continue
    if not spelling.startswith(prefix): continue
    if entry.path in state.seen and not entry.is_list: continue
    suffix = '' if entry.spec.kind == 'flag' or negated else '='
    completions.append(Completion(spelling + suffix, entry.spec.doc, group='options'))
  for help_flag in (('--help',) if offer_double else ('-h', '-help')):
    if help_flag.startswith(prefix): completions.append(Completion(help_flag, state.cmd.help_doc, group='options'))
  return tuple(completions)


def _complete_cmd(cmd:'type[Cmd]', prior:Sequence[str], current:str, prog:str) -> CompletionResult:
  schema = cmd._schema()
  state = _WalkState(cmd=cmd, prog=prog, schema=schema, mode='complete', values={}, seen=set())
  sub_cmd, sub_idx = _consume_tokens(state, prior)
  if sub_cmd is not None:
    sub_name = prior[sub_idx-1]
    return _complete_cmd(sub_cmd, prior[sub_idx:], current, f'{prog} {sub_name}')

  if state.pending_opt is not None: return _entry_completions(state.pending_opt, current)
  if state.remainder is not None: return _entry_completions(state.remainder, current)

  if state.pos_idx < len(schema.positionals):
    entry = schema.positionals[state.pos_idx]
    if entry.spec.kind == 'remainder' and (state.pos_idx > 0 or state.end_opts or not _is_option_token(current)):
      return _entry_completions(entry, current)

  if not state.end_opts and _is_option_token(current):
    name, eq, value_prefix = current.partition('=')
    if eq:
      found = schema.flag_entries.get(name)
      if found is None: return CompletionResult()
      entry, negated = found
      if negated: return CompletionResult()
      return _entry_completions(entry, value_prefix, value_prefix=name + '=')
    return CompletionResult(_option_completions(state, current))

  candidates:list[Completion] = []
  path_prefix:str|None = None
  if not state.end_opts and not current:
    candidates.extend(_option_completions(state, current))

  if state.pos_idx < len(schema.positionals):
    positional = _entry_completions(schema.positionals[state.pos_idx], current)
    candidates.extend(positional.candidates)
    path_prefix = positional.path_prefix
  elif schema.sub_cmds:
    candidates.extend(Completion(name, _first_doc_line(sub_cmd), group='commands')
      for name, sub_cmd in schema.sub_cmds.items() if name.startswith(current))

  return CompletionResult(tuple(candidates), path_prefix)


def _format_completion_result(result:CompletionResult) -> str:
  'Format the line-oriented completion protocol consumed by `format_zsh_completion`.'
  lines = []
  for candidate in result.candidates:
    value = candidate.value.replace('\t', ' ').replace('\n', ' ')
    doc = candidate.doc.replace('\t', ' ').replace('\n', ' ')
    lines.append(f'candidate\t{candidate.group}\t{value}\t{doc}')
  if result.path_prefix is not None: lines.append(f'path\t{result.path_prefix}')
  return '\n'.join(lines)


@dataclass_transform(kw_only_default=True, field_specifiers=(pos, remainder, opt, flag, sub, group))
class Cmd:
  '''
  Base class for command structures.
  Subclasses are automatically converted into keyword-only dataclasses,
  whose fields must each be declared with `pos`, `remainder`, `opt`, `flag`, `sub` or `group`.
  '''

  cmd_name:ClassVar[str] = '' # Optional explicit subcommand name; otherwise it is derived from the class name.
  help_doc:ClassVar[str] = 'Show this help.' # Description of the built-in help option.

  _cmd_parent:'Cmd|None' = None # Set on group and subcommand instances during construction. Not a dataclass field.


  def __init_subclass__(cls, **kwargs:Any) -> None:
    super().__init_subclass__(**kwargs)
    dataclass(cls, kw_only=True)


  @classmethod
  def _schema(cls) -> CmdSchema:
    'The parsable structure of this command class, computed on demand and cached per class.'
    schema = cls.__dict__.get('_cmd_schema')
    if schema is None:
      schema = _build_schema(cls)
      setattr(cls, '_cmd_schema', schema)
    assert isinstance(schema, CmdSchema)
    return schema


  @classmethod
  def validate(cls) -> None:
    '''
    Validate this command declaration and cache its schema.
    Call this after all types referenced by the command have been defined to detect declaration errors eagerly.
    Parsing and help formatting perform the same validation automatically when first used.
    '''
    cls._schema()


  @property
  def parent(self) -> 'Cmd|None':
    'The enclosing command or group instance, if any.'
    return self._cmd_parent


  @property
  def sub_cmd(self) -> 'Cmd|None':
    'The parsed subcommand, if this command declares a subcommand field.'
    schema = type(self)._schema()
    if not schema.sub_path: return None
    cmd = getattr(self, schema.sub_path[-1])
    assert cmd is None or isinstance(cmd, Cmd)
    return cmd


  @classmethod
  def parse(cls, args:Sequence[str], prog:str='') -> Self:
    '''
    Parse `args` into an instance of this command.
    Raise `CmdError` for invalid arguments, or `CmdHelp` if help was requested.
    '''
    cmd = _parse_cmd(cls, list(args), prog or _derive_cmd_name(cls))
    assert isinstance(cmd, cls)
    return cmd


  @classmethod
  def complete(cls, args:Sequence[str], prog:str='') -> CompletionResult:
    '''
    Complete a partial command line.
    `args` contains the command arguments through the word under the cursor; its final item is the current partial word.
    An empty sequence is treated like a single empty current word.
    '''
    prior, current = (args[:-1], args[-1]) if args else ((), '')
    return _complete_cmd(cls, prior, current, prog or _derive_cmd_name(cls))


  @classmethod
  def parse_or_exit(cls, args:Sequence[str]|None=None, prog:str='') -> Self:
    'Parse `args`, defaulting to `sys.argv`; print help or an error message and exit if the arguments are unsatisfactory.'
    if args is None:
      args = sys_argv[1:]
      prog = prog or basename(sys_argv[0])
    mode = environ.get('PITHY_CMDPARSE_MODE', 'parse')
    if mode == 'complete':
      print(_format_completion_result(cls.complete(args, prog=prog)))
      sys_exit(0)
    if mode == 'print-zsh-completion':
      print(format_zsh_completion(prog or _derive_cmd_name(cls)))
      sys_exit(0)
    if mode != 'parse':
      print(f'error: invalid PITHY_CMDPARSE_MODE: {mode!r}', file=stderr)
      sys_exit(2)
    try: return cls.parse(args, prog=prog)
    except CmdHelp as help:
      print(format_help(help.cmd, help.prog, color=ansi.is_out_tty))
      sys_exit(0)
    except CmdError as err:
      color = ansi.is_err_tty
      print(format_usage(err.cmd or cls, err.prog or prog, color=color), file=stderr)
      error = f'{ansi.sgr(ansi.cBOLD, ansi.cTXT_R)}error:{ansi.RST}' if color else 'error:'
      print(f'{error} {err.msg}', file=stderr)
      sys_exit(2)


  @classmethod
  def main(cls, args:Sequence[str]|None=None, prog:str='') -> Any:
    'Parse `args` and run the resulting command.'
    return cls.parse_or_exit(args, prog=prog).run()


  def run(self) -> Any:
    'Run this command. The default implementation dispatches to the subcommand, if any.'
    cmd = self.sub_cmd
    if cmd is None: raise NotImplementedError(f'{type(self).__name__} does not implement `run`.')
    return cmd.run()



_camel_re = re.compile(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])')


def _derive_cmd_name(cmd:type[Cmd]) -> str:
  name = cmd.__name__.removesuffix('Cmd').removesuffix('Command') or cmd.__name__
  return _camel_re.sub('-', name).lower()


def _pos_usage(entry:Entry) -> str:
  s = entry.metavar + ('...' if entry.is_list else '')
  return f'[{s}]' if entry.has_default else s


def _subcommands_usage(schema:CmdSchema) -> str:
  return '{' + ','.join(schema.sub_cmds) + '}'


def _styled(text:str, style:str, color:bool) -> str:
  return f'{style}{text}{ansi.RST}' if color else text


def _option_style(flag:str, *, bold:bool) -> str:
  color = ansi.cTXT_C if len(flag) > 2 else ansi.cTXT_G
  return ansi.sgr(ansi.cBOLD, color) if bold else ansi.sgr(color)


def format_usage(cmd:type[Cmd], prog:str='', *, color:bool=False) -> str:
  'Format the usage line for `cmd`.'
  schema = cmd._schema()
  parts = [_styled('usage:', ansi.sgr(ansi.cBOLD, ansi.cTXT_B), color)]
  parts.append(_styled(prog or _derive_cmd_name(cmd), ansi.sgr(ansi.cBOLD, ansi.cTXT_M), color))
  if schema.opts: parts.append(f'[{_styled("options", ansi.TXT_G, color)}]')
  parts.extend(_styled(_pos_usage(entry), ansi.TXT_Y, color) for entry in schema.positionals)
  if schema.sub_cmds:
    commands = _styled(_subcommands_usage(schema), ansi.TXT_G, color) + ' ...'
    parts.append(f'[{commands}]' if schema.sub_has_default else commands)
  return ' '.join(parts)


def _opt_usage(entry:Entry) -> str:
  flags = ', '.join(entry.flags)
  return flags if entry.spec.kind == 'flag' else f'{flags} {entry.metavar}'


def _format_rows(rows:list[tuple[str,str]], styled_labels:list[str]|None=None) -> list[str]:
  width = min(max(len(label) for label, _ in rows), 24)
  lines = []
  for idx, (label, doc) in enumerate(rows):
    styled_label = styled_labels[idx] if styled_labels else label
    doc_lines = dedent(doc).strip().splitlines()
    if not doc_lines: lines.append(f'  {styled_label}')
    elif len(label) > width:
      lines.append(f'  {styled_label}')
      lines.extend(f'  {"":{width}}  {line}' if line else '' for line in doc_lines)
    else:
      lines.append(f'  {styled_label}{"":{width - len(label)}}  {doc_lines[0]}')
      lines.extend(f'  {"":{width}}  {line}' if line else '' for line in doc_lines[1:])
  return lines


def format_help(cmd:type[Cmd], prog:str='', *, color:bool=False) -> str:
  'Format the complete help text for `cmd`.'
  schema = cmd._schema()
  lines = [format_usage(cmd, prog, color=color)]

  doc = dedent(cmd.__doc__ or '').strip()
  if doc: lines.extend(['', doc])

  if schema.positionals:
    lines.extend(['', _styled('positional arguments:', ansi.sgr(ansi.cBOLD, ansi.cTXT_B), color)])
    pos_rows = [(_pos_usage(e), e.spec.doc) for e in schema.positionals]
    pos_labels = [_styled(label, ansi.sgr(ansi.cBOLD, ansi.cTXT_Y), color) for label, _ in pos_rows]
    lines.extend(_format_rows(pos_rows, pos_labels))

  lines.extend(['', _styled('options:', ansi.sgr(ansi.cBOLD, ansi.cTXT_B), color)])
  opt_rows = [(_opt_usage(e), e.spec.doc) for e in schema.opts] + [('-h, -help', cmd.help_doc)]
  opt_labels = []
  for entry in [*schema.opts, None]:
    flags = entry.flags if entry else ('-h', '-help')
    styled_flags = ', '.join(_styled(flag, _option_style(flag, bold=True), color) for flag in flags)
    if entry is not None and entry.spec.kind != 'flag':
      styled_flags += ' ' + _styled(entry.metavar, ansi.sgr(ansi.cBOLD, ansi.cTXT_Y), color)
    opt_labels.append(styled_flags)
  lines.extend(_format_rows(opt_rows, opt_labels))

  if schema.sub_cmds:
    lines.extend(['', _styled('commands:', ansi.sgr(ansi.cBOLD, ansi.cTXT_B), color)])
    lines.append(f'  {_styled(_subcommands_usage(schema), ansi.sgr(ansi.cBOLD, ansi.cTXT_G), color)}')
    cmd_rows = [(name, _first_doc_line(c)) for name, c in schema.sub_cmds.items()]
    cmd_labels = [_styled(name, ansi.sgr(ansi.cBOLD, ansi.cTXT_Y), color) for name, _ in cmd_rows]
    lines.extend(f'  {line}' for line in _format_rows(cmd_rows, cmd_labels))
    lines.extend(['', "For help with a specific command, pass '-h' to that command."])

  return '\n'.join(lines)


def _first_doc_line(cmd:type[Cmd]) -> str: return dedent(cmd.__doc__ or '').strip().partition('\n')[0]


def format_zsh_completion(prog:str) -> str:
  '''
  Format a zsh completion function for an executable using `Cmd.parse_or_exit` or `Cmd.main`.
  The executable is invoked dynamically for every completion request.
  The function calls `_pithy_cmdparse_complete_request`, which is defined in zsh/pithy-cmdparse-completion.zsh.
  '''
  fn_name = '_' + re.sub(r'[^A-Za-z0-9_]', '_', prog)
  return f'''\
#compdef {prog}

{fn_name}() {{
  local -a cmdparse_invocation=("$words[1]")
  local -a cmdparse_args=("${{(@)words[2,$CURRENT]}}")
  _pithy_cmdparse_complete_request
}}

compdef {fn_name} {prog}'''
