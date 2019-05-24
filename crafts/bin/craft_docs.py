# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from pithy.ansi import *
from pithy.fs import *
from pithy.io import *
from pithy.string import *
from pithy.task import *


def main() -> None:
  run('muck doc/index.html', exits=True)
  remove_dir_contents('docs/')
  # TODO: would be better to have muck tells us what all of the data dependencies are.
  for src in walk_files('_build/doc', file_exts=['.css', '.html', '.jpg', '.js', '.png', '.svg']):
    copy_path(src, replace_prefix(src, prefix='_build/doc', replacement='docs'))
  with open('readme.md', 'w') as f:
    run('html-extract docs/index.html -id s0', out=f, exits=True)


if __name__ == '__main__': main()
