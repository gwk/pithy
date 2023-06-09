#!/usr/bin/env python3

from pithy.html import Div, Html, MultipleMatchesError, NoMatchError, P
from utest import utest, utest_exc, utest_seq, utest_val


src = '''
<!DOCTYPE HTML>
<html lang="en-us">
  <head>
    <title>TITLE</title>
    <meta charset="utf-8"/>
  </head>
  <body>
    <div id="d0" class="DIV-CLASS">
      <p>The P0 text.</p>
    </div>
    <div id="d1" class="DIV-CLASS">
      <h1>H1</h1>
      <p>The P1 text.</p>
    </div>
  </body>
</html>
'''


html = Html.parse(src)
head = html.head
body  = html.body

utest('en-us', html.get, 'lang')
utest(head, html.pick, 'head')
utest(head.title, html.find, 'title')

div0, div1 = body.child_nodes()
utest(True, isinstance, div0, Div)
utest(True, isinstance, div1, Div)

utest(div0, body.pick_first, Div)
utest(div0, html.find_first, Div)

utest_seq([div0, div1], body.pick_all, Div)
utest_seq([div0, div1], html.find_all, Div)
utest_seq([div0, div1], body.pick_all, cl='DIV-CLASS')
utest_seq([div0, div1], html.find_all, cl='DIV-CLASS')

utest(div1, body.pick_first, id='d1')
utest(div1, html.find_first, id='d1')

p1:P = div1.pick(P)
utest(p1, html.find, text='P1')

utest_exc(NoMatchError, html.pick, tag='nonexistent')
utest_exc(NoMatchError, html.find, tag='nonexistent')

utest_exc(MultipleMatchesError, body.pick, Div)
utest_exc(MultipleMatchesError, html.find, Div)

utest_exc(MultipleMatchesError, body.pick, cl='DIV-CLASS')
utest_exc(MultipleMatchesError, html.find, cl='DIV-CLASS')


sd0 = body.pick(id='d0', traversable=True)
sd1 = html.find(id='d1', traversable=True)

utest_val(div0, sd0.orig, 'sd0.orig')
utest_val(div1, sd1.orig, 'sd1.orig')

utest(div1, sd0.next)
utest(div0, sd1.prev)
