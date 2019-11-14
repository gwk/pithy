# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# count file extensions found in a directory tree.

# TODO:
# implement path arguments
# multiple arguments should cause each directory to be recursed
# stats should be printed for each directory when completed, then total stats when all done.

# implement ext listing (-l)
#  usage example: count-ext -l "mp3 m4a"
#  this would cause the relative path of each file matching the given extensions to be listed
#  in this case don't print stats, so that the results can be piped to other utilities


import os
from argparse import ArgumentParser
from ..fs import path_ext, walk_files
from typing import *


def main() -> None:
  parser = ArgumentParser(description='Count lines of source code.')
  parser.add_argument('paths', nargs='+', help='Directories to explore.')
  args = parser.parse_args()

  ext_counts = DefaultDict[str,int](int)

  for path in walk_files(*args.paths):
    ext = path_ext(path)
    ext_counts[ext] += 1

  empty_name = '[none]'
  max_len = max(len(empty_name), max(len(k) for k in ext_counts))

  for k in sorted(ext_counts.keys()):
    v = ext_counts[k]
    print('{0:{1}}: {2}'.format(k or empty_name, max_len, v))


if __name__ == '__main__': main()
