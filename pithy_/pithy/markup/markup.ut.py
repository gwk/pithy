# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from copy import replace

from pithy.markup import Mu, TagMu
from utest import utest


utest(Mu(), Mu)

utest(TagMu(tag='div'), TagMu, tag='div')

utest(Mu(_=['x', 'y'], attrs={'a': 'a1'}), Mu, 'x', 'y', a='a1')

utest(Mu(attrs={'class':'c'}), Mu, cl='c')


utest(TagMu(tag='r'), replace, TagMu(tag='o'), tag='r')
utest(Mu(cl='r'), replace, Mu(cl='o'), cl='r')

utest(Mu(_=['x']), replace, Mu(_=['a', 'b']), _=['x'])

utest(Mu(a='a2', b='b'), replace, Mu(a='a1', b='b'), a='a2')


# Text and attribute values are stripped of the characters that escaping does not defend against.

utest('&amp;a&lt;b', Mu.esc_text, '&a<\u202eb')
utest('ab', Mu.esc_text, 'a\u200bb')
utest("'ab'", Mu.quote_attr_val, 'a\u202eb')
