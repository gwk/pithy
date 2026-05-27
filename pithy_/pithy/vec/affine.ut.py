# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from math import pi

from pithy.vec import V
from pithy.vec.affine import AffineMat
from utest import utest, utest_val


h_pi = pi * 0.5


# identity.
utest_val(True, AffineMat().is_identity)
utest(V(1, 2, 3), AffineMat().__mul__, V(1, 2, 3))

# translate.
utest(AffineMat(tx=3, ty=4), AffineMat.translate, 3, 4)
utest(AffineMat(tx=3, ty=4, tz=5), AffineMat.translate, 3, 4, 5)
utest(V(4, 6, 0), AffineMat.translate(3, 4).__mul__, V(1, 2, 0))
utest(V(4, 6, 8), AffineMat.translate(3, 4, 5).__mul__, V(1, 2, 3))
utest(AffineMat(tx=1, ty=2, tz=3), AffineMat.translate_v, V(1, 2, 3))

# scale.
utest(AffineMat(xx=2, yy=3, zz=4), AffineMat.scale, 2, 3, 4)
utest(AffineMat(xx=5, yy=5, zz=5), AffineMat.scale, 5)
utest(V(2, 6, 12), AffineMat.scale(2, 3, 4).__mul__, V(1, 2, 3))

# rotate_z.
utest(AffineMat(xx=0, xy=1, yx=-1, yy=0), AffineMat.rotate_z, h_pi)
utest(AffineMat(xx=0, xy=-1, yx=1, yy=0), AffineMat.rotate_z, -h_pi)
utest(AffineMat(xx=-1, xy=0, yx=0, yy=-1), AffineMat.rotate_z, pi)
# 90 deg CCW: (1,0,0) -> (0,1,0).
utest(V(0, 1, 0), AffineMat.rotate_z(h_pi).__mul__, V(1, 0, 0))
# 90 deg CCW: (0,1,0) -> (-1,0,0).
utest(V(-1, 0, 0), AffineMat.rotate_z(h_pi).__mul__, V(0, 1, 0))
# Z is unaffected.
utest(V(0, 1, 7), AffineMat.rotate_z(h_pi).__mul__, V(1, 0, 7))

# rotate_x.
utest(AffineMat(yy=0, yz=1, zy=-1, zz=0), AffineMat.rotate_x, h_pi)
utest(AffineMat(yy=0, yz=-1, zy=1, zz=0), AffineMat.rotate_x, -h_pi)
utest(AffineMat(yy=-1, yz=0, zy=0, zz=-1), AffineMat.rotate_x, pi)
# 90 deg CCW about X: (0,1,0) -> (0,0,1).
utest(V(0, 0, 1), AffineMat.rotate_x(h_pi).__mul__, V(0, 1, 0))
# 90 deg CCW about X: (0,0,1) -> (0,-1,0).
utest(V(0, -1, 0), AffineMat.rotate_x(h_pi).__mul__, V(0, 0, 1))
# X is unaffected.
utest(V(7, 0, 1), AffineMat.rotate_x(h_pi).__mul__, V(7, 1, 0))

# rotate_y.
utest(AffineMat(xx=0, xz=-1, zx=1, zz=0), AffineMat.rotate_y, h_pi)
utest(AffineMat(xx=0, xz=1, zx=-1, zz=0), AffineMat.rotate_y, -h_pi)
utest(AffineMat(xx=-1, xz=0, zx=0, zz=-1), AffineMat.rotate_y, pi)
# 90 deg CCW about Y: (0,0,1) -> (1,0,0).
utest(V(1, 0, 0), AffineMat.rotate_y(h_pi).__mul__, V(0, 0, 1))
# 90 deg CCW about Y: (1,0,0) -> (0,0,-1).
utest(V(0, 0, -1), AffineMat.rotate_y(h_pi).__mul__, V(1, 0, 0))
# Y is unaffected.
utest(V(1, 7, 0), AffineMat.rotate_y(h_pi).__mul__, V(0, 7, 1))

# rotate_z_about: rotating (2,0) 90 deg CCW about (1,0) gives (1,1).
utest(V(1, 1, 0), AffineMat.rotate_z_about(h_pi, 1, 0).__mul__, V(2, 0, 0))
utest(V(1, 1, 0), AffineMat.rotate_z_about_v(h_pi, V(1, 0)).__mul__, V(2, 0, 0))

# compose (*).
t = AffineMat.translate(10, 20, 30)
s = AffineMat.scale(2)
# Scale then translate: (1,1,1) -> (2,2,2) -> (12,22,32).
utest(V(12, 22, 32), (t @ s).__mul__, V(1, 1, 1))
# Translate then scale: (1,1,1) -> (11,21,31) -> (22,42,62).
utest(V(22, 42, 62), (s @ t).__mul__, V(1, 1, 1))

# inv: composing with inverse gives identity (within floating point).

_eps = 1e-12

for m in [
  AffineMat.translate(3, -7, 5),
  AffineMat.scale(2, 5, 3),
  AffineMat.rotate_z(h_pi),
  AffineMat.rotate_x(h_pi),
  AffineMat.rotate_y(h_pi),
  AffineMat.rotate_z(1.23),
  AffineMat.translate(3, 4, 1) @ AffineMat.rotate_z(0.5) @ AffineMat.scale(2, 3, 4),
  AffineMat.rotate_x(0.3) @ AffineMat.rotate_y(0.7) @ AffineMat.rotate_z(1.1),
 ]:
  p = V(5, 7, 11)
  recovered = m.inv * (m * p)
  utest_val(abs(recovered.x - p.x) < _eps, True)
  utest_val(abs(recovered.y - p.y) < _eps, True)
  utest_val(abs(recovered.z - p.z) < _eps, True)


# is_flat.
utest_val(True, AffineMat().is_flat)
utest_val(True, AffineMat.translate(3, 4).is_flat)
utest_val(True, AffineMat.rotate_z(h_pi).is_flat)
utest_val(False, AffineMat.rotate_x(h_pi).is_flat)
utest_val(False, AffineMat.rotate_y(h_pi).is_flat)


# to_svg_matrix.

utest('matrix(1,0,0,1,3,4)', AffineMat.translate(3, 4).to_svg_matrix)
utest('matrix(0,1,-1,0,0,0)', AffineMat.rotate_z(h_pi).to_svg_matrix)
