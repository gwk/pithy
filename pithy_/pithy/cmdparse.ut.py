# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Literal

from pithy import ansi
from pithy.cmdparse import (Cmd, CmdDeclError, CmdError, CmdHelp, Completion, CompletionResult, flag, format_help, format_usage,
  format_zsh_completion, group, opt, Path, pos, remainder, sub)
from utest import utest, utest_exc, utest_run, utest_val


class Common(Cmd):
  'Options shared between commands.'
  verbose:bool = flag('-verbose', '-v', doc='Log verbosely.')
  color:bool = flag(default=True, doc='Colorize output.')


class Build(Cmd):
  'Build the project.'
  common:Common = group()
  target:str = pos(doc='The target to build.')
  jobs:int = opt('-jobs', '-j', default=1, doc='Number of parallel jobs.')
  defines:list[str] = opt('-D', default_factory=list, doc='Preprocessor definitions.')


class AddUser(Cmd):
  'Add a user.'
  names:list[str] = pos(doc='The user names to add.')
  home:Path|None = opt(default=None, doc='The home directory.')


class Tool(Cmd):
  'An example tool.'
  common:Common = group()
  cmd:Build|AddUser = sub(doc='The command to run.')


class CompletePositional(Cmd):
  action:Literal['build','test'] = pos(doc='The action.')
  source:Path = pos(doc='The source path.')


utest(Build(common=Common(verbose=False, color=True), target='all', jobs=1, defines=[]), Build.parse, ['all'])

utest(Build(common=Common(verbose=True, color=False), target='all', jobs=4, defines=['A=1', 'B']),
  Build.parse, ['-v', '--no-color', '-j', '4', '-D', 'A=1', '-D=B', 'all'])

# Multi-character names accept both dash styles; aliases are explicit and are otherwise ordinary names.
utest(Build(common=Common(verbose=True, color=True), target='all', jobs=2, defines=[]),
  Build.parse, ['--verbose', '--jobs=2', 'all'])
utest(Build(common=Common(verbose=False, color=False), target='all', jobs=1, defines=[]),
  Build.parse, ['-verbose=false', '--color=no', 'all'])

utest(Build(common=Common(verbose=False, color=True), target='-weird', jobs=1, defines=[]),
  Build.parse, ['--', '-weird'])

# Variadic positionals and typed options.
utest(AddUser(names=['a', 'b'], home='/home'), AddUser.parse, ['a', '--home=/home', 'b'])


@utest_run
def test_literal_strings() -> None:
  class Choose(Cmd):
    actions:list[Literal['build','test']] = pos(doc='Actions to perform.')
    color:Literal['auto','always','never'] = opt(default='auto', doc='When to use color.')

  utest(Choose(actions=['build', 'test'], color='never'), Choose.parse, ['build', '--color=never', 'test'])
  utest_exc(CmdError("{build,test}: invalid value: 'deploy'; expected one of: build, test"), Choose.parse, ['deploy'])
  utest_exc(CmdError("--color: invalid value: 'sometimes'; expected one of: auto, always, never"),
    Choose.parse, ['--color=sometimes', 'build'])
  utest_val('usage: choose [options] {build,test}...', format_usage(Choose))
  assert '  {build,test}...  Actions to perform.' in format_help(Choose)
  assert '  -color {auto,always,never}\n                            When to use color.' in format_help(Choose)

# Errors are explicit; nothing is guessed.
utest_exc(CmdError('unrecognized option: --jobz'), Build.parse, ['--jobz=2', 'all'])
utest_exc(CmdError('unrecognized option: --v'), Build.parse, ['--v', 'all'])
utest_exc(CmdError('unrecognized option: --j'), Build.parse, ['--j=2', 'all'])
utest_exc(CmdError('unrecognized option: --D'), Build.parse, ['--D=A=1', 'all'])
utest_exc(CmdError('--jobs: option requires a value.'), Build.parse, ['all', '--jobs'])
utest_exc(CmdError('--jobs: option requires a value; for a value beginning with a dash, use --jobs=VALUE.'),
  Build.parse, ['--jobs', '-1', 'all'])
utest_exc(CmdError("--jobs: invalid value: 'x'; invalid literal for int() with base 10: 'x'"),
  Build.parse, ['--jobs=x', 'all'])
