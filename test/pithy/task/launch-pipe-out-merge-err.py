#!/usr/bin/env python3

from utest import *
import os
from pithy.task import launch
from pithy.pipe import DuplexPipe
from pithy.io import outZ

fdr, fdw = os.pipe()
_, proc, _ = launch(['python3', '-c', 'from sys import stderr; print("std out."); print("std err.", file=stderr)'], out=fdw, err=fdw)
os.close(fdw)
while True:
  output = os.read(fdr, 4096)
  if not output: break
  outZ(output.decode())
os.close(fdr)
proc.wait()
