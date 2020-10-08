#!/usr/bin/env python3

from sys import argv, stderr, stdout
from pithy.json import format_json_bytes
out_raw = stdout.buffer


def main():
  for path in argv[1:]:
    fmt_json(path)




main()
