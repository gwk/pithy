# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import _SubParsersAction, ArgumentParser, Namespace
from functools import cached_property
from typing import Callable, Sequence


class ArgParser(ArgumentParser):
  '''
  A subclass of the standard ArgumentParser.
  '''


class CommandParser(ArgParser):
  '''
  A subclass of ArgParser that is intended for configuration with subcommand parsers.
  Use `add_command()` to add subcommands.
  The result of this function is itself a CommandParser due to the way that ArgumentParser implements `add_subparsers`
  and `add_parser`.

  To create multiple levels of subcommands, use `add_parent_command()` to create intermediate parent parsers.
  '''

  @cached_property
  def _commands_subparsers(self) -> _SubParsersAction:
    commands = self.add_subparsers(required=True, dest='command', help='Available commands.')
    self.epilog = "For help with a specific command, pass '-h' to that command."
    return commands


  def _check_is_valid_parent(self) -> None:
    if self.get_default('main_fn') is not None:
      raise Exception('CommandParser has a `main_fn` function set; '
        'use `add_parent_command()` instead of `add_command()` to create intermediate parent parsers.')


  def add_command(self, main_fn:Callable[[Namespace],None], name:str|None=None, **kwargs) -> 'CommandParser':
    '''
    Add a command to the parser.
    By default, `name` will be derived from `main_fn` by removing any 'main_' prefix and replacing underscores with hyphens.
    '''
    self._check_is_valid_parent()

    if not name:
      name = main_fn.__name__.removeprefix('main_').replace('_', '-')

    command = self._commands_subparsers.add_parser(name, **kwargs)
    assert isinstance(command, CommandParser)
    command.set_defaults(main_fn=main_fn)
    return command


  def add_parent_command(self, name:str, **kwargs) -> 'CommandParser':
    '''
    Add a parent command to the parser.
    '''
    self._check_is_valid_parent()
    command = self._commands_subparsers.add_parser(name, **kwargs)
    assert isinstance(command, CommandParser)
    return command



  def parse_and_run_command(self, args:Sequence[str]|None=None) -> Namespace:
    '''
    Parse arguments and run the command.
    '''
    ns = self.parse_args(args)
    ns.main_fn(ns)
    return ns
