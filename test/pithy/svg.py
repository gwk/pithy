#!/usr/bin/env python3

from utest import *
from pithy.svg import *


with SvgWriter(stdout, w=800, h=800, vx=0, vy=0, vw=800, vh=800) as svg:
  svg.style('g{'+'color:blue;'+'font-family:Times}')
  svg.rect(x=0, y=0, w=800, h=800)
  svg.rect(pos=(2, 2), size=(796, 796), stroke='red', fill=None)

  svg.circle(x=400, y=400, r=399, fill='white')
  svg.line((0, 0), (800, 800), stroke='green')
  svg.text(x=30, y=30, text='test text', style='fill: red;')
  with svg.g():
    svg.path(('M', 10, 30), ('A', 20,20, 0,0,1, 50,30), fill='none', stroke='black')
    svg.image(x=50, y=50, size=(50,50), href='test.png')

  with svg.symbol(id='testSymbol', vx=0,vy=0,vw=80,vh=80):
    svg.rect(pos=(2, 2), size=(796, 796), stroke='red', fill=None)

  svg.use(id='#testSymbol', pos=(0,0), w=20, h=20)

  with svg.marker(id='dot', w=5, h=5, x=5, y=5, vx=0, vy=0, vw=10, vh=10):
    svg.circle(x=400, y=400, r=399, fill='white')

  svg.polyline((0,0), (10,10), (20,10), style='fill:none;stroke:black;stroke-width:3')
