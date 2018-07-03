#!/usr/bin/env python3

from pithy.svg import *
from sys import stdout

s = 40

with SvgWriter(stdout, w=1024, h=1024, stroke='black', fill='white', stroke_width=2) as svg:
  y = 5
  svg.grid(title='snap=False', pos=(5, y), size=s, step=10, r=4)
  svg.grid(title='snap=True', pos=(55, y), size=s, step=10, r=4, off=(5, 5))
