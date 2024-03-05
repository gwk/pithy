# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from operator import add, mul, neg, sub, truediv

from pithy.vec import V
from utest import utest


utest(V(-1,-2), neg, V(1,2))

utest(V(4,6), add, V(1,2), V(3,4))

utest(V(0,0), sub, V(1,2), V(1,2))

utest(V(2,4), mul, V(1,2), 2)

utest(V(0.5, 1), truediv, V(1,2), 2)