utest_exc(CmdError('--jobs: specified more than once.'), Build.parse, ['--jobs=1', '--jobs=2', 'all'])
utest_exc(CmdError("--verbose: invalid value: 'maybe'; expected one of ['0', '1', 'false', 'no', 'true', 'yes']"),
  Build.parse, ['--verbose=maybe', 'all'])
utest_exc(CmdError('--no-color: negated flag takes no value.'), Build.parse, ['--no-color=true', 'all'])
utest_exc(CmdError('unrecognized option: -no-v'), Build.parse, ['-no-v', 'all'])
utest_exc(CmdError('missing required argument: TARGET'), Build.parse, [])
utest_exc(CmdError("unexpected argument: 'extra'"), Build.parse, ['all', 'extra'])


@utest_run
def test_completion() -> None:
  utest_val(CompletionResult((Completion('--jobs=', 'Number of parallel jobs.', group='options'),)), Build.complete(['--j']))
  utest_val(CompletionResult((Completion('build', 'Build the project.', group='commands'),)), Tool.complete(['bu']))
  utest_val(CompletionResult((Completion('build'),)), CompletePositional.complete(['bu']))
  utest_val('', CompletePositional.complete(['build', '']).path_prefix)

  # Path annotations retain string values while requesting path completion.
  utest_val('', AddUser.complete(['--home', '']).path_prefix)
  utest_val(CompletionResult(path_prefix='--home='), AddUser.complete(['--home=src']))

  # Non-list options are omitted once seen; list options remain repeatable.
  jobs_values = {c.value for c in Build.complete(['--jobs=2', 'all', '']).candidates}
  assert '-jobs=' not in jobs_values and '--jobs=' not in jobs_values
  defines_values = {c.value for c in Build.complete(['-D=A', 'all', '']).candidates}
  assert '-D=' in defines_values

  class ParentPositional(Cmd):
    workspace:Literal['dev','prod'] = pos()
    cmd:Build = sub()

  utest_val(CompletionResult((Completion('build', 'Build the project.', group='commands'),)), ParentPositional.complete(['dev', 'bu']))

  class ForwardPaths(Cmd):
    tool:str = pos()
    paths:list[Path] = remainder()

  utest_val(CompletionResult(path_prefix=''), ForwardPaths.complete(['cc', 'input.c', '']))


@utest_run
def test_zsh_completion_script() -> None:
  script = format_zsh_completion('tool')
  assert script.startswith('#compdef tool\n')
  # The parameter expansion flags are easy to mangle in the generating f-string; assert their exact spellings.
  assert 'cmdparse_args=("${(@)words[2,$CURRENT]}")' in script
  assert '_pithy_cmdparse_complete_request' in script
  assert script.endswith('compdef _tool tool')


@utest_run
def test_remainder() -> None:
  class Forward(Cmd):
    verbose:bool = flag()
    tool:str = pos()
    args:list[str] = remainder(doc='Arguments passed to the tool.')

  utest_val(Forward(verbose=True, tool='cc', args=[]), Forward.parse(['-verbose', 'cc']))
  utest_val(Forward(verbose=False, tool='cc', args=['-O2', '--', 'a.c']), Forward.parse(['cc', '-O2', '--', 'a.c']))

  # A `--` that begins the remainder is the separator and is consumed; writing it twice passes one through.
  utest_val(Forward(verbose=False, tool='cc', args=['-O2']), Forward.parse(['cc', '--', '-O2']))
  utest_val(Forward(verbose=False, tool='cc', args=['--', '-O2']), Forward.parse(['cc', '--', '--', '-O2']))

  # Once preceding positionals are filled, even recognized options belong to the remainder.
  utest_val(Forward(verbose=False, tool='cc', args=['-verbose', 'input']), Forward.parse(['cc', '-verbose', 'input']))

  class OnlyRemainder(Cmd):
    args:list[str] = remainder()

  utest_val(OnlyRemainder(args=[]), OnlyRemainder.parse([]))
  utest_val(OnlyRemainder(args=[]), OnlyRemainder.parse(['--']))
  utest_val(OnlyRemainder(args=['-x']), OnlyRemainder.parse(['--', '-x']))
  utest_val(OnlyRemainder(args=['--', '-x']), OnlyRemainder.parse(['--', '--', '-x']))
  utest_exc(CmdError('unrecognized option: -x'), OnlyRemainder.parse, ['-x'])


