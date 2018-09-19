#!/usr/bin/env python3

from pithy.svg import *
from sys import stdout

w = 512
h = 1024
with Svg(w=w, h=h) as svg:
  svg.grid(size=(w, h), stroke='#E0E0E0', fill='white', stroke_width=0.5)

  y = 0

  with svg.g(translate(y=y)) as g:
    g.rect((0, 0), (64, 32), title='rect0', r=8)
    g.rect(x=80, y=0, w=64, h=32, r=(16, 8), stroke='gray', fill='white', title='rect1')
  y += 48

  with svg.g(translate(y=y)) as g:
    g.circle((16, 16), 16, title='circle0')
    g.circle(x=64, y=16, r=16, stroke='gray', fill='white', title='circle1')
  y += 48

  with svg.g(translate(y=y)) as g:
    g.line((0, 0), (32, 32), stroke='black', title='line0')
    g.line(x1=32, y1=0, x2=64, y2=32, stroke='black', title='line1')
  y += 48

  with svg.g(translate(y=y)) as g:
    g.path([('M', 0, 0), ('L', 32, 32), ('l', 32, -32)], stroke='black', fill=None, title='path0')
  y += 48

  with svg.g(translate(y=y)) as g:
    g.polyline([(0,0), (32,32), (64,0)], stroke='black', fill=None, title='polyline0')
  y += 48

  svg.text(x=0, y=y, text='TEXT')
  y += 16

  img_base64 = 'data:image/png;base64,R0lGODdhBAAEAIAAAAAAAP///yH5BAQAAAAALAAAAAAEAAQAAAIFRHxnuAUAOw=='

  svg.image((0, y), (16,16), href=img_base64)
  svg.image(x=32, y=y, w=32, h=32, href=img_base64)
  y += 48

  with svg.g(translate(y=y)) as g:
    with g.symbol(id='sym', vw=32, vh=32) as g1:
      g1.rect(pos=(8, 8), size=(16, 16), stroke='black', fill=None)
      g1.rect(pos=(0, 0), size=(32, 32), stroke='black', fill=None)
    g.use('sym', (0,0), 32)
    g.use('sym', (48,0), 16)
  y += 48

  with svg.g(translate(x=16, y=y)) as g:
    with g.marker(id='dot', pos=(4,4), size=8, vw=8, vh=8) as marker:
      marker.circle((4, 4), r=4)
    g.polyline([(0,0), (16,0), (32,0)], stroke='black', marker_start="url(#dot)", marker_mid="url(#dot)", marker_end="url(#dot)")
  y += 32

svg.write(stdout)
