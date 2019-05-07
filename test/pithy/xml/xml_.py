#!/usr/bin/env python3

from utest import *
from pithy.xml import *



html = Xml(tag='html', lang='en-us')
head = html.append(Xml(tag='head', ch=[Xml(tag='title', ch=['TITLE'])]))
body = html.append(Xml(tag='body'))

div0 = body.append(Xml(tag='div', cl='DIV-CLASS', id='DIV-ID-0'))
p0 = div0.append(Xml(tag='p', ch=['Paragraph #0 text.\n\npost-newlines.\n']))

div1 = body.append(Xml(tag='div', cl='DIV-CLASS', id='DIV-ID-1'))
p1 = div1.append(Xml(tag='p', ch=['Paragraph #1 text.  post double space.\n']))

utest('en-us', html.get, 'lang')
utest(head, html.pick, 'head')

utest(div0, body.pick_first, tag='div')
utest(div0, html.find_first, tag='div')

utest_seq([div0, div1], body.pick_all, tag='div')
utest_seq([div0, div1], html.find_all, tag='div')
utest_seq([div0, div1], body.pick_all, cl='DIV-CLASS')
utest_seq([div0, div1], html.find_all, cl='DIV-CLASS')

utest(div1, body.pick_first, id='DIV-ID-1')
utest(div1, html.find_first, id='DIV-ID-1')

utest(p1, html.find, text='#1 text')

utest_exc(NoMatchError, html.pick, tag='nonexistant')
utest_exc(NoMatchError, html.find, tag='nonexistant')

utest_exc(MultipleMatchesError, body.pick, 'div')
utest_exc(MultipleMatchesError, html.find, 'div')

utest_exc(MultipleMatchesError, body.pick, cl='DIV-CLASS')
utest_exc(MultipleMatchesError, html.find, cl='DIV-CLASS')
