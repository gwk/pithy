from math import pi

from pithy.vec import h_pi, V
from utest import utest


q_pi = pi * 0.25

# rot_z.

# Special codepath for 90 and 180 degrees that avoid floating point error.
utest(V(0, 1), V.rot_z, V(1, 0), rad=h_pi)
utest(V(-1, 0), V.rot_z, V(0, 1), rad=h_pi)

utest(V(1, 0), V.rot_z, V(0, 1), rad=-h_pi)
utest(V(0, -1), V.rot_z, V(1, 0), rad=-h_pi)

utest(V(-1, -1), V.rot_z, V(1, 1), rad=pi)
utest(V(1, 1), V.rot_z, V(-1, -1), rad=-pi)

# Normal trigonometric codepath.
utest(V(0.7071067811865476, 0.7071067811865475), V.rot_z, V(1, 0), rad=q_pi)
utest(V(-0.7071067811865475, 0.7071067811865476), V.rot_z, V(0, 1), rad=q_pi)


# det_xy.

utest(0, V.det_xy, V(1, 0), V(1, 0))
utest(1, V.det_xy, V(1, 0), V(0, 1))
utest(-1, V.det_xy, V(0, 1), V(1, 0))
