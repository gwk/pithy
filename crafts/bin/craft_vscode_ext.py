# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from pithy.fs import is_dir, expand_user, remove_dir_contents_if_exists, copy_path, walk_files
from pithy.io import errSL
from pithy.string import replace_prefix



def main() -> None:
  arg_parser = ArgumentParser(description='Build VSCode extensions.')
  arg_parser.add_argument('-name')
  arg_parser.add_argument('-src')
  args = arg_parser.parse_args()
  name = args.name
  src = args.src

  for s in ('..', '/'):
    if s in name: exit(f'invalid name (contains {s!r}): {name!r}')

  dst = expand_user(f'~/.vscode-insiders/extensions/{name}')
  remove_dir_contents_if_exists(dst)

  src_path = f'{src}/package.json'
  dst_path = f'{dst}/package.json'
  errSL('copy:', src_path, dst_path)
  copy_path(src_path, dst_path, create_dirs=True)
  for d in ['configurations', 'grammars', 'themes']:
    src_dir = f'{src}/{d}'
    if is_dir(src_dir, follow=True):
      for src_path in walk_files(src_dir, file_exts='.json'):
        dst_path = replace_prefix(src_path, src, dst)
        errSL('copy:', src_path, dst_path)
        copy_path(src_path, dst_path, create_dirs=True)
