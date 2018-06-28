#!/usr/bin/env python3

from pithy.svg import *

with SvgWriter(w=800, h=800) as svg:
  for i, b in enumerate([None] + sorted(baselines), 1):
    y = i * 50
    svg.line((0, y), (500, y), stroke='#E0E0E0')
    svg.text((0, y), alignment_baseline=b, style='font-size: 24px; background-color: blue', text=b)
