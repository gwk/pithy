#!/usr/bin/env python3

from utest import *
from pithy.svg import *


with SvgWriter(stdout, w=800, h=800, vx=0, vy=0, vw=800, vh=800) as svg:
  svg.rect(x=0, y=0, w=800, h=800)
  svg.rect(pos=(2, 2), size=(796, 796), stroke='red', fill=None)

  svg.circle(x=400, y=400, r=399, fill='white')
  svg.line((0, 0), (800, 800), stroke='green')
