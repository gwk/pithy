#!/usr/bin/env python3

from pithy.markup import MultipleMatchesError, NoMatchError
from pithy.xml import Xml
from utest import utest, utest_exc, utest_seq, utest_val


html = Xml(tag='html', lang='en-us')
head = html.append(Xml(tag='head', ch=[Xml(tag='title', ch=['TITLE'])]))
body = html.append(Xml(tag='body'))

div0 = body.append(Xml(tag='div', cl='DIV-CLASS', id='DIV-ID-0'))
p0 = div0.append(Xml(tag='p', ch=['Paragraph #0 text.\n\npost-newlines.\n']))

div1 = body.append(Xml(tag='div', cl='DIV-CLASS', id='DIV-ID-1'))
p1 = div1.append(Xml(tag='p', ch=['Paragraph #1 text.  post double space.\n']))

utest('en-us', html.get, 'lang')
utest(head, html.pick, 'head')

utest(div0, body.pick_first, 'div')
utest(div0, html.find_first, 'div')

utest_seq([div0, div1], body.pick_all, 'div')
utest_seq([div0, div1], html.find_all, 'div')
utest_seq([div0, div1], body.pick_all, cl='DIV-CLASS')
utest_seq([div0, div1], html.find_all, cl='DIV-CLASS')

utest(div1, body.pick_first, id='DIV-ID-1')
utest(div1, html.find_first, id='DIV-ID-1')

utest(p1, html.find, text='#1 text')

utest_exc(NoMatchError, html.pick, 'nonexistent')
utest_exc(NoMatchError, html.find, 'nonexistent')

utest_exc(MultipleMatchesError, body.pick, 'div')
utest_exc(MultipleMatchesError, html.find, 'div')

utest_exc(MultipleMatchesError, body.pick, cl='DIV-CLASS')
utest_exc(MultipleMatchesError, html.find, cl='DIV-CLASS')


sd0 = body.pick(id='DIV-ID-0', traversable=True)
sd1 = html.find(id='DIV-ID-1', traversable=True)

utest_val(div0, sd0.orig, 'sd0.orig')
utest_val(div1, sd1.orig, 'sd1.orig')

utest(div1, sd0.next)
utest(div0, sd1.prev)
