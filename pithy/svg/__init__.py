# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
SVG types based on Markup (`Mu` class family).
SVG elements reference: https://developer.mozilla.org/en-US/docs/Web/SVG/Element.
'''

from os import PathLike
from typing import Any, BinaryIO, cast, ClassVar, Iterable, Self, TextIO

from ..default import Default
from ..markup import _Mu, Mu, MuAttrs, NoMatchError, prefer_int
from ..range import NumRange
from ..vec import V


Dim = int|float|str
Vec = tuple[float,float]|V
VecOrNum = Vec|float
BoundsF2 = tuple[tuple[float,float],tuple[float,float]]
PathCommand = str|tuple[int|float|str,...]

_LxmlFilePath = str | bytes | PathLike[str] | PathLike[bytes]
_LxmlFileReadSource = _LxmlFilePath | BinaryIO | TextIO

class SvgNode(Mu):
  '''
  Abstract class for SVG elements.
  '''

  tag_types:ClassVar[dict[str,type['Mu']]] = {} # Dispatch table mapping tag names to Mu subtypes.

  replaced_attrs = {}


  def __init__(self, *args, title:str|None=None, **kwargs) -> None:
    '''
    SvgNode constructor.
    The `title` parameter is treated as a special attribute that is converted into a `title` child element.
    This is convenient because for many elements the title is the only child element.
    '''
    super().__init__(*args, **kwargs)
    if title is not None:
      self.title = title


  @property
  def title(self) -> str|None:
    'Get the title text from the title child element. If it does not exist return None.'
    try: return self.pick('title').text
    except NoMatchError: return None

  @title.setter
  def title(self, title:str|None):
    'Add a title child element to the head of the children list.'
    try:
      title_el = self.pick('title')
    except NoMatchError:
      if title is not None:
        self._.insert(0, Title(_=title))
    else:
      if title is None:
        self._.remove(title_el)
      else:
        title_el._ = [title]

  @title.deleter
  def title(self) -> None:
    'Remove the title child element.'
    try: title_el = self.pick('title')
    except NoMatchError as e: raise AttributeError('title') from e
    else: self._.remove(title_el)


  @classmethod
  def parse_file(cls, file:_LxmlFileReadSource,  **kwargs:Any) -> 'SvgNode':
    from lxml import etree
    tree = etree.parse(file)
    root = tree.getroot()
    if root is None: # Empty or whitespace strings produce None.
      return Svg() # type: ignore[unreachable]
    node = SvgNode.from_etree(root) # type: ignore[arg-type]
    assert isinstance(node, SvgNode), node
    return node



SvgNode.generic_tag_type = SvgNode # Note: this creates a circular reference.


class _MixinPos:
  'Mixin for SVG elements that have x and y attributes.'

  def pos(self, pos:Vec) -> Self:
    'Set the x and y attributes from the provided `pos` vector.'
    unpack_Vec_and_set(cast(SvgNode, self).attrs, 'x', 'y', pos)
    return self


class _MixinSize:
  'Mixin for SVG elements that have width and height attributes.'

  def size(self, size:VecOrNum) -> Self:
    'Set the width and height attributes from the provided `size` vector or number.'
    unpack_VecOrNum_and_set(cast(SvgNode, self).attrs, 'width', 'height', size)
    return self


class _MixinViewBox:
  'Mixin for SVG elements that have a viewBox attribute.'

  def viewbox(self, vx:float=0, vy:float=0, vw:float|None=None, vh:float|None=None) -> Self:
    'Set the viewBox attribute.'
    cast(SvgNode, self).attrs['viewBox'] = fmt_viewBox(vx, vy, vw, vh)
    return self


def _tag(Subclass:type[_Mu]) -> type[_Mu]:
  'Decorator for associating a concrete subclass with the lowercase tag matching its name.'
  assert issubclass(Subclass, Mu)
  Subclass.tag = Subclass.__name__.lower()
  SvgNode.tag_types[Subclass.tag] = Subclass
  return Subclass


@_tag
class Script(SvgNode):
  'SVG Script element. Note that Html also has a subclass of the same name.'

@_tag
class Style(SvgNode):
  'SVG Style element. Note that Html also has a subclass of the same name.'


# SVG leaf elements.

@_tag
class Circle(SvgNode):
  'SVG Circle element.'

  def c(self, *, c:Vec) -> Self:
    'Set the cx and cy attributes from the provided `c` vector.'
    unpack_Vec_and_set(self.attrs, 'cx', 'cy', c)
    return self


@_tag
class Image(SvgNode, _MixinPos, _MixinSize):
  'SVG Image element.'


@_tag
class Line(SvgNode):
  'SVG Line element.'

  def p1(self, p1:Vec) -> Self:
    unpack_Vec_and_set(self.attrs, 'x1', 'y1', p1)
    return self

  def p2(self, p2:Vec) -> Self:
    unpack_Vec_and_set(self.attrs, 'x2', 'y2', p2)
    return self


@_tag
class Path(SvgNode):
  'SVG Path element.'

  def __init__(self, *args, d:Iterable[PathCommand]|Default=Default._, **kw_attrs) -> None:

    if isinstance(d, Default):
      super().__init__(*args, **kw_attrs)
      return

    if not isinstance(d, str):
      cmd_strs = []

      for c in d:

        if isinstance(c, str):
          if c: cmd_strs.append(c) # Ignore empty strings.
          continue

        try: code = c[0]
        except IndexError: continue # Ignore empty tuples.

        if not isinstance(code, str): raise Exception(f'path command code must be a string; received command: {c!r}')

        try: exp_len = _path_command_lens[code]
        except KeyError as e: raise Exception(f'bad path command code: {code!r}; received command: {c!r}') from e

        if len(c) != exp_len + 1:
          raise Exception(f'path command code {code!r} requires {exp_len} arguments; received command: {c!r}')

        cmd_strs.append(code + ','.join(str(prefer_int(n)) for n in c[1:]))

      d = ' '.join(cmd_strs)

    super().__init__(*args, d=d, **kw_attrs)


@_tag
class SvgPoly(SvgNode):
  'Abstract class for SVG polygon and polyline elements.'

  def __init__(self, *args, points:str|Iterable[str|Vec]|Default=Default._, **kw_attrs) -> None:

    if isinstance(points, Default):
      super().__init__(*args, **kw_attrs)
      return

    if not isinstance(points, str):
      point_strs = []
      for p in points:
        if isinstance(p, str):
          point_strs.append(p)
        elif len(p) < 2:
          raise Exception(f'invalid point for {self.tag}: {p!r}')
        else:
          point_strs.append(f'{prefer_int(p[0])},{prefer_int(p[1])}')
      points = ' '.join(point_strs)

    super().__init__(*args, points=points, **kw_attrs)


@_tag
class Polygon(SvgPoly):
  'SVG Polygon element.'


@_tag
class Polyline(SvgPoly):
  'SVG Polyline element.'


@_tag
class Rect(SvgNode, _MixinPos, _MixinSize):
  'SVG Rect element.'

  def r(self, r:VecOrNum) -> Self:
    'Set the rx and ry (corner rounding) attributes from the provided `r` vector or number.'
    unpack_VecOrNum_and_set(self.attrs, 'rx', 'ry', r)
    return self


@_tag
class Text(SvgNode, _MixinPos):
  'SVG Text element.'

  def alignment_baseline(self, alignment_baseline:str|None) -> Self:
    if alignment_baseline:
      if alignment_baseline not in alignment_baselines: raise ValueError(alignment_baseline)
      self.attrs['alignment-baseline'] = alignment_baseline
    return self


@_tag
class Title(SvgNode):
  'SVG Title element.'


@_tag
class TSpan(SvgNode):
  'SVG TSpan element.'


@_tag
class Use(SvgNode, _MixinPos, _MixinSize):
  'SVG Use element.'



class SvgBranch(SvgNode):
  'An abstract class for SVG nodes that can contain other nodes.'


  def circle(self, c:Vec|None=None, *, cx:float|None=None, cy:float|None=None, r:float|None=None, **kw_attrs:Any) -> Circle:
    'Create a child `circle` element.'
    if c is not None:
      assert cx is None and cy is None
      cx, cy = unpack_Vec(c)
    return self.append(Circle(cx=cx, cy=cy, r=r, **kw_attrs))


  def clip_path(self, **kw_attrs:Any) -> 'ClipPath':
    'Create a child `clipPath` element.'
    return self.append(ClipPath(**kw_attrs))


  def defs(self, **kw_attrs:Any) -> 'Defs':
    'Create a child `defs` element.'
    return self.append(Defs(**kw_attrs))


  def g(self, transform:Iterable[str]='', **kw_attrs:Any) -> 'G':
    'Create child `g` element.'
    return self.append(G(transform=transform, **kw_attrs))


  def image(self, pos:Vec|None=None, size:VecOrNum|None=None, *,
   x:float|None=None, y:float|None=None, width:float|None=None, height:float|None=None, **kw_attrs:Any) -> Image:
    'Create a child `image` element.'
    if pos is not None:
      assert x is None and y is None
      x, y = unpack_Vec(pos)
    if size is not None:
      assert width is None and height is None
      width, height = unpack_VecOrNum(size)
    if x is not None: kw_attrs['x'] = x
    if y is not None: kw_attrs['y'] = y
    if width is not None: kw_attrs['width'] = width
    if height is not None: kw_attrs['height'] = height
    return self.append(Image(**kw_attrs))


  def line(self, p1:Vec|None=None, p2:Vec|None=None, *,
   x1:float|None=None, y1:float|None=None, x2:float|None=None, y2:float|None=None, **kw_attrs:Any) -> Line:
    'Create a child `line` element.'
    if p1 is not None:
      assert x1 is None and y1 is None
      x1, y1 = unpack_Vec(p1)
    if p2 is not None:
      assert x2 is None and y2 is None
      x2, y2 = unpack_VecOrNum(p2)
    return self.append(Line(x1=x1, y1=y1, x2=x2, y2=y2, **kw_attrs))


  def marker(self, *, id:str='', pos:Vec|None=None, size:VecOrNum|None=None,
   refX:float|None=None, refY:float|None=None, markerWidth:float|None=None, markerHeight:float|None=None,
   vx:float=0, vy:float=0, vw:float|None=None, vh:float|None=None,
   markerUnits='strokeWidth', orient:str='auto', **kw_attrs:Any) -> 'Marker':
    'Create a child `marker` element.'
    if pos is not None:
      assert refX is None and refY is None
      refX, refY = unpack_Vec(pos)
    if size is not None:
      assert markerWidth is None and markerHeight is None
      markerWidth, markerHeight = unpack_VecOrNum(size)
    if id: kw_attrs['id'] = id
    if refX is not None: kw_attrs['refX'] = refX
    if refY is not None: kw_attrs['refY'] = refY
    if markerWidth is not None: kw_attrs['markerWidth'] = markerWidth
    if markerHeight is not None: kw_attrs['markerHeight'] = markerHeight
    if markerUnits: kw_attrs['markerUnits'] = markerUnits
    if orient: kw_attrs['orient'] = orient
    return self.append(
      Marker(**kw_attrs).viewbox(vx, vy, vw, vh))


  def path(self, d:Iterable[PathCommand], **kw_attrs:Any) -> Path:
    'Create a child `path` element.'
    return self.append(Path(d=d, **kw_attrs))


  def polygon(self, points:Iterable[Vec], **kw_attrs:Any) -> Polygon:
    'Create a child `polygon` element.'
    return self.append(Polygon(points=points, **kw_attrs))


  def polyline(self, points:Iterable[Vec], **kw_attrs:Any) -> Polyline:
    'Create a child `polyline` element.'
    return self.append(Polyline(points=points, **kw_attrs))


  def rect(self, pos:Vec|None=None, size:VecOrNum|None=None, *, r:VecOrNum|None=None,
   x:float|None=None, y:float|None=None, width:float|None=None, height:float|None=None,
   rx:float|None=None, ry:float|None=None, **kw_attrs:Any) -> Rect:
    'Create a child `rect` element.'
    if pos is not None:
      assert x is None and y is None
      x, y = unpack_Vec(pos)
    if size is not None:
      assert width is None and height is None
      width, height = unpack_VecOrNum(size)
    if r is not None:
      assert rx is None and ry is None
      rx, ry = unpack_VecOrNum(r)
    if rx is not None: kw_attrs['rx'] = rx
    if ry is not None: kw_attrs['ry'] = ry
    return self.append(Rect(x=x, y=y, width=width, height=height, **kw_attrs))


  def script(self, *text:str, **kw_attrs,) -> Script:
    'Create a child `script` element.'
    return self.append(Script(_=text, **kw_attrs))


  def style(self, *text:str, **kw_attrs,) -> Style:
    'Create a child `style` element.'
    return self.append(Style(_=text, **kw_attrs))


  def symbol(self, *, _=(), id:str, vx:float=0, vy:float=0, vw:float, vh:float, **kw_attrs:Any) -> 'Symbol':
    'Create a child `symbol` element.'
    return self.append(Symbol(_=_, id=id, **kw_attrs).viewbox(vx=vx, vy=vy, vw=vw, vh=vh))


  def use(self, href:str, pos:Vec|None=None, size:VecOrNum|None=None, *,
   x:float|None=None, y:float|None=None, width:float|None=None, height:float|None=None, **kw_attrs:Any) -> Use:
    'Create a child `use` element to use a previously defined symbol.'
    if pos is not None:
      assert x is None and y is None
      x, y = unpack_Vec(pos)
    if size is not None:
      assert width is None and height is None
      width, height = unpack_VecOrNum(size)
    if x is not None: kw_attrs['x'] = x
    if y is not None: kw_attrs['y'] = y
    if width is not None: kw_attrs['width'] = width
    if height is not None: kw_attrs['height'] = height
    return self.append(Use(href=href, **kw_attrs))


  def grid(self, pos:Vec=(0,0), size:VecOrNum=(256,256), *,
   step:VecOrNum=16, offset:Vec=(0, 0), r:VecOrNum|None=None, **kw_attrs:Any) -> 'G':
    x, y = unpack_Vec(pos)
    width, height = unpack_VecOrNum(size)
    sx, sy = unpack_VecOrNum(step)
    off_x, off_y = unpack_Vec(offset)
    if off_x <= 0: off_x = sx # Do not emit line at 0, because that is handled by border.
    if off_y <= 0: off_y = sy # Do not emit line at 0, because that is handled by border.
    x_start = x + off_x
    y_start = y + off_y
    x_end = x + width
    y_end = y + height
    kw_attrs.setdefault('cl', 'grid')
    # TODO: if we are really going to support rounded corners then the border rect should clip the interior lines.
    g = self.append(G(**kw_attrs))
    for tick in NumRange(x_start, x_end, sx): g.line((tick, y), (tick, y_end)) # Vertical lines.
    for tick in NumRange(y_start, y_end, sy): g.line((x, tick), (x_end, tick)) # Horizontal lines.
    g.rect(cl='grid-border', x=x, y=y, width=width, height=height, r=r, fill='none')
    return g


@_tag
class Svg(SvgBranch, _MixinPos, _MixinSize, _MixinViewBox):
  '''
  SVG element.
  HTML contexts for use: Phrasing.
  '''

  def __init__(self, *args, **kw_attrs) -> None:
    '''
    Add the xmlns as the first attribute.
    If the user wants to override this, they can do so by passing `xmlns` as a keyword argument.
    '''
    super().__init__(*args, xmlns='http://www.w3.org/2000/svg', **kw_attrs)


# SVG branch elements.

@_tag
class ClipPath(SvgBranch):
  'SVG ClipPath element.'


@_tag
class Defs(SvgBranch):
  'SVG Defs element.'


@_tag
class G(SvgBranch):
  'SVG Group element.'

  def __call__(self, transform:Iterable[str]|None=None) -> Self:

    if transform is not None:
      t:str = ''
      if isinstance(transform, str):
        t = transform
      else:
        t = ' '.join(transform)
      if t:
        self.attrs['transform'] = t
    return self


@_tag
class Marker(SvgBranch, _MixinPos, _MixinSize, _MixinViewBox):
  'SVG Marker element.'


@_tag
class Symbol(SvgBranch, _MixinViewBox):
  'SVG Symbol element.'


# Transforms.
# Note: SVG syntax allows spaces or commas between numbers in transform strings. We use commas exclusively in our output.

def scale(x:float, y:float|None=None) -> str:
  if y is None:
    return f'scale({x})'
  return f'scale({x},{y})'


def rotate(degrees:float, x:float=0, y:float=0) -> str:
  if x == 0 and y == 0:
    return f'rotate({prefer_int(degrees)})'
  return f'rotate({prefer_int(degrees)},{prefer_int(x)},{prefer_int(y)})'


def translate(x:float=0, y:float=0) -> str:
  return f'translate({prefer_int(x)},{prefer_int(y)})'


def matrix(a:float, b:float, c:float, d:float, e:float, f:float) -> str:
  return f'matrix({a},{b},{c},{d},{e},{f})'


def apply_transforms(svg:SvgNode, transforms:Iterable[str]) -> SvgNode:
  '''
  Apply transforms to an SVG node.
  This function modifies the "transform" attribute of the node, applying the given transforms ahead of any existing transforms.
  '''
  transforms = [transforms] if isinstance(transforms, str) else list(transforms)
  if transforms:
    if existing := svg.attrs.get('transform'):
      transforms += existing
  svg.attrs['transform'] = ' '.join(transforms)
  return svg


# Miscellaneous.


_path_command_lens = {
  'A' : 7,
  'M' : 2,
  'm' : 2,
  'L' : 2,
  'l' : 2,
  'Z' : 0,
  'z' : 0
}


valid_units = frozenset({'em', 'ex', 'px', 'pt', 'pc', 'cm', 'mm', '%', ''})

def validate_unit(unit: str) -> str:
  'Ensure that `unit` is a valid unit string and return it.'
  if unit not in valid_units:
    raise Exception(f'Invalid SVG unit: {unit!r}; should be one of {sorted(valid_units)}')
  return unit


def fmt_viewBox(vx:float, vy:float, vw:float|None, vh:float|None) -> str|None:
  if vw is None and vh is None:
    return None
  assert vw is not None and vw > 0
  assert vh is not None and vh > 0
  return f'{prefer_int(vx)} {prefer_int(vy)} {prefer_int(vw)} {prefer_int(vh)}'


def unpack_Vec(v:Vec) -> tuple[float, float]:
  if isinstance(v, tuple):
    x, y = v
    return float(x), float(y)
  else:
    return v.x, v.y


def unpack_Vec_and_set(attrs:MuAttrs, kx:str, ky:str, v:Vec) -> None:
  x, y = unpack_Vec(v)
  attrs[kx] = x
  attrs[ky] = y


def unpack_VecOrNum(vn:VecOrNum) -> tuple[float, float]:
  if isinstance(vn, tuple):
    x, y = vn
    return float(x), float(y)
  elif isinstance(vn, V):
    return vn.x, vn.y
  else:
    s = float(vn)
    return (s, s)


def unpack_VecOrNum_and_set(attrs:MuAttrs, kx:str, ky:str, vn:VecOrNum) -> None:
  x, y = unpack_VecOrNum(vn)
  attrs[kx] = x
  attrs[ky] = y


def expand_opt_bounds(l:BoundsF2|None, r:BoundsF2|None) -> BoundsF2|None:
  if l is None: return r
  if r is None: return l
  (llx, lly), (lhx, lhy) = l
  (rlx, rly), (rhx, rhy) = r
  return ((min(llx, rlx), min(lly, rly)), (max(lhx, rhx), max(lhy, rhy)))


alignment_baselines = {
  'after-edge',
  'alphabetic',
  'auto',
  'baseline',
  'before-edge',
  'central',
  'hanging',
  'ideographic',
  'inherit',
  'mathematical',
  'middle',
  'text-after-edge',
  'text-before-edge',
}
