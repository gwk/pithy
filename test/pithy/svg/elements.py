#!/usr/bin/env python3

from pithy.svg import *
from sys import stdout

w = 512
h = 1024
with SvgWriter(stdout, w=w, h=h) as svg:
  svg.grid(size=(w, h), stroke='#E0E0E0', fill='white', stroke_width=0.5)

  y = 0

  with svg.g(translate(y=y)):
    svg.rect((0, 0), (64, 32), r=8, title='rect0')
    svg.rect(x=80, y=0, w=64, h=32, r=(16, 8), stroke='gray', fill='white', title='rect1')
  y += 48

  with svg.g(translate(y=y)):
    svg.circle((16, 16), 16, title='circle0')
    svg.circle(x=64, y=16, r=16, stroke='gray', fill='white', title='circle1')
  y += 48

  with svg.g(translate(y=y)):
    svg.line((0, 0), (32, 32), stroke='black', title='line0')
    svg.line(x1=32, y1=0, x2=64, y2=32, stroke='black', title='line1')
  y += 48

  with svg.g(translate(y=y)):
    svg.path([('M', 0, 0), ('L', 32, 32), ('l', 32, -32)], stroke='black', fill=None, title='path0')
  y += 48

  with svg.g(translate(y=y)):
    svg.polyline([(0,0), (32,32), (64,0)], stroke='black', fill=None, title='polyline0')
  y += 48

  svg.text(x=0, y=y, text='TEXT')
  y += 16

  img_base64 = 'data:image/png;base64,R0lGODdhBAAEAIAAAAAAAP///yH5BAQAAAAALAAAAAAEAAQAAAIFRHxnuAUAOw=='

  svg.image((0, y), (16,16), href=img_base64)
  svg.image(x=32, y=y, w=32, h=32, href=img_base64)
  y += 48

  with svg.g(translate(y=y)):
    with svg.symbol(id='sym', vw=32, vh=32):
      svg.rect(pos=(8, 8), size=(16, 16), stroke='black', fill=None)
      svg.rect(pos=(0, 0), size=(32, 32), stroke='black', fill=None)
    svg.use('sym', (0,0), 32)
    svg.use('sym', (48,0), 16)
  y += 48

  with svg.g(translate(x=16, y=y)):
    with svg.marker(id='dot', pos=(4,4), size=8, vw=8, vh=8):
      svg.circle((4, 4), r=4)
    svg.polyline([(0,0), (16,0), (32,0)], stroke='black', marker_start="url(#dot)", marker_mid="url(#dot)", marker_end="url(#dot)")
  y += 32
