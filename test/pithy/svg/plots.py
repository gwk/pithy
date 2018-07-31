#!/usr/bin/env python3

from pithy.svg import *
from pithy.num import NumRange
from sys import stdout
from math import sin, pi


size = (400,200)

with Svg(stdout, w=1000, h=1000, stroke='black', fill='white', stroke_width=1) as svg:

  y = 5
  r = NumRange(0, 1, 1/16, closed=True)
  with svg.plot(pos=(5, y), size=size, title_h=12, tick_w=32, tick_h=12,
   title='Identity and Sin',
   grid_step=0.25,
   tick_step=(0.25, 0.25),
   tick_x=True, tick_y=True,
   series=[
    LineSeries('identity', [(x, x) for x in r]),
    LineSeries('sin', [(x, sin(x*2*pi)) for x in r])
   ]):
    pass
