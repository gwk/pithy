# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import Namespace

from pithy.argparser import CommandParser
from pithy.filestatus import path_exists
from pithy.frozendicts import frozendict
from pithy.json import out_json
from pithy.path import path_dir_or_dot

from .api import B2Client
from .capabilities import all_capabilities_and_groups, file_ro_capabilities, file_rw_capabilities, file_rwd_capabilities
from .creds import B2Creds


def main() -> None:
  parser = CommandParser(description='B2 application key management tool.')

  list_cmd = parser.add_command(main_list)
  list_cmd.add_argument('-creds', required=True, help='Path to a credentials JSON file that can list keys.')

  create_cmd = parser.add_command(main_create)
  create_cmd.add_argument('-creds', required=True,
    help='Path to a credentials JSON file that can list buckets and create keys.')
  create_cmd.add_argument('-name', required=True, help='The application key name.')
  create_cmd.add_argument('-buckets', nargs='+', required=True, help='Names of the buckets.')
  create_cmd.add_argument('-capabilities', nargs='+', required=True,
    help='Capabilities for the key. Special values: "file-ro", "file-rw", "file-rwd".')
  create_cmd.add_argument('-output', required=False, help='Path to output the generated key JSON; defaults to "{name}.json".')

  parser.parse_and_run_command()


def main_list(args:Namespace) -> None:
  'List application keys.'

  if not path_exists(args.creds, follow=True):
    exit(f'Error: Credentials path does not exist: {args.creds!r}.')

  creds = B2Creds.load(args.creds)
  client = B2Client(creds.key_id, creds.key_secret)

  for key in client.list_keys():
    out_json(key.as_json())


def main_create(args:Namespace) -> None:
  'Create a new application key.'

  if not path_exists(args.creds, follow=True):
    exit(f'Error: Credentials path does not exist: {args.creds!r}.')

  out_path = args.output or f'{args.name}.json'

  if path_exists(out_path, follow=False):
    exit(f'Error: Output path already exists: {out_path!r}.')

  if not path_exists(path_dir_or_dot(out_path), follow=True):
    exit(f'Error: Output directory does not exist: {path_dir_or_dot(out_path)!r}.')

  capabilities:list[str] = []
  for cap in args.capabilities:
    if cap not in all_capabilities_and_groups:
      exit(f'Error: Invalid capability: {cap!r}.')
    match cap:
      case 'file-ro': capabilities.extend(file_ro_capabilities)
      case 'file-rw': capabilities.extend(file_rw_capabilities)
      case 'file-rwd': capabilities.extend(file_rwd_capabilities)
      case _: capabilities.append(cap)

  creds = B2Creds.load(args.creds)
  client = B2Client(creds.key_id, creds.key_secret)

  bucket_names = args.buckets
  assert bucket_names
  buckets:dict[str,str] = {}
  for bucket_name in bucket_names:
    buckets[bucket_name] = client.get_bucket_by_name(bucket_name).id

  bucket_ids = list(buckets.values())
  for name, id in buckets.items():
    print(f'bucket {name!r} -> {id!r}')

  created_key = client.create_key(args.name, capabilities, bucket_ids)
  creds = B2Creds.from_created_key(created_key, frozendict(buckets))
  creds.save(out_path)


if __name__ == '__main__': main()
