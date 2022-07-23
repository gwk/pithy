#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import plistlib
import yaml

from sys import stdout, argv

from pithy.io import outL
from pithy.fs import walk_files
from pithy.schema import compile_schema, write_schema
from pithy.json import load_json


def main() -> None:

  syntaxes = []

  for path in walk_files(*argv[1:], file_exts=['.json', '.plist', '.yaml']):
    outL(path)
    if path.endswith('.json'):
      syntax = load_json(open(path))
    elif path.endswith('.plist'):
      syntax = plistlib.load(open(path, 'rb'))
    elif path.endswith('.yaml'):
      syntax = yaml.load(open(path))
    else: exit("unsupported extension")
    syntaxes.append(syntax)

  schema = compile_schema(*syntaxes)

  outL()
  write_schema(stdout, schema)
