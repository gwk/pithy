#!/usr/bin/env python3

from utest import *
from pithy.xml.selector import *

s = XmlSel({'':'html', 'LANG':'a', 0:'b', 1:{'':'head', 'y':'y'}})
