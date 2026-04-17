# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from copy import replace

from pithy.markup import Mu, TagMu
from utest import utest, utest_exc


utest(Mu(), Mu)

utest(TagMu(tag='div'), TagMu, tag='div')

utest(Mu(_=['x', 'y'], attrs={'a': 'a1'}), Mu, 'x', 'y', a='a1')

utest(Mu(attrs={'class':'c'}), Mu, cl='c')


utest(TagMu(tag='r'), replace, TagMu(tag='o'), tag='r')
utest(Mu(cl='r'), replace, Mu(cl='o'), cl='r')

utest(Mu(_=['x']), replace, Mu(_=['a', 'b']), _=['x'])

utest(Mu(a='a2', b='b'), replace, Mu(a='a1', b='b'), a='a2')
