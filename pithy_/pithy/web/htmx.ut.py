# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.html import Div, HtmlNode
from pithy.web.htmx import configure_htmx_event_replaced_attrs, hx_inherited, hx_trigger_on
from utest import utest, utest_exc


utest({'hx-target:inherited': 'this', 'hx-swap:inherited': 'outerHTML'}, hx_inherited, hx_target='this', hx_swap='outerHTML')

utest('itemsChanged from:body', hx_trigger_on, from_body='itemsChanged')
utest('a from:body, b from:body', hx_trigger_on, from_body=['a', 'b'])
utest('load, itemsChanged from:body', hx_trigger_on, 'load', from_body='itemsChanged')
utest('every 30s, intersect once, a from:body', hx_trigger_on, 'every 30s', 'intersect once', from_body=('a',))
utest('load', hx_trigger_on, 'load', from_body=())
utest_exc(ValueError('hx_trigger_on: no trigger clauses.'), hx_trigger_on, from_body=[])

configure_htmx_event_replaced_attrs()
utest('hx-on::before:request', HtmlNode.replaced_attrs.get, 'hx-on--before-request')
utest('hx-on::after:history:push', HtmlNode.replaced_attrs.get, 'hx-on--after-history-push')
utest("<div hx-on::before:request='f()'></div>\n", Div(hx_on__before_request='f()').render_str)
