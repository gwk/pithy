#!/usr/bin/env python3

from pithy.svg import Svg, Line, Text, alignment_baselines
from pithy.io import outZ


svg = Svg(w=800, h=800)
for i, b in enumerate([None, *sorted(alignment_baselines)], 1):
  y = i * 50
  svg.append(Line((0, y), (500, y), stroke='#E0E0E0'))
  svg.append(Text(f'X -- {b}', pos=(0, y), alignment_baseline=b, style='font-size: 24px; background-color: blue'))

outZ(*svg.render())
