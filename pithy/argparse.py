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
  A subclass of ArgParser that has a lazy `commands` subparser.
  The subparser is defined as lazy because subparsers will be of type CommandParser and may not themselves define subcommands.
  '''


  @cached_property
  def commands(self) -> _SubParsersAction:
    commands = self.add_subparsers(required=True, dest='command', help='Available commands.')
    self.epilog = "For help with a specific command, pass '-h' to that command."
    return commands


  def add_command(self, main_fn:Callable[[Namespace],None], name:str|None=None, **kwargs) -> 'CommandParser':
    '''
    Add a command to the parser.
    By default, `name` will be derived from `main_fn` by removing the 'main_' prefix and replacing underscores with hyphens.
    '''
    if not name:
      name = main_fn.__name__.removeprefix('main_').replace('_', '-')

    command = self.commands.add_parser(name, **kwargs)
    command.set_defaults(main=main_fn)
    return command # type: ignore[no-any-return]


  def parse_and_run_command(self, args:Sequence[str]|None=None) -> Namespace:
    '''
    Parse arguments and run the command.
    '''
    ns = self.parse_args(args)
    ns.main(ns)
    return ns
