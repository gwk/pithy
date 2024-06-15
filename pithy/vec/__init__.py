# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Sequence
from dataclasses import dataclass
from math import atan2, cos, isfinite, pi, sin, sqrt
from typing import overload, Union


h_pi = pi * 0.5


def _fmt_float(f:float) -> str:
  i = int(f)
  return str(i) if f == i else str(f)


@dataclass(frozen=True, slots=True)
class V(Sequence[float]):
  '''
  V is a 3D vector type.
  The components are named x, y, and z.
  Each component defaults to zero if not specified.
  '''

  x:float = 0
  y:float = 0
  z:float = 0


  def __str__(self) -> str:
    if self.z == 0:
      return f'({_fmt_float(self.x)},{_fmt_float(self.y)})'
    return f'({_fmt_float(self.x)},{_fmt_float(self.y)},{_fmt_float(self.z)})'


  def __repr__(self) -> str: return f'V{self}'


  # Arithmetic operations.

  def __neg__(self) -> 'V': return V(-self.x, -self.y, -self.z)


  def __bool__(self) -> bool: return bool(self.x or self.y or self.z)


  def __add__(self, r:'V') -> 'V':
    if not isinstance(r, V): return NotImplemented # type: ignore[unreachable]
    return V(self.x+r.x, self.y+r.y, self.z+r.z)


  def __sub__(self, r:'V') -> 'V':
    if not isinstance(r, V): return NotImplemented # type: ignore[unreachable]
    return V(self.x - r.x, self.y - r.y, self.z - r.z)


  def __mul__(self, s:Union[float,'V']) -> 'V':
    if isinstance(s, V): # Elementwise multiplication
      return V(self.x*s.x, self.y*s.y, self.z*s.z)
    if not isinstance(s, (int, float)): return NotImplemented # type: ignore[unreachable]
    return V(self.x*s, self.y*s, self.z*s)


  def __truediv__(self, r:Union[float,'V']) -> 'V':
    if isinstance(r, V): # Elementwise division
      return V(self.x / r.x, self.y / r.y, self.z / r.z)
    if not isinstance(r, (int, float)): return NotImplemented # type: ignore[unreachable]
    return V(self.x / r, self.y / r, self.z / r)


  def __len__(self) -> int: return 3


  def __iter__(self):
    yield self.x
    yield self.y
    yield self.z


  @overload
  def __getitem__(self, i:int) -> float: ...

  @overload
  def __getitem__(self, i:slice) -> tuple[float]: ...

  def __getitem__(self, i):
    match i:
      case 0: return self.x
      case 1: return self.y
      case 2: return self.z
      case _: # Assume that `i` is a slice.
        return (self.x, self.y, self.z)[i]

  @property
  def xy(self) -> 'V': return V(self.x, self.y)

  @property
  def xz(self) -> 'V': return V(self.x, self.z)

  @property
  def yz(self) -> 'V': return V(self.y, self.z)

  @property
  def yx(self) -> 'V': return V(self.y, self.x)

  @property
  def zx(self) -> 'V': return V(self.z, self.x)

  @property
  def zy(self) -> 'V': return V(self.z, self.y)


  @property
  def is_finite(self) -> bool:
    return isfinite(self.x) and isfinite(self.y) and isfinite(self.z)


  @property
  def mag(self) -> float:
    'Magnitude (length) of the vector.'
    return sqrt(self.x**2 + self.y**2 + self.z**2)


  @property
  def mag2(self) -> float:
    'Magnitude squared of the vector.'
    return self.x**2 + self.y**2 + self.z**2


  @property
  def norm(self) -> 'V':
    'Normalized vector.'
    l = self.mag
    if not self.mag > 0: raise ValueError(f'Cannot normalize zero vector: {self}.')
    n = self / l
    if not n.is_finite: raise ValueError(f'Normalized vector is not finite: {n}.')
    return n


  @property
  def perp_xy_left(self) -> 'V':
    'Perpendicular vector to the left.'
    return V(-self.y, self.x)


  @property
  def perp_xy_right(self) -> 'V':
    'Perpendicular vector to the right.'
    return V(self.y, -self.x)


  @property
  def angle_xy(self) -> float:
    'Angle in the xy plane from the positive x axis.'
    return atan2(self.y, self.x)


  def cross(self, r:'V') -> 'V':
    'Cross product.'
    return V(
      self.y*r.z - self.z*r.y,
      self.z*r.x - self.x*r.z,
      self.x*r.y - self.y*r.x)


  def det_xy(self, r:'V') -> float:
    '''
    The determinant of two 2D vectors is the signed area of the parallelogram defined by the vectors in the xy plane.
    This is equivalent to the Z component of the cross product.
    '''
    return self.x*r.y - self.y*r.x


  def dist(self, r:'V') -> float:
    'Distance to another vector.'
    return (self - r).mag


  def dot(self, r:'V') -> float:
    'Dot product.'
    return self.x*r.x + self.y*r.y + self.z*r.z


  def mid(self, r:'V') -> 'V':
    'Midpoint between two vectors.'
    return (self + r) * 0.5


  def req_no_z(self) -> None:
    if self.z: raise ValueError(f'V.z component is non-zero: {self!r}')


  def rot_z(self, rad:float) -> 'V':
    'Rotate around the positive Z axis by `rad` radians.'
    # Special case the 90, 180 degree rotation cases to avoid floating point error.
    if rad == h_pi:
      return V(-self.y, self.x, self.z)
    if rad == -h_pi:
      return V(self.y, -self.x, self.z)
    if rad == pi or rad == -pi:
      return V(-self.x, -self.y, self.z)
    return V(
      self.x*cos(rad) - self.y*sin(rad),
      self.x*sin(rad) + self.y*cos(rad),
      self.z)
