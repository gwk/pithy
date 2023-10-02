#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import json
import sys

from pithy.fs import walk_files
from pithy.io import errL


def main() -> None:

  for path in walk_files(*sys.argv[1:], file_exts='.json'):
    print(path)
    try:
      with open(path) as f:
        o = json.load(f)
      with open(path, 'w') as f:
        json.dump(o, f, sort_keys=True, indent=2)
        f.write('\n')
    except Exception as e:
      errL(f'error: {path}: {e}')
