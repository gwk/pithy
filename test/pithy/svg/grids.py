#!/usr/bin/env python3

from pithy.svg import *
from sys import stdout

s = 40

with Svg(stdout, w=1024, h=1024, stroke='black', fill='white', stroke_width=2) as svg:
  y = 5
  svg.grid(title='grid0', pos=(5, y), size=s, step=10, corner_radius=4)
  svg.grid(title='grid1 (offset)', pos=(55, y), size=s, step=10, corner_radius=4, off=(5, 5))
