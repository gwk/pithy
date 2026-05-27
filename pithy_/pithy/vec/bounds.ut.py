# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.vec import V, VecBounds
from utest import utest, utest_val


# Single vector: l and h are both that vector.
b = VecBounds(V(1, 2, 3))
utest_val(V(1, 2, 3), b.l)
utest_val(V(1, 2, 3), b.h)

# Two vectors: l/h are the component-wise min/max.
b = VecBounds(V(0, 0, 0), V(1, 2, 3))
utest_val(V(0, 0, 0), b.l)
utest_val(V(1, 2, 3), b.h)

# Order of arguments does not matter.
b = VecBounds(V(1, 2, 3), V(0, 0, 0))
utest_val(V(0, 0, 0), b.l)
utest_val(V(1, 2, 3), b.h)

# Mixed-sign vectors: per-component min/max, not by-vector ordering.
b = VecBounds(V(-1, 5, 0), V(3, -2, 4))
utest_val(V(-1, -2, 0), b.l)
utest_val(V(3, 5, 4), b.h)

# Constructing from an existing VecBounds passes through unchanged.
inner = VecBounds(V(1, 2, 3), V(4, 5, 6))
utest(inner, VecBounds, inner)

# Expanding a VecBounds with an additional V.
inner = VecBounds(V(1, 2, 3), V(4, 5, 6))
expanded = VecBounds(inner, V(0, 9, 3))
utest_val(V(0, 2, 3), expanded.l)
utest_val(V(4, 9, 6), expanded.h)
