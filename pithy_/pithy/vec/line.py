# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from . import V


def intersect_lines(a:tuple[V,V], b:tuple[V,V]) -> V|None:
  'Given two infinite lines, return the intersection point if it exists or else None.'

  a0, a1 = a
  b0, b1 = b
  da = a1 - a0
  db = b1 - b0

  det = da.det_xy(db)
  if det == 0: return None  # Lines are parallel or coincident

  # Calculate the interpolation parameter 't' from a0.
  ta0 = (b0 - a0).det_xy(b1 - a0) / det

  return a0 + da * ta0



def project_point_onto_line(p:V, a:V, b:V) -> V:
  'Project point p onto the line defined by points a and b.'
  ab = b - a
  mag2 = ab.mag2
  if mag2 == 0: return a # Line is ill-defined, but we can still return the provided point.
  ap = p - a
  proj = ab * ap.dot(ab) / mag2
  return a + proj
