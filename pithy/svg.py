# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
SVG writer.
SVG elements reference: https://developer.mozilla.org/en-US/docs/Web/SVG/Element.
'''

from .num import Num, NumRange
from .xml import XmlAttrs, XmlWriter, add_opt_attrs, esc_xml_attr, esc_xml_text
from html import escape as html_escape
from types import TracebackType
from typing import Any, Callable, ContextManager, Dict, Iterator, List, Optional, Sequence, TextIO, Tuple, Type, Union, Iterable, overload


Dim = Union[int, float, str]
Vec = Tuple[Num, Num]
VecOrNum = Union[Vec, Num]
F2 = Tuple[float, float]
F2OrF = Union[F2, float]
PathCommand = Tuple

PointTransform = Callable[[Tuple], Vec]


class SvgBase(XmlWriter):

  replaced_attrs = {
    'href': 'xlink:href', # safari Version 11.1.1 requires this, even though xlink is deprecated in svg 2 standard.
    **XmlWriter.replaced_attrs,
  }


  def leaf(self, tag:str, attrs:XmlAttrs) -> None:
    '''
    Output a non-nesting SVG element.
    'title' is treated as a special attribute that is translated into a <title> child element and rendered as a tooltip.
    '''
    if attrs and 'title' in attrs: self.leaf_text(tag, attrs, text='')
    else: super().leaf(tag, attrs)


  def leaf_text(self, tag:str, attrs:XmlAttrs, text:str) -> None:
    '''
    Output a non-nesting XML element that contains text between the open and close tags.
    'title' is treated as a special attribute that is translated into a <title> child element and rendered as a tooltip.
    '''
    if attrs:
      try: title = attrs.pop('title')
      except KeyError: pass
      else:
        self.write_raw(f'<{tag}{self.fmt_attrs(attrs)}>{self._render_title(title)}{esc_xml_text(text)}</{tag}>')
        return
    super().leaf_text(tag, attrs=attrs, text=text)


  def sub(self, tag:str, attrs:XmlAttrs) -> XmlWriter:
    '''
    Create a child XmlWriter for use in a `with` context to represent a nesting XML element.
    'title' is treated as a special attribute that is translated into a <title> child element and rendered as a tooltip.
    '''
    title_el = ''
    if attrs:
      try: title = attrs.pop('title')
      except KeyError: pass
      else:
        title_el = self._render_title(title)
    s = super().sub(tag, attrs=attrs)
    if title_el: self.write_raw(title_el)
    return s


  # SVG Elements.

  def _render_title(self, title:Optional[str]) -> str:
    return '' if title is None else f'<title>{esc_xml_text(title)}</title>'


  def circle(self, pos:Vec=None, r:Num=None, *, x:Num=None, y:Num=None, **attrs:Any) -> None:
    'Output an SVG `circle` element.'
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    add_opt_attrs(attrs, cx=fmt_num(x), cy=fmt_num(y), r=fmt_num(r))
    self.leaf('circle', attrs)


  def defs(self, **attrs:Any) -> XmlWriter:
    'Output an SVG `defs` element.'
    return self.sub('defs', attrs)


  def g(self, *transforms:str, **attrs:Any) -> XmlWriter:
    'Create an SVG `g` element for use in a context manager.'
    add_opt_attrs(attrs, transform=(' '.join(transforms) if transforms else None))
    return self.sub('g', attrs)


  def image(self, pos:Vec=None, size:VecOrNum=None, *, x:Num=None, y:Num=None, w:Num=None, h:Num=None, **attrs:Any) -> None:
    'Output an SVG `defs` element.'
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      w, h = unpack_VecOrNum(size)
    add_opt_attrs(attrs, x=fmt_num(x), y=fmt_num(y), width=fmt_num(w), height=fmt_num(h))
    self.leaf('image', attrs)


  def line(self, a:Vec=None, b:Vec=None, *, x1:Num=None, y1:Num=None, x2:Num=None, y2:Num=None, **attrs:Any) -> None:
    'Output an SVG `defs` element.'
    if a is not None:
      assert x1 is None
      assert y1 is None
      x1, y1 = a
    if b is not None:
      assert x2 is None
      assert y2 is None
      x2, y2 = b
    add_opt_attrs(attrs, x1=fmt_num(x1), y1=fmt_num(y1), x2=fmt_num(x2), y2=fmt_num(y2))
    self.leaf('line', attrs)


  def marker(self, id:str, pos:Vec=None, size:VecOrNum=None, *, x:Num=None, y:Num=None, w:Num=None, h:Num=None,
   vx:Num=0, vy:Num=0, vw:Num=None, vh:Num=None,
   markerUnits='strokeWidth', orient:str='auto', **attrs:Any) -> XmlWriter:
    'Output an SVG `marker` element.'
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      w, h = unpack_VecOrNum(size)
    add_opt_attrs(attrs, id=id, refX=fmt_num(x), refY=fmt_num(y), markerWidth=fmt_num(w), markerHeight=fmt_num(h),
      viewBox=fmt_viewBox(vx, vy, vw, vh), markerUnits=markerUnits, orient=orient)
    return self.sub('marker', attrs=attrs)


  def path(self, commands:Iterable[PathCommand], **attrs:Any) -> None:
    'Output an SVG `path` element.'
    assert 'd' not in attrs
    cmd_strs:List[str] = []
    for c in commands:
      try: code = c[0]
      except IndexError: continue
      try: exp_len = _path_command_lens[code]
      except KeyError as e: raise Exception(f'bad path command code: {c!r}') from e
      if len(c) != exp_len + 1: raise Exception(f'path command requires {exp_len} arguments: {c}')
      cmd_strs.append(code + ','.join(fmt_num(n) for n in c[1:]))
    assert 'd' not in attrs
    attrs['d'] = ' '.join(cmd_strs)
    self.leaf('path', attrs)


  def polyline(self, points:Iterable[Vec], **attrs:Any) -> None:
    point_strs:List[str] = []
    assert 'points' not in attrs
    for p in points:
      if len(p) < 2: raise Exception(f'bad point for polyline: {p}')
      point_strs.append(f'{fmt_num(p[0])},{fmt_num(p[1])}')
    attrs['points'] = ' '.join(point_strs)
    self.leaf('polyline', attrs)


  def rect(self, pos:Vec=None, size:VecOrNum=None, *, x:Num=None, y:Num=None, w:Num=None, h:Num=None, r:VecOrNum=None, **attrs:Any) -> None:
    'Output an SVG `rect` element.'
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      w, h = unpack_VecOrNum(size)
    rx:Optional[Num]
    ry:Optional[Num]
    if isinstance(r, tuple):
      rx, ry = r
    else:
      rx = ry = r
    add_opt_attrs(attrs, x=fmt_num(x), y=fmt_num(y), width=fmt_num(w), height=fmt_num(h), rx=fmt_num(rx), ry=fmt_num(ry))
    self.leaf('rect', attrs)


  def style(self, text:str, **attrs,) -> None:
    'Output an SVG `style` element.'
    self.leaf_text('style', attrs, text.strip())


  def symbol(self, id:str, *, vx:Num=None, vy:Num=None, vw:Num=None, vh:Num=None, **attrs:Any) -> XmlWriter:
    'Output an SVG `symbol` element.'
    if vx is None: vx = 0
    if vy is None: vy = 0
    # TODO: figure out if no viewBox is legal and at all useful.
    assert vw >= 0 # type: ignore
    assert vh >= 0 # type: ignore
    add_opt_attrs(attrs, id=id, viewBox=f'{vx} {vy} {vw} {vh}')
    return self.sub('symbol', attrs)


  def text(self, pos:Vec=None, *, x:Num=None, y:Num=None, text:str=None, alignment_baseline:str=None, **attrs:Any) -> None:
    'Output an SVG `text` element.'
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if alignment_baseline is not None and alignment_baseline not in alignment_baselines: raise ValueError(alignment_baseline)
    add_opt_attrs(attrs, x=fmt_num(x), y=fmt_num(y), alignment_baseline=alignment_baseline)
    assert text is not None
    self.leaf_text('text', attrs, text)


  def use(self, id:str, pos:Vec=None, size:VecOrNum=None, *, x:Num=None, y:Num=None, w:Num=None, h:Num=None, **attrs:Any) -> None:
    'Use a previously defined symbol'
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
    add_opt_attrs(attrs, href=id, x=fmt_num(x), y=fmt_num(y), width=fmt_num(w), height=fmt_num(h))
    return self.leaf('use', attrs)


  # High level.

  def grid(self, pos:Vec=(0,0), size:VecOrNum=(256,256), *,
   step:VecOrNum=16, off:Vec=(0, 0), r:VecOrNum=None, **attrs:Any) -> None:
    # TODO: per-axis log-transform option.
    x, y = f2_for_vec(pos)
    w, h = unpack_VecOrNum(size)
    sx, sy = unpack_VecOrNum(step)
    off_x, off_y = f2_for_vec(off)
    if off_x <= 0: off_x = sx # Do not emit line at 0, because that is handled by border.
    if off_y <= 0: off_y = sy # Do not emit line at 0, because that is handled by border.
    x_start = x + off_x
    y_start = y + off_y
    x_end = x + w
    y_end = y + h
    class_ = attrs.setdefault('class_', 'grid')
    # TODO: if we are really going to support rounded corners then the border rect should clip the interior lines.
    with self.g(**attrs):
      for tick in NumRange(x_start, x_end, sx): self.line((tick, y), (tick, y_end)) # Vertical lines.
      for tick in NumRange(y_start, y_end, sy): self.line((x, tick), (x_end, tick)) # Horizontal lines.
      self.rect(class_=class_+'-border', x=x, y=y, w=w, h=h, r=r, fill='none')


  def plot(self, pos:Vec=(0,0), size:Vec=(512,1024), *, series:Sequence['PlotSeries'],
   min_x=None, max_x=None, min_y=None, max_y=None,
   visible_x0=False, visible_y0=False, symmetric_x=False, symmetric_y=False, symmetric_xy=False,
   r:VecOrNum=None, grid_step:VecOrNum=None, **attrs:Any) -> 'Plot':
    return Plot(file=self.file, pos=pos, size=size, series=series,
     min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y,
     visible_x0=visible_x0, visible_y0=visible_y0, symmetric_x=symmetric_x, symmetric_y=symmetric_y, symmetric_xy=symmetric_xy,
     r=r, grid_step=grid_step, **attrs)


class SvgWriter(SvgBase):
  '''
  SvgWriter is a ContextManager class that outputs SVG code to a file (stdout by default).
  Like its parent class XmlWriter, it uses the __enter__ and __exit__ methods to automatically output open and close tags.
  '''
  def __init__(self, file:TextIO=None, pos:Vec=None, size:VecOrNum=None, *, x:Dim=None, y:Dim=None, w:Dim=None, h:Dim=None,
   vx:Num=0, vy:Num=0, vw:Num=None, vh:Num=None, **attrs:Any) -> None:
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
    attrs = { # Put the xml nonsense up front.
      'xmlns': 'http://www.w3.org/2000/svg',
      'xmlns:xlink': 'http://www.w3.org/1999/xlink', # Safari does not yet support SVG 2.
      **attrs
    }
    add_opt_attrs(attrs, x=x, y=y, width=w, height=h, viewBox=self.viewBox)
    super().__init__(tag='svg', file=file, attrs=attrs)


# Plots.

Plotter = Callable[[SvgBase, PointTransform, Tuple], None]

def circle_plotter(r:Num=1, **attrs:Any) -> Plotter:
  attrs.setdefault('class_', 'series')
  def plotter(svg:SvgBase, transform:PointTransform, point:Tuple) -> None:
    svg.circle(transform(point), r=r, title=', '.join(str(f) for f in point))
  return plotter


class PlotSeries:

  bounds:Optional[Tuple[Vec, Vec]] = None # Overridden by subclasses.

  def render(self, svg:SvgBase, transform:PointTransform) -> None: raise NotImplementedError



class XYSeries(PlotSeries):

  def __init__(self, name:str, points:Sequence[Tuple], plotter:Optional[Plotter]=circle_plotter(), **attrs:Any) -> None:
    self.name = name
    self.points = list(points) # TODO: clamp points to visible range, possibly plus margin.
    self.plotter = plotter
    attrs.setdefault('id', name)
    attrs.setdefault('class_', 'series')
    self.attrs = attrs
    self.bounds = None
    if self.points:
      x, y = self.points[0][:2]
      min_x = x
      max_x = x
      min_y = y
      max_y = y
      for p in self.points:
        x = p[0]
        y = p[1]
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
      self.bounds = ((min_x, min_y), (max_x, max_y))


  def render(self, svg:SvgBase, transform:PointTransform) -> None:
    assert self.plotter is not None
    with svg.g(**self.attrs):
      for p in self.points: self.plotter(svg, transform, p)


class LineSeries(XYSeries):

  def __init__(self, name:str, points:Sequence[Tuple], plotter:Plotter=None, **attrs:Any) -> None:
    super().__init__(name=name, points=points, plotter=plotter, **attrs)


  def render(self, svg:SvgBase, transform:PointTransform) -> None:
    with svg.g(**self.attrs):
      svg.polyline(points=(transform(p) for p in self.points), fill='none')
      # TODO: option to fill polylines.
      if self.plotter is not None:
        for p in self.points: self.plotter(svg, transform, p)


class Plot(SvgBase):

  def __init__(self, file:TextIO, pos:Vec=(0,0), size:Vec=(512,1024),
   *, series:Sequence[PlotSeries],
   min_x=None, max_x=None, min_y=None, max_y=None,
   visible_x0=False, visible_y0=False, symmetric_x=False, symmetric_y=False, symmetric_xy=False,
   r:VecOrNum=None, grid_step:VecOrNum=None,
   title:str=None, title_h:float=0.0,
   **attrs:Any) -> None:

    self.pos = pos
    self.size = size
    self.series = series
    self.visible_x0 = visible_x0
    self.visible_y0 = visible_y0
    self.symmetric_x = symmetric_x
    self.symmetric_y = symmetric_y
    self.symmetric_xy = symmetric_xy
    self.r = r
    self.grid_step = grid_step

    self.title = title
    if title is None:
      self.title_h = 0.0
    elif title_h == 0.0: raise ValueError('Plot.title_h must be positive')
    else:
      self.title_h = title_h

    self.w = size[0]
    self.h = size[1] + self.title_h

    # Determine bounds.
    expand_min_x = min_x is None
    expand_max_x = max_x is None
    expand_min_y = min_y is None
    expand_max_y = max_y is None
    for s in series:
      b = s.bounds
      if b is not None:
        (mnx, mny), (mxx, mxy) = b
        if expand_min_x: min_x = mnx if (min_x is None) else min(min_x, mnx)
        if expand_max_x: max_x = mxx if (max_x is None) else max(max_x, mxx)
        if expand_min_y: min_y = mny if (min_y is None) else min(min_y, mny)
        if expand_max_y: max_y = mxy if (max_y is None) else max(max_y, mxy)

    if min_x is None: min_x = 0
    if min_y is None: min_y = 0
    if max_x is None or max_x <= min_x: max_x = min_x + 1
    if max_y is None or max_y <= min_y: max_y = min_y + 1

    if visible_x0:
      if min_x > 0: min_x = 0
      elif max_x < 0: max_x = 0
    if visible_y0:
      if min_y > 0: min_y = 0
      elif max_y < 0: max_y = 0

    if symmetric_xy:
      max_x = max_y = max(max_x, -min_x, max_y, -min_y)
      min_x = min_y = -max_x
    else:
      if symmetric_x:
        max_x = max(max_x, -min_x)
        min_x = -max_x
      if symmetric_y:
        max_y = max(max_y, -min_y)
        min_y = -max_y

    self.min_x = min_x
    self.max_x = max_x
    self.min_y = min_y
    self.max_y = max_y

    data_w = max_x - min_x
    data_h = max_y - min_y
    self.data_w = data_w
    self.data_h = data_h

    scale_x = size[0] / data_w
    scale_y = size[1] / data_h
    self.scale = (scale_x, scale_y)

    def transform(point:tuple) -> Vec:
      return ((point[0]-min_x) * scale_x, (data_h - (point[1]-min_y)) * scale_y)

    self.transform = transform

    y = self.title_h
    # Initialize as `g` element.
    attrs.setdefault('class_', 'plot')
    attrs['transform'] = translate(pos[0], pos[1] + y)
    super().__init__(tag='g', file=file, attrs=attrs)

    # Title.
    if self.title is not None:
      self.text((0, -y), text=self.title, class_='title', text_anchor='left', alignment_baseline='hanging')

    # Grid.
    if grid_step is not None:
      if isinstance(grid_step, tuple):
        step_x, step_y = grid_step
      else:
        step_x = step_y = grid_step
      grid_w = data_w*scale_x
      grid_h = data_h*scale_y
      off_x = scale_x * (step_x - min_x % step_x)
      off_y = scale_y * (step_y - min_y % step_y)
      self.grid(pos=(0, 0), size=(grid_w, grid_h), step=(step_x*scale_x, step_y*scale_y), off=(off_x, off_y), r=r,
        transform=f'{scale(1,-1)} {translate(0, -grid_h)}')

    # Axes.
    if min_y <= 0 and max_y >= 0: # Draw x axis.
      self.line(transform((0, min_y)), transform((0, max_y)), class_='axis', id='x-axis')
    if min_x <= 0 and max_x >= 0: # Draw y axis.
      self.line(transform((min_x, 0)), transform((max_x, 0)), class_='axis', id='y-axis')

    # Series.
    for s in series:
      s.render(self, transform)



# Transforms.

def scale(x:Num=1, y:Num=1) -> str: return f'scale({x},{y})'
def rotate(degrees:Num, x:Num=0, y:Num=0) -> str: return f'rotate({degrees},{x},{y})'
def translate(x:Num=0, y:Num=0) -> str: return f'translate({x},{y})'


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


def fmt_viewBox(vx:Optional[Num], vy:Optional[Num], vw:Optional[Num], vh:Optional[Num]) -> Optional[str]:
  if vw is None and vh is None:
    return None
  else:
    if vx is None: vx = 0
    if vy is None: vy = 0
    assert vw is not None and vw > 0
    assert vh is not None and vh > 0
    return f'{fmt_num(vx)} {fmt_num(vy)} {fmt_num(vw)} {fmt_num(vh)}'


@overload
def fmt_num(n:Num) -> str: ...
@overload
def fmt_num(n:Optional[Num]) -> Optional[str]: ...

def fmt_num(n:Optional[Num]) -> Optional[str]:
  if n is None: return None
  if isinstance(n, float):
    i = int(n)
    if i == n: return str(i)
  return str(n)


def f2_for_vec(v:Vec) -> F2:
  x, y = v
  return (float(x), float(y))


def unpack_VecOrNum(vn:VecOrNum) -> Tuple[float, float]:
  if isinstance(vn, tuple):
    x, y = vn
    return float(x), float(y)
  else:
    s = float(vn)
    return (s, s)


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
