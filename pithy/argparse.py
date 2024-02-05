# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import _SubParsersAction, ArgumentParser, Namespace
from typing import Callable

from .util import lazy_property


class ArgParser(ArgumentParser):
  '''
  A subclass of the standard ArgumentParser.
  '''



class CommandParser(ArgParser):
  '''
  A subclass of ArgParser that has a lazy `commands` subparser.
  The subparser is defined as lazy because subparsers will be of type CommandParser and may not themselves define subcommands.
  '''


  @lazy_property
  def commands(self) -> _SubParsersAction:
    commands = self.add_subparsers(required=True, dest='command', help='Available commands.')
    self.epilog = "For help with a specific command, pass '-h' to that command."
    return commands


  def add_command(self, main_fn:Callable[[Namespace],None], name:str|None=None, **kwargs) -> 'CommandParser':
    '''
    Add a command to the parser.
    '''
    if not name:
      name = main_fn.__name__.removeprefix('main_').replace('_', '-')

    command = self.commands.add_parser(name, **kwargs)
    command.set_defaults(main=main_fn)
    return command # type: ignore[no-any-return]
