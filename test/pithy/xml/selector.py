#!/usr/bin/env python3

from utest import *
from pithy.xml import Xml
from pithy.xml.selector import *

xml = Xml.from_raw({'':'html', 'lang':'en-us',
  0:{'':'head',
    0:{'':'title', 0:'TITLE'}},
  1:{'':'body',
    0:{'':'div', 'class':'DIV-CLASS', 'id':'DIV-ID-0',
      0:'div 0 text.'},
    1:{'':'div', 'class':'DIV-CLASS', 'id':'DIV-ID-1',
      0:'div 0 text.'},
    }})

head = xml[0]
body = xml[1]
div0 = body[0]
div1 = body[1]

sel = XmlSel(xml)

utest(xml['lang'], sel.get, 'lang')
utest_repr("<head: title:'TITLE'>", sel.get, 'head')
utest_repr("<body: div:'div 0 text.' div:'div 0 text.'>", sel.get, 'body')

utest_exc(NoMatchError, sel.__getitem__, 'nonexistant')
utest_exc(MultipleMatchesError, sel.body.__getitem__, 'DIV-CLASS')

#from code import interact
#interact(local=locals())
