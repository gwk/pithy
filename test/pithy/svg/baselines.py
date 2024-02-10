#!/usr/bin/env python3

from pithy.io import outZ
from pithy.svg import alignment_baselines, Line, Svg, Text


svg = Svg(w=800, h=800)
for i, b in enumerate([None, *sorted(alignment_baselines)], 1):
  y = i * 48
  svg.append(Line((8, y), (256, y), stroke='#E0E0E0'))
  svg.append(Text(f'X -- {b}', pos=(8, y), alignment_baseline=b, style='font-size: 24px; background-color: blue'))

outZ(*svg.render())
