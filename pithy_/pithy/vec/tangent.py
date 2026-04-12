# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from math import asin

from . import h_pi, V


def point_circle_tangent(p:V, *, c:V, r:float, sign:int) -> V:
  '''
  Compute the tangent point from point `p` to a Corner circle.
  The point is required to lie outside the circle; thus are always two possible tangents.
  (Note: we could define a special case for when `p` lies exactly on the circle).

  We choose the desired tangent by multiplying the calculated tangent angle by `sign` (+1 or -1).
  If sign is 1, then the tangent ray will be to the left of the line from `p` to `c`.
  '''
  assert sign == -1 or sign == 1
  pc = c - p
  d = pc.mag
  if d <= r: raise ValueError(f'Point {p} cannot lie inside circle ({c=}, {r=}).')

  centerline_angle = pc.angle_xy

  # Calculate the angle between the center and tangent rays.
  # The tangent is by definition at right angle to the radius, so the center line is the hypotenuse of a right triangle.
  tangent_angle = asin(r / d)

  # The tangent point is obtained by rotating the radius vector by a the tangent angle.
  return c + V(r).rot_z(centerline_angle + sign * (h_pi + tangent_angle))


def circles_bitangent(*, ac:V, ar:float, a_sign:int, bc:V, br:float, b_sign:int) -> tuple[V,V]:
  '''
  Compute the bitangent line between two circles.
  The circles may overlap but must not be identical.
  There are two or four possible bitangent lines.
  '''

  assert a_sign == -1 or a_sign == 1
  assert b_sign == -1 or b_sign == 1

  ab = bc - ac # The centerline vector from a to b.
  d = ab.mag
  if d == 0: raise ValueError(f'Circle centers must be distinct: {ac=}, {bc=}.')
  # TODO: if d < epsilon, raise error.

  if d <= ar + br and a_sign != b_sign:
    raise ValueError(f'Circles overlap; cross-tangent is not possible: {ac=}, {ar=}, {a_sign=}, {bc=}, {br=}, {b_sign=}.')

  centerline_angle = ab.angle_xy

  # Calculate the additional angle between the center and bitangent.
  # In order to do so, we treat each radius as a +/- offset, depending on the sign.
  sra = a_sign * ar
  srb = b_sign * br
  r_d = srb - sra
  tangent_angle = asin(r_d / d)

  # The tangent points are obtained by rotating the radius vectors by the tangent angle.
  return (
    ac + V(ar).rot_z(centerline_angle + a_sign*h_pi + tangent_angle),
    bc + V(br).rot_z(centerline_angle + b_sign*h_pi + tangent_angle))
