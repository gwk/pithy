# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.markup import Mu, TagMu
from utest import utest, utest_exc


utest(Mu(), Mu)

utest(TagMu(tag='div'), TagMu, tag='div')

utest(Mu(_=['x', 'y'], attrs={'a': 'a1'}), Mu, 'x', 'y', a='a1')

utest(Mu(attrs={'class':'c'}), Mu, cl='c')
