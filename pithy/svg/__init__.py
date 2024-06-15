# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
SVG types based on Markup (`Mu` class family).
SVG elements reference: https://developer.mozilla.org/en-US/docs/Web/SVG/Element.
'''

from typing import Any, ClassVar, Iterable, Optional

from ..markup import (_Mu, add_nonopt_attrs, Mu, mu_child_classes_lax, MuAttrs, MuChildLax, MuChildOrChildrenLax, NoMatchError,
  prefer_int)
from ..range import NumRange


Dim = int|float|str
Vec = tuple[float,float]
VecOrNum = Vec|float
F2 = tuple[float,float]
F2OrF = F2|float
BoundsF2 = tuple[F2,F2]
PathCommand = tuple|str


class SvgNode(Mu):
  '''
  Abstract class for SVG elements.
  '''

  tag_types:ClassVar[dict[str,type['Mu']]] = {} # Dispatch table mapping tag names to Mu subtypes.

  replaced_attrs = {
    'w': 'width',
    'h': 'height',
  }


  def __init__(self:_Mu,
   *_mu_positional_children:'MuChildLax', # Children can be passed as positional arguments.
   _:'MuChildOrChildrenLax'=(), # Children can also be passed to the named underscore parameter.
   tag:str='',
   cl:Iterable[str]|None=None,
   _orig:_Mu|None=None,
   _parent:Optional['Mu']=None,
   title:str|None=None, # See docstring.
   attrs:MuAttrs|None=None,
   **kw_attrs:Any) -> None:
    '''
    SvgNode constructor.
    The `title` parameter is a special attribute that is not included in the `attrs` parameter.
    It is converted into a `title` child element.
    This is convenient because for many elements the title is the only child element.
    '''

    if title is not None:
      assert _orig is None and _parent is None # Should not be setting `title` for a subtree node.
      if isinstance(_, mu_child_classes_lax): # Single child argument; wrap it in a list.
        _ = [_]
      elif not isinstance(_, list):
          _ = list(_)
      _.append(Title(_=title))
    super().__init__(tag=tag, attrs=attrs, _=_, cl=cl, _orig=_orig, _parent=_parent, *_mu_positional_children, **kw_attrs)


  @property
  def title(self) -> str|None:
    '''
    Get the title child element.
    TODO: implement setter.
    '''
    try: return self.pick('title').text
    except NoMatchError: return None


SvgNode.generic_tag_type = SvgNode # Note: this creates a circular reference.


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

  def __init__(self, *, pos:Vec|None=None, r:float|None=None, x:float|None=None, y:float|None=None,
   attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    add_nonopt_attrs(kwargs, cx=x, cy=y, r=r)
    super().__init__(attrs=attrs, **kwargs)


@_tag
class Image(SvgNode):

  def __init__(self, pos:Vec|None=None, *, size:VecOrNum|None=None, x:float|None=None, y:float|None=None, w:float|None=None, h:float|None=None,
   attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      w, h = unpack_VecOrNum(size)
    add_nonopt_attrs(kwargs, x=x, y=y, width=w, height=h)
    super().__init__(attrs=attrs, **kwargs)


@_tag
class Line(SvgNode):
  'SVG Line element.'

  def __init__(self, a:Vec|None=None, b:Vec|None=None, *, x1:float|None=None, y1:float|None=None, x2:float|None=None, y2:float|None=None,
   attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    if a is not None:
      assert x1 is None
      assert y1 is None
      x1, y1 = a
    if b is not None:
      assert x2 is None
      assert y2 is None
      x2, y2 = b
    add_nonopt_attrs(kwargs, x1=x1, y1=y1, x2=x2, y2=y2)
    super().__init__(attrs=attrs, **kwargs)


@_tag
class Path(SvgNode):
  'SVG Path element.'

  def __init__(self, d:Iterable[PathCommand],
   attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    assert (attrs is None or 'd' not in attrs)
    if isinstance(d, str):
      kwargs['d'] = d
    else:
      cmd_strs:list[str] = []
      for c in d:
        if isinstance(c, str):
          cmd_strs.append(c)
          continue
        try: code = c[0]
        except IndexError: continue
        try: exp_len = _path_command_lens[code]
        except KeyError as e: raise Exception(f'bad path command code: {c!r}') from e
        if len(c) != exp_len + 1: raise Exception(f'path command requires {exp_len} arguments: {c}')
        cmd_strs.append(code + ','.join(str(prefer_int(n)) for n in c[1:]))
      kwargs['d'] = ' '.join(cmd_strs)
    super().__init__(attrs=attrs, **kwargs)


@_tag
class SvgPoly(SvgNode):
  'Abstract class for SVG polygon and polyline elements.'

  def __init__(self, points:Iterable[Vec],
   attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    assert (attrs is None or 'points' not in attrs)
    point_strs:list[str] = []
    for p in points:
      if len(p) < 2: raise Exception(f'bad point for {self.tag}: {p}')
      point_strs.append(f'{prefer_int(p[0])},{prefer_int(p[1])}')
    kwargs['points'] = ' '.join(point_strs)
    super().__init__(attrs=attrs, **kwargs)


@_tag
class Polygon(SvgPoly):
  'SVG Polygon element.'


@_tag
class Polyline(SvgPoly):
  'SVG Polyline element.'


@_tag
class Rect(SvgNode):
  'Rect element.'

  def __init__(self, pos:Vec|None=None, size:VecOrNum|None=None, *, x:float|None=None, y:float|None=None, w:float|None=None, h:float|None=None, r:VecOrNum|None=None,
   attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      w, h = unpack_VecOrNum(size)
    rx:float|None
    ry:float|None
    if isinstance(r, tuple):
      rx, ry = r
    else:
      rx = ry = r
    add_nonopt_attrs(kwargs, x=x, y=y, width=w, height=h, rx=rx, ry=ry)
    super().__init__(attrs=attrs, **kwargs)


@_tag
class Text(SvgNode):
  tag = 'text'

  def __init__(self, _='', pos:Vec|None=None, x:float|None=None, y:float|None=None, alignment_baseline:str|None=None,
   attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if alignment_baseline is not None and alignment_baseline not in alignment_baselines: raise ValueError(alignment_baseline)
    add_nonopt_attrs(kwargs, x=x, y=y, alignment_baseline=alignment_baseline)
    super().__init__(_=_, attrs=attrs, **kwargs)


@_tag
class Title(SvgNode):
  'SVG Title element.'


@_tag
class TSpan(SvgNode):
  tag = 'tspan'


@_tag
class Use(SvgNode):
  tag = 'use'

  def __init__(self, id:str, pos:Vec|None=None, size:VecOrNum|None=None, *, x:float|None=None, y:float|None=None, w:float|None=None, h:float|None=None,
   attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    assert id
    if id[0] != '#': id = '#' + id
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      w, h = unpack_VecOrNum(size)
    add_nonopt_attrs(kwargs, href=id, x=x, y=y, width=w, height=h)
    super().__init__(attrs=attrs, **kwargs)



class SvgBranch(SvgNode):
  'An abstract class for SVG nodes that can contain other nodes.'


  def circle(self, pos:Vec|None=None, r:float|None=None, x:float|None=None, y:float|None=None, **kwargs:Any) -> Circle:
    'Create a child `circle` element.'
    return self.append(Circle(pos=pos, r=r, x=x, y=y, **kwargs))


  def clip_path(self, **kwargs:Any) -> 'ClipPath':
    'Create a child `clipPath` element.'
    return self.append(ClipPath(**kwargs))


  def defs(self, **kwargs:Any) -> 'Defs':
    'Create a child `defs` element.'
    return self.append(Defs(**kwargs))


  def g(self, transform:Iterable[str]='', **kwargs:Any) -> 'G':
    'Create child `g` element.'
    return self.append(G(transform=transform, **kwargs))


  def image(self, pos:Vec|None=None, size:VecOrNum|None=None, *, x:float|None=None, y:float|None=None, w:float|None=None, h:float|None=None, **kwargs:Any) -> Image:
    'Create a child `image` element.'
    return self.append(Image(pos=pos, size=size, x=x, y=y, w=w, h=h, **kwargs))


  def line(self, a:Vec|None=None, b:Vec|None=None, *, x1:float|None=None, y1:float|None=None, x2:float|None=None, y2:float|None=None, **kwargs:Any) -> Line:
    'Create a child `line` element.'
    return self.append(Line(a=a, b=b, x1=x1, y1=y1, x2=x2, y2=y2, **kwargs))


  def marker(self, _=(), id:str='', pos:Vec|None=None, size:VecOrNum|None=None, x:float|None=None, y:float|None=None, w:float|None=None, h:float|None=None,
   vx:float=0, vy:float=0, vw:float|None=None, vh:float|None=None, markerUnits='strokeWidth', orient:str='auto', **kwargs:Any) -> 'Marker':
    'Create a child `marker` element.'
    return self.append(Marker(_=_, id=id, pos=pos, size=size, x=x, y=y, w=w, h=h, vx=vx, vy=vy, vw=vw, vh=vh,
      markerUnits=markerUnits, orient=orient, **kwargs))


  def path(self, d:Iterable[PathCommand], **kwargs:Any) -> Path:
    'Create a child `path` element.'
    return self.append(Path(d=d, **kwargs))


  def polygon(self, points:Iterable[Vec], **kwargs:Any) -> Polygon:
    'Create a child `polygon` element.'
    return self.append(Polygon(points=points, **kwargs))


  def polyline(self, points:Iterable[Vec], **kwargs:Any) -> Polyline:
    'Create a child `polyline` element.'
    return self.append(Polyline(points=points, **kwargs))


  def rect(self, pos:Vec|None=None, size:VecOrNum|None=None, *, x:float|None=None, y:float|None=None, w:float|None=None, h:float|None=None, r:VecOrNum|None=None, **kwargs:Any) -> Rect:
    'Create a child `rect` element.'
    return self.append(Rect(pos=pos, size=size, x=x, y=y, w=w, h=h, r=r, **kwargs))


  def script(self, *text:str, **kwargs,) -> Script:
    'Create a child `script` element.'
    return self.append(Script(_=text, **kwargs))


  def style(self, *text:str, **kwargs,) -> Style:
    'Create a child `style` element.'
    return self.append(Style(_=text, **kwargs))


  def symbol(self, id:str, _=(), vx:float|None=None, vy:float|None=None, vw:float=-1, vh:float=-1, **kwargs:Any) -> 'Symbol':
    'Create a child `symbol` element.'
    return self.append(Symbol(_=_, id=id, vx=vx, vy=vy, vw=vw, vh=vh, **kwargs))


  def use(self, id:str, pos:Vec|None=None, size:VecOrNum|None=None, *, x:float|None=None, y:float|None=None, w:float|None=None, h:float|None=None, **kwargs:Any) -> Use:
    'Create a child `use` element to use a previously defined symbol.'
    return self.append(Use(id=id, pos=pos, size=size, x=x, y=y, w=w, h=h, **kwargs))


  def grid(self, pos:Vec=(0,0), size:VecOrNum=(256,256), *,
   step:VecOrNum=16, offset:Vec=(0, 0), corner_radius:VecOrNum|None=None, **kwargs:Any) -> 'G':
    x, y = f2_for_vec(pos)
    w, h = unpack_VecOrNum(size)
    sx, sy = unpack_VecOrNum(step)
    off_x, off_y = f2_for_vec(offset)
    if off_x <= 0: off_x = sx # Do not emit line at 0, because that is handled by border.
    if off_y <= 0: off_y = sy # Do not emit line at 0, because that is handled by border.
    x_start = x + off_x
    y_start = y + off_y
    x_end = x + w
    y_end = y + h
    _= kwargs.setdefault('cl', 'grid')
    # TODO: if we are really going to support rounded corners then the border rect should clip the interior lines.
    g = self.append(G(**kwargs))
    for tick in NumRange(x_start, x_end, sx): g.line((tick, y), (tick, y_end)) # Vertical lines.
    for tick in NumRange(y_start, y_end, sy): g.line((x, tick), (x_end, tick)) # Horizontal lines.
    g.rect(cl='grid-border', x=x, y=y, w=w, h=h, r=corner_radius, fill='none')
    return g



@_tag
class Svg(SvgBranch):
  '''
  HTML contexts for use: Phrasing.
  '''

  def __init__(self, pos:Vec|None=None, size:VecOrNum|None=None, *, x:Dim|None=None, y:Dim|None=None, w:Dim|None=None, h:Dim|None=None,
   vx:float=0, vy:float=0, vw:float|None=None, vh:float|None=None, attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      if isinstance(size, tuple):
        w, h = size
      else:
        w = h = size
    self.x = x
    self.y = y
    self.w = w
    self.h = h
    self.vx = vx
    self.vy = vy
    self.vw = vw
    self.vh = vh
    self.viewBox = fmt_viewBox(vx, vy, vw, vh)
    kwargs = { # Put the xmlns declaration first.
      'xmlns': 'http://www.w3.org/2000/svg',
      **kwargs
    }
    add_nonopt_attrs(kwargs, x=x, y=y, width=w, height=h, viewBox=self.viewBox)
    super().__init__(attrs=attrs, **kwargs)


# SVG branch elements.

@_tag
class ClipPath(SvgBranch):
  'ClipPath element.'


@_tag
class Defs(SvgBranch):
  'Defs element.'


@_tag
class G(SvgBranch):
  'Group element.'

  def __init__(self, transform:Iterable[str]='',
   _:Iterable[SvgNode]=(), attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    t:str = ''
    if isinstance(transform, str):
      t = transform
    else:
      t = ' '.join(transform)
    if t:
      kwargs['transform'] = t
    super().__init__(_=_, attrs=attrs, **kwargs)


@_tag
class Marker(SvgBranch):
  'Marker element.'

  def __init__(self, id:str='', pos:Vec|None=None, size:VecOrNum|None=None, x:float|None=None, y:float|None=None, w:float|None=None, h:float|None=None,
   vx:float=0, vy:float=0, vw:float|None=None, vh:float|None=None, markerUnits='strokeWidth', orient:str='auto',
   _:Iterable[SvgNode]=(), attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    if not id: raise ValueError('Marker requires an `id` string')
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      w, h = unpack_VecOrNum(size)
    add_nonopt_attrs(kwargs, id=id, refX=x, refY=y, markerWidth=w, markerHeight=h,
      viewBox=fmt_viewBox(vx, vy, vw, vh), markerUnits=markerUnits, orient=orient)
    super().__init__(_=_, attrs=attrs, **kwargs)


@_tag
class Symbol(SvgBranch):

  def __init__(self, id:str, vx:float|None=None, vy:float|None=None, vw:float=-1, vh:float=-1,
   _:Iterable[SvgNode]=(), attrs:MuAttrs|None=None, **kwargs:Any) -> None:
    if vx is None: vx = 0
    if vy is None: vy = 0
    # TODO: figure out if no viewBox is legal and at all useful.
    assert vw >= 0
    assert vh >= 0
    add_nonopt_attrs(kwargs, id=id, viewBox=f'{prefer_int(vx)} {prefer_int(vy)} {prefer_int(vw)} {prefer_int(vh)}')
    super().__init__(_=_, attrs=attrs, **kwargs)


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

def _validate_unit(unit: str):
  'Ensure that `unit` is a valid unit string.'
  if unit not in valid_units:
    raise Exception(f'Invalid SVG unit: {unit!r}; should be one of {sorted(valid_units)}')


def fmt_viewBox(vx:float|None, vy:float|None, vw:float|None, vh:float|None) -> str|None:
  if vw is None and vh is None:
    return None
  else:
    if vx is None: vx = 0
    if vy is None: vy = 0
    assert vw is not None and vw > 0
    assert vh is not None and vh > 0
    return f'{prefer_int(vx)} {prefer_int(vy)} {prefer_int(vw)} {prefer_int(vh)}'


def f2_for_vec(v:Vec) -> F2:
  x, y = v
  return (float(x), float(y))


def unpack_VecOrNum(vn:VecOrNum) -> tuple[float, float]:
  if isinstance(vn, tuple):
    x, y = vn
    return float(x), float(y)
  else:
    s = float(vn)
    return (s, s)


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
