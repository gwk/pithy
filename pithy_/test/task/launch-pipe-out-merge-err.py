#!/usr/bin/env python3

import os

from pithy.io import outZ
from pithy.pipe import DuplexPipe
from pithy.task import launch


fdr, fdw = os.pipe()

_cmd, proc, _input_bytes = launch(
  ['python3', '-c', 'from sys import stderr, stdout; print("std out."); stdout.flush(); print("std err.", file=stderr)'],
  out=fdw, err=fdw)

os.close(fdw)
while True:
  output = os.read(fdr, 4096)
  if not output: break
  outZ(output.decode())
os.close(fdr)
proc.wait()
