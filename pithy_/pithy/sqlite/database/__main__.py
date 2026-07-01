# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
CLI for managing a pithy.sqlite Database group.

Because a DbConfig is defined by the owning application (often via `Database.set_global_config`),
each command takes a dotted `app` spec naming the module that defines it. See `load_config`.
'''

from argparse import Namespace
from importlib import import_module

from ...argparser import CommandParser
from ...logs import logI
from . import Database, DbConfig


def main() -> None:
  parser = CommandParser(prog='pithy.sqlite.database', description='Manage a pithy.sqlite Database group.')

  command_init = parser.add_command(main_init)
  command_init.add_argument('app', help=app_help)

  command_manifest = parser.add_command(main_manifest)
  command_manifest.add_argument('app', help=app_help)
  command_manifest.add_argument('-write', action='store_true',
    help='Write the current config to the manifest, overwriting any existing manifest. Without this, the manifest is checked.')

  _ = (command_init, command_manifest) # Silence unused variable warnings.

  parser.parse_and_run_command()


app_help = ("Dotted name of the application module that defines the DbConfig, optionally with a ':attribute' suffix. "
  'Without an attribute, the module is imported and `Database.global_config()` is used. See `load_config`.')


def main_init(args:Namespace) -> None:
  'Create and initialize each database file, then write the manifest. Idempotent.'
  config = load_config(args.app)
  Database.initialize(config)


def main_manifest(args:Namespace) -> None:
  'Check or write the config manifest in the data dir for discovery by generic tools.'
  config = load_config(args.app)
  if args.write:
    config.write_manifest()
    logI('Wrote database manifest.', path=config.manifest_path)
    return
  if not config.is_manifest_current():
    exit(f'error: database manifest is missing or stale: {config.manifest_path!r}.\n'
      f'Run `python3 -m pithy.sqlite.database manifest {args.app} -write` to update it.')
  logI('Database manifest is current.', path=config.manifest_path)


def load_config(spec:str) -> DbConfig:
  '''
  Resolve a DbConfig from a dotted `spec`, a module path with an optional ':attribute' suffix.

  Without an attribute, the module is imported and `Database.global_config()` is returned.
  With an attribute, the named (possibly dotted) attribute is resolved on the module;
  if it is not already a DbConfig but is callable, it is called with no arguments.
  This supports apps that expose a config object or factory directly.
  '''
  module_name, _, attr = spec.partition(':')
  module = import_module(module_name)
  if not attr:
    return Database.global_config()
  obj:object = module
  for part in attr.split('.'):
    obj = getattr(obj, part)
  if isinstance(obj, DbConfig): return obj
  if callable(obj):
    result = obj()
    if not isinstance(result, DbConfig):
      exit(f'error: {spec!r} returned {type(result).__name__}, not a DbConfig.')
    return result
  exit(f'error: {spec!r} resolved to {type(obj).__name__}, which is not a DbConfig or a callable returning one.')


if __name__ == '__main__': main()