@utest_run
def test_subcommands() -> None:
  tool = Tool.parse(['-v', 'build', '-j', '2', 'all'])
  utest_val(Build(common=Common(verbose=False, color=True), target='all', jobs=2, defines=[]), tool.cmd)
  utest_val(True, tool.common.verbose, desc='parent option')
  utest_val(tool, tool.cmd.parent, desc='subcommand parent link')
  utest_val(tool.cmd, tool.sub_cmd, desc='sub_cmd property')

  # The name is derived from the class name.
  utest_val(AddUser(names=['gwk'], home=None), Tool.parse(['add-user', 'gwk']).cmd)


@utest_run
def test_parent_options_precede_subcommand() -> None:
  # Parent options must precede the subcommand name; the subcommand owns every token after it.
  tool = Tool.parse(['build', 'all', '-v'])
  assert isinstance(tool.cmd, Build)
  utest_val(False, tool.common.verbose, desc='parent flag')
  utest_val(True, tool.cmd.common.verbose, desc='subcommand flag')
  utest_exc(CmdError('unrecognized option: -v'), Tool.parse, ['add-user', 'gwk', '-v'])
utest_exc(CmdError("unrecognized command: 'nope'"), Tool.parse, ['nope'])
utest_exc(CmdError('missing command.'), Tool.parse, ['-v'])

utest_exc(CmdHelp, Tool.parse, ['-h'])
utest_exc(CmdError('unrecognized option: --h'), Tool.parse, ['--h'])
utest_exc(CmdHelp, Tool.parse, ['-help'])
utest_exc(CmdHelp, Tool.parse, ['build', '--help'])


@utest_run
def test_optional_fields_without_explicit_defaults() -> None:
  # An optional type implies a default of None, even when the field specifier is not given one.

  class Opt(Cmd):
    'Optional fields.'
    name:str|None = opt()
    cmd:AddUser|None = sub()

  utest_val(Opt(name=None, cmd=None), Opt.parse([]))
  utest_val(Opt(name='x', cmd=AddUser(names=['a'], home=None)), Opt.parse(['--name=x', 'add-user', 'a']))


@utest_run
def test_decl_errors() -> None:

  def bad_variadic() -> None:
    class BadVariadic(Cmd):
      rest:list[str] = pos()
      last:str = pos()
    BadVariadic.parse([])

  utest_exc(CmdDeclError('BadVariadic.rest: a variadic positional must be declared last.'), bad_variadic)

  def bad_remainder_type() -> None:
    class BadRemainderType(Cmd):
      rest:str = remainder()
    BadRemainderType.parse([])

  utest_exc(CmdDeclError('BadRemainderType.rest: a remainder field must be typed `list[T]`.'), bad_remainder_type)

  def bad_literal_type() -> None:
    class BadLiteralType(Cmd):
      value:Literal['one',2] = pos()
    BadLiteralType.parse([])

  utest_exc(CmdDeclError('BadLiteralType.value: Literal arguments must contain only strings.'), bad_literal_type)

  def bad_sub_pos() -> None:
    class BadSubPos(Cmd):
      names:list[str] = pos()
      cmd:Build = sub()
    BadSubPos.parse([])

  utest_exc(
    CmdDeclError('BadSubPos.names: a command with subcommands can declare only required, non-variadic positionals.'),
    bad_sub_pos)

  def bad_undeclared() -> None:
    class BadUndeclared(Cmd):
      x:int = 0
    BadUndeclared.parse([])

  utest_exc(CmdDeclError(
    'BadUndeclared.x: field must be declared with pos, remainder, opt, flag, sub or group.'), bad_undeclared)

  def double_dash_decl() -> None:
    class DoubleDashDecl(Cmd):
      foo:str|None = opt('--foo')
    DoubleDashDecl.validate()

  utest_exc(CmdDeclError("DoubleDashDecl.foo: flag declarations must use a single dash: '--foo'"), double_dash_decl)

  for invalid in ('-foo=bar', '-foo bar', '-café', '-💥'):
    def invalid_flag() -> None:
      class InvalidFlag(Cmd):
        value:str|None = opt(invalid)
      InvalidFlag.validate()

    utest_exc(CmdDeclError(
      f'InvalidFlag.value: flag may contain only ASCII letters, digits, hyphens and underscores: {invalid!r}'),
      invalid_flag)

  for reserved in ('-h', '-help'):
    def reserved_help() -> None:
      class ReservedHelp(Cmd):
        value:bool = flag(reserved)
      ReservedHelp.validate()

    utest_exc(CmdDeclError(f"ReservedHelp: option name is reserved for help: {reserved!r}"), reserved_help)


