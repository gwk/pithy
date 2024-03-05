# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.vec import V
from pithy.vec.tangent import circles_bitangent, point_circle_tangent
from utest import utest


# point_circle_tangent

# Degenerate zero radius circle.
utest(V(1, 0), point_circle_tangent, V(0, 0), c=V(1, 0), r=0, sign=1)
utest(V(1, 0), point_circle_tangent, V(0, 0), c=V(1, 0), r=0, sign=-1)

utest(V(1, 2), point_circle_tangent, V(1, 1), c=V(2,2), r=1, sign=1)
utest(V(2, 1), point_circle_tangent, V(1, 1), c=V(2,2), r=1, sign=-1)

utest(V(1.5000000000000002, 0.8660254037844387), point_circle_tangent, V(0, 0), c=V(2, 0), r=1, sign=1)
utest(V(1.5000000000000002, -0.8660254037844387), point_circle_tangent, V(0, 0), c=V(2, 0), r=1, sign=-1)


# circles_bitangent.

# Degenerate zero radius circles.
utest((V(0,0), V(1,0)), circles_bitangent, ac=V(0,0), ar=0, a_sign=1, bc=V(1,0), br=0, b_sign=1)

utest((V(0,0), V(1.5000000000000002, 0.8660254037844387)), circles_bitangent, ac=V(0,0), ar=0, a_sign=1, bc=V(2,0), br=1, b_sign=1)
utest((V(0,0), V(1.5000000000000002, -0.8660254037844387)), circles_bitangent, ac=V(0,0), ar=0, a_sign=1, bc=V(2,0), br=1, b_sign=-1)

utest((V(1,1), V(1,2)), circles_bitangent, ac=V(1, 1), ar=0, a_sign=1, bc=V(2,2), br=1, b_sign=1)
utest((V(1,1), V(2,1)), circles_bitangent, ac=V(1, 1), ar=0, a_sign=1, bc=V(2,2), br=1, b_sign=-1)

utest((V(0,1), V(2,1)), circles_bitangent, ac=V(0,0), ar=1, a_sign=1, bc=V(2,0), br=1, b_sign=1)
utest((V(0,-1), V(2,-1)), circles_bitangent, ac=V(0,0), ar=1, a_sign=-1, bc=V(2,0), br=1, b_sign=-1)
