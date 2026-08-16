# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import Namespace

from b2sdk.v3 import B2Api, Bucket, FullApplicationKey, InMemoryAccountInfo
from pithy.argparser import CommandParser
from pithy.filestatus import path_exists
from pithy.frozendicts import frozendict
from pithy.path import path_dir_or_dot
from pithy.type_utils import req_type

from .capabilities import all_capabilities_and_groups, file_ro_capabilities, file_rw_capabilities, file_rwd_capabilities
from .creds import B2Creds


def main() -> None:
  parser = CommandParser(description='B2 application key management tool.')

  list_cmd = parser.add_command(main_list)
  list_cmd.add_argument('-creds', required=True, help='Path to a credentials JSON file that can list keys.')

  create_cmd = parser.add_command(main_create)
  create_cmd.add_argument('name', help='The application key name.')
  create_cmd.add_argument('-output', required=False, help='Path to output the generated key JSON; defaults to "{name}.json".')
  create_cmd.add_argument('-creds', required=True,
    help='Path to a credentials JSON file that can list buckets and create keys.')
  create_cmd.add_argument('-buckets', nargs='+', required=True, help='Names of the buckets.')
  create_cmd.add_argument('-capabilities', nargs='+', required=True,
    help='Capabilities for the key. Special values: "file-ro", "file-rw", "file-rwd".')

  parser.parse_and_run_command()


def main_list(args:Namespace) -> None:
  'List application keys.'

  if not path_exists(args.creds, follow=True):
    exit(f'Error: Credentials path does not exist: {args.creds!r}.')

  creds = B2Creds.load(args.creds)
  b2 = B2Api(InMemoryAccountInfo()) # type: ignore[no-untyped-call]
  b2.authorize_account(application_key_id=creds.key_id, application_key=creds.key_secret.val)

  keys = b2.list_keys()
  for key in keys:
    print(key.as_dict()) # type: ignore[no-untyped-call]


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
  b2 = B2Api(InMemoryAccountInfo()) # type: ignore[no-untyped-call]
  b2.authorize_account(application_key_id=creds.key_id, application_key=creds.key_secret.val)

  bucket_names = args.buckets
  assert bucket_names
  buckets:dict[str,str] = {}
  for bucket_name in bucket_names:
    bucket:Bucket = b2.get_bucket_by_name(bucket_name)
    buckets[bucket_name] = req_type(bucket.id_, str)

  bucket_ids = list(buckets.values())
  for name, id in buckets.items():
    print(f'bucket {name!r} -> {id!r}')

  key_info:FullApplicationKey = b2.create_key(key_name=args.name, capabilities=capabilities, bucket_ids=bucket_ids)
  creds = B2Creds.from_b2(key_info, frozendict(buckets))
  creds.save(out_path)


if __name__ == '__main__': main()
