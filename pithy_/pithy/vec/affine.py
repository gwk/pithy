# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from dataclasses import dataclass
from math import cos, pi, sin

from . import V


h_pi = pi * 0.5


@dataclass(frozen=True, slots=True)
class AffineMat:
  '''
  A 3D affine transformation stored in column-major order with basis-vector naming.

    [ xx  yx  zx  tx ]
    [ xy  yy  zy  ty ]
    [ xz  yz  zz  tz ]
    [  0   0   0   1 ]

  The final row is fixed and not stored.

  Defaults to the identity transform.
  '''

  xx:float = 1; xy:float = 0; xz:float = 0
  yx:float = 0; yy:float = 1; yz:float = 0
  zx:float = 0; zy:float = 0; zz:float = 1
  tx:float = 0; ty:float = 0; tz:float = 0


  def __repr__(self) -> str:
    return (
      f'AffineMat('
      f'xx={self.xx},xy={self.xy},xz={self.xz}, '
      f'yx={self.yx},yy={self.yy},yz={self.yz}, '
      f'zx={self.zx},zy={self.zy},zz={self.zz}, '
      f'tx={self.tx},ty={self.ty},tz={self.tz})')



  def __matmul__(self, other:AffineMat) -> AffineMat:
    '''
    Matrix multiplication composes self with another AffineMat (returns AffineMat).
    '''
    # For each column of r, multiply by self's linear part; add self's translation to the translation column.
    # Naming: s_* = self's fields, r_* = r's fields.
    sxx, sxy, sxz = self.xx, self.xy, self.xz
    syx, syy, syz = self.yx, self.yy, self.yz
    szx, szy, szz = self.zx, self.zy, self.zz
    stx, sty, stz = self.tx, self.ty, self.tz

    rxx, rxy, rxz = other.xx, other.xy, other.xz
    ryx, ryy, ryz = other.yx, other.yy, other.yz
    rzx, rzy, rzz = other.zx, other.zy, other.zz
    rtx, rty, rtz = other.tx, other.ty, other.tz

    return AffineMat(
      # x-basis column.
      xx=sxx*rxx + syx*rxy + szx*rxz,
      xy=sxy*rxx + syy*rxy + szy*rxz,
      xz=sxz*rxx + syz*rxy + szz*rxz,
      # y-basis column.
      yx=sxx*ryx + syx*ryy + szx*ryz,
      yy=sxy*ryx + syy*ryy + szy*ryz,
      yz=sxz*ryx + syz*ryy + szz*ryz,
      # z-basis column.
      zx=sxx*rzx + syx*rzy + szx*rzz,
      zy=sxy*rzx + syy*rzy + szy*rzz,
      zz=sxz*rzx + syz*rzy + szz*rzz,
      # Translation column.
      tx=sxx*rtx + syx*rty + szx*rtz + stx,
      ty=sxy*rtx + syy*rty + szy*rtz + sty,
      tz=sxz*rtx + syz*rty + szz*rtz + stz)


  def __mul__(self, other:V) -> V:
    'Normal multiplication applies the matrix transform to a V.'
    return V(
      self.xx*other.x + self.yx*other.y + self.zx*other.z + self.tx,
      self.xy*other.x + self.yy*other.y + self.zy*other.z + self.ty,
      self.xz*other.x + self.yz*other.y + self.zz*other.z + self.tz)


  @property
  def det(self) -> float:
    'Determinant of the 3x3 linear part, via cofactor expansion along the first row.'
    xx, xy, xz = self.xx, self.xy, self.xz
    yx, yy, yz = self.yx, self.yy, self.yz
    zx, zy, zz = self.zx, self.zy, self.zz
    return xx*(yy*zz - zy*yz) - yx*(xy*zz - zy*xz) + zx*(xy*yz - yy*xz)


  @property
  def inv(self) -> AffineMat:
    'Inverse of this transform. Raises ValueError if the matrix is singular.'
    d = self.det
    if d == 0:
      raise ValueError(f'AffineMat matrix is singular (det=0): {self!r}')
    inv_d = 1.0 / d

    xx, xy, xz = self.xx, self.xy, self.xz
    yx, yy, yz = self.yx, self.yy, self.yz
    zx, zy, zz = self.zx, self.zy, self.zz
    tx, ty, tz = self.tx, self.ty, self.tz

    # Compute the inverse of the 3x3 linear part via the adjugate (transpose of cofactors).
    ixx = (yy*zz - zy*yz) * inv_d
    ixy = (zy*xz - xy*zz) * inv_d
    ixz = (xy*yz - yy*xz) * inv_d

    iyx = (zx*yz - yx*zz) * inv_d
    iyy = (xx*zz - zx*xz) * inv_d
    iyz = (yx*xz - xx*yz) * inv_d

    izx = (yx*zy - zx*yy) * inv_d
    izy = (zx*xy - xx*zy) * inv_d
    izz = (xx*yy - yx*xy) * inv_d

    # Inverse translation: -R^-1 * t.
    return AffineMat(
      xx=ixx, xy=ixy, xz=ixz,
      yx=iyx, yy=iyy, yz=iyz,
      zx=izx, zy=izy, zz=izz,
      tx=-(ixx*tx + iyx*ty + izx*tz),
      ty=-(ixy*tx + iyy*ty + izy*tz),
      tz=-(ixz*tx + iyz*ty + izz*tz),
    )


  @property
  def is_identity(self) -> bool:
    return (
      self.xx == 1 and self.xy == 0 and self.xz == 0 and
      self.yx == 0 and self.yy == 1 and self.yz == 0 and
      self.zx == 0 and self.zy == 0 and self.zz == 1 and
      self.tx == 0 and self.ty == 0 and self.tz == 0)


  @property
  def is_flat(self) -> bool:
    'True if this is a pure 2D transform: z cross-terms are all identity (xz=yz=zx=zy=0, zz=1, tz=0).'
    return (
      self.xz == 0 and self.yz == 0 and
      self.zx == 0 and self.zy == 0 and self.zz == 1 and
      self.tz == 0)


  def to_svg_matrix(self) -> str:
    '''
    Return the SVG matrix(a,b,c,d,e,f) transform string for this affine transform.
    Raises ValueError if the transform is not flat (i.e. has non-trivial z components).
    SVG convention: matrix(a,b,c,d,e,f) where a=xx, b=xy, c=yx, d=yy, e=tx, f=ty.
    '''
    if not self.is_flat:
      raise ValueError(f'AffineMat transform is not flat (has 3D components); cannot convert to SVG matrix: {self!r}')
    return f'matrix({self.xx},{self.xy},{self.yx},{self.yy},{self.tx},{self.ty})'


  @staticmethod
  def identity() -> AffineMat:
    'The identity transform.'
    return AffineMat()


  @staticmethod
  def translate(tx:float=0, ty:float=0, tz:float=0) -> 'AffineMat':
    'A pure translation.'
    return AffineMat(tx=tx, ty=ty, tz=tz)


  @staticmethod
  def translate_v(v:V) -> AffineMat:
    'A pure translation from a V.'
    return AffineMat(tx=v.x, ty=v.y, tz=v.z)


  @staticmethod
  def scale(sx:float, sy:float|None=None, sz:float|None=None) -> AffineMat:
    'A uniform or per-axis scale. If sy or sz are omitted, sx is used for all omitted axes.'
    if sy is None: sy = sx
    if sz is None: sz = sx
    return AffineMat(xx=sx, yy=sy, zz=sz)


  @staticmethod
  def rotate_z(rad:float) -> AffineMat:
    'A counter-clockwise rotation about the +Z axis by rad radians (the standard 2D rotation).'
    if rad == h_pi:
      return AffineMat(xx=0, xy=1, yx=-1, yy=0)
    if rad == -h_pi:
      return AffineMat(xx=0, xy=-1, yx=1, yy=0)
    if rad == pi or rad == -pi:
      return AffineMat(xx=-1, xy=0, yx=0, yy=-1)
    c = cos(rad)
    s = sin(rad)
    return AffineMat(xx=c, xy=s, yx=-s, yy=c)


  @staticmethod
  def rotate_x(rad:float) -> AffineMat:
    'A counter-clockwise rotation about the +X axis by rad radians.'
    if rad == h_pi:
      return AffineMat(yy=0, yz=1, zy=-1, zz=0)
    if rad == -h_pi:
      return AffineMat(yy=0, yz=-1, zy=1, zz=0)
    if rad == pi or rad == -pi:
      return AffineMat(yy=-1, yz=0, zy=0, zz=-1)
    c = cos(rad)
    s = sin(rad)
    return AffineMat(yy=c, yz=s, zy=-s, zz=c)


  @staticmethod
  def rotate_y(rad:float) -> AffineMat:
    'A counter-clockwise rotation about the +Y axis by rad radians.'
    if rad == h_pi:
      return AffineMat(xx=0, xz=-1, zx=1, zz=0)
    if rad == -h_pi:
      return AffineMat(xx=0, xz=1, zx=-1, zz=0)
    if rad == pi or rad == -pi:
      return AffineMat(xx=-1, xz=0, zx=0, zz=-1)
    c = cos(rad)
    s = sin(rad)
    return AffineMat(xx=c, xz=-s, zx=s, zz=c)


  @staticmethod
  def rotate_axis(rad:float, axis:V) -> AffineMat:
    'A counter-clockwise rotation about the given axis vector by rad radians.'
    a = axis.norm
    x, y, z = a.x, a.y, a.z
    if x == 0 and y == 0: return AffineMat.rotate_z(rad)
    if y == 0 and z == 0: return AffineMat.rotate_x(rad)
    if x == 0 and z == 0: return AffineMat.rotate_y(rad)
    c = cos(rad)
    s = sin(rad)
    t = 1 - c
    return AffineMat(
      xx=c + x*x*t,     xy=y*x*t + z*s,   xz=z*x*t - y*s,
      yx=x*y*t - z*s,   yy=c + y*y*t,     yz=z*y*t + x*s,
      zx=x*z*t + y*s,   zy=y*z*t - x*s,   zz=c + z*z*t)


  @staticmethod
  def rotate_axis_about(rad:float, axis:'V', center:'V') -> 'AffineMat':
    'A counter-clockwise rotation about the given axis through the given center point.'
    r = AffineMat.rotate_axis(rad, axis)
    return AffineMat.translate_v(center) @ r @ AffineMat.translate_v(-center)


  @staticmethod
  def rotate_z_about(rad:float, cx:float, cy:float) -> AffineMat:
    'A counter-clockwise rotation about the Z axis through the 2D point (cx, cy).'
    r = AffineMat.rotate_z(rad)
    return AffineMat.translate(cx, cy) @ r @ AffineMat.translate(-cx, -cy)


  @staticmethod
  def rotate_z_about_v(rad:float, center:V) -> AffineMat:
    'A counter-clockwise rotation about the Z axis through the given V point (z ignored).'
    return AffineMat.rotate_z_about(rad, center.x, center.y)
