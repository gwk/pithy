# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.web.htmx import hx_inherited, hx_trigger_on
from utest import utest, utest_exc


utest({'hx-target:inherited': 'this', 'hx-swap:inherited': 'outerHTML'}, hx_inherited, hx_target='this', hx_swap='outerHTML')

utest('itemsChanged from:body', hx_trigger_on, from_body='itemsChanged')
utest('a from:body, b from:body', hx_trigger_on, from_body=['a', 'b'])
utest('load, itemsChanged from:body', hx_trigger_on, 'load', from_body='itemsChanged')
utest('every 30s, intersect once, a from:body', hx_trigger_on, 'every 30s', 'intersect once', from_body=('a',))
utest('load', hx_trigger_on, 'load', from_body=())
utest_exc(ValueError('hx_trigger_on: no trigger clauses.'), hx_trigger_on, from_body=[])
