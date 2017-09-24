#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from pithy.ansi import *
from pithy.io import *
from pithy.task import runCO


def main():
  c, o = runCO(['node_modules/.bin/tsc', *argv[1:]])
  for line in o.split('\n'):
    m = regex.match(line)
    if not m:
      outL(TXT_M, line, RST)
      continue
    path, line, col, kind, code, msg = m.groups()
    kind_color = TXT_Y if kind == 'warning' else TXT_R
    outL(f'{TXT_L}{path}:{line}:{col}: {kind_color}{kind}: {RST}{msg} {TXT_D}({code})')
  exit(c)


regex = re.compile(r'([^\(]+)\((\d+),(\d+)\): (error|warning) (\w+): (.+)')


if __name__ == '__main__': main()