@utest_run
def test_validate() -> None:
  utest_val(None, Build.validate())

  class Bad(Cmd):
    value:int = 0

  utest_exc(CmdDeclError(
    'Bad.value: field must be declared with pos, remainder, opt, flag, sub or group.'), Bad.validate)


@utest_run
def test_prefixed_groups() -> None:
  class Endpoint(Cmd):
    host:str = opt()
    port:int = opt(default=443)

  class Proxy(Cmd):
    listen:Endpoint = group(prefix='listen')
    upstream:Endpoint = group(prefix='upstream')

  utest_val(Proxy(listen=Endpoint(host='localhost', port=8443), upstream=Endpoint(host='example.com', port=443)),
    Proxy.parse(['-listen-host=localhost', '--listen-port=8443', '-upstream-host', 'example.com']))

  class UnderscorePrefix(Cmd):
    endpoint:Endpoint = group(prefix='remote_endpoint')

  utest_val(UnderscorePrefix(endpoint=Endpoint(host='example.com', port=443)),
    UnderscorePrefix.parse(['-remote-endpoint-host=example.com']))

  def invalid_prefix() -> None:
    class InvalidPrefix(Cmd):
      endpoint:Endpoint = group(prefix='remote endpoint')
    InvalidPrefix.validate()

  utest_exc(CmdDeclError(
    "InvalidPrefix.endpoint: group prefix may contain only ASCII letters, digits, hyphens and underscores: "
    "'remote endpoint'"), invalid_prefix)


utest_val('''\
usage: tool [options] {build,add-user} ...

An example tool.

options:
  -verbose, -v  Log verbosely.
  -color        Colorize output.
  -h, -help     Show this help.

commands:
  {build,add-user}
    build     Build the project.
    add-user  Add a user.

For help with a specific command, pass '-h' to that command.''',
  format_help(Tool, 'tool'), desc='help text')


@utest_run
def test_colored_help() -> None:
  plain = format_help(Tool, 'tool')
  colored = format_help(Tool, 'tool', color=True)
  utest_val(plain, ansi.strip_ctrl_seq(colored), desc='color does not alter text or alignment')
  assert f'{ansi.sgr(ansi.cBOLD, ansi.cTXT_B)}usage:{ansi.RST}' in colored
  assert f'{ansi.sgr(ansi.cBOLD, ansi.cTXT_M)}tool{ansi.RST}' in colored
  assert f'{ansi.sgr(ansi.cBOLD, ansi.cTXT_G)}-v{ansi.RST}' in colored
  assert f'{ansi.sgr(ansi.cBOLD, ansi.cTXT_C)}-verbose{ansi.RST}' in colored
  assert f'{ansi.sgr(ansi.cBOLD, ansi.cTXT_G)}{{build,add-user}}{ansi.RST}' in colored

  colored_usage = format_usage(Tool, 'tool', color=True)
  assert f'{ansi.TXT_G}options{ansi.RST}' in colored_usage
  assert f'{ansi.TXT_G}{{build,add-user}}{ansi.RST}' in colored_usage


class CustomHelp(Cmd):
  '''
    A custom-help command.

    Its description preserves paragraphs
      and relative indentation.
  '''
  help_doc = 'Explain this command.'
  value:str|None = opt(doc='''
    A value with multiple lines.
      The second line is indented.
  ''')


utest_val('''\
usage: custom-help [options]

A custom-help command.

Its description preserves paragraphs
  and relative indentation.

options:
  -value <value>  A value with multiple lines.
                    The second line is indented.
  -h, -help       Explain this command.''', format_help(CustomHelp), desc='custom help description')
