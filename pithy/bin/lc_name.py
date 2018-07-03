# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# rename files to have lower case extensions.

import os
from argparse import ArgumentParser
from sys import stderr
from pithy.fs import file_inode, path_join, split_dir_name, move_file, walk_files

def main() -> None:
  parser = ArgumentParser(description='Lower case file names.')
  parser.add_argument('paths', nargs='+', help='Paths to explore.')
  args = parser.parse_args()

  for path in walk_files(*args.paths):
    dir, name = split_dir_name(path)
    lc_name = name.lower()
    if lc_name == name:
      continue
    lc_path = path_join(dir, lc_name)
    try: inode = file_inode(lc_path)
    except FileNotFoundError: pass
    else:
      # OSX file system is case insensitive, so lc_path always appears to exist.
      # Check if it is really the same file by comparing inodes.
      if file_inode(path) != inode:
        print('error: {!r} -> {!r}; destination already exists.'.format(path, lc_path), file=stderr)
        continue
    move_file(path, to=lc_path, overwrite=True)


if __name__ == '__main__': main()
