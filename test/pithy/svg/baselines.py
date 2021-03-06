#!/usr/bin/env python3

from pithy.svg import *
from sys import stdout

with Svg(w=800, h=800) as svg:
  for i, b in enumerate([None] + sorted(alignment_baselines), 1):
    y = i * 50
    svg.line((0, y), (500, y), stroke='#E0E0E0')
    svg.text(f'X -- {b}', pos=(0, y), alignment_baseline=b, style='font-size: 24px; background-color: blue')

svg.write(stdout)
