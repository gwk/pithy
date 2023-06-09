#!/usr/bin/env python3

from pithy.io import outZ
from pithy.svg import *


s = 40
y = 5

svg = Svg(w=512, h=512, stroke='black', fill='white', stroke_width=2)
svg.grid(title='grid0', pos=(5, y), size=s, step=10, corner_radius=4)
svg.grid(title='grid1 (offset)', pos=(55, y), size=s, step=10, corner_radius=4, offset=(5, 5))

outZ(*svg.render())
