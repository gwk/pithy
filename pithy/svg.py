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

PointTransform = Callable[[Tuple], F2]

Tick = Union[bool, Callable[[float], Any]]


class SvgWriter(XmlWriter):

  replaced_attrs = {
    'href': 'xlink:href', # safari Version 11.1.1 requires this, even though xlink is deprecated in svg 2 standard.
    **XmlWriter.replaced_attrs,
  }

  def __init__(self, *args:Any, children:Iterable[Any]=(), tag:str=None, file:TextIO=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    '`title` attribute gets converted into a child element (renders in browsers as a tooltip).'
    if attrs:
      try: title = attrs.pop('title')
      except KeyError: pass
      else:
        tail_children = tuple(children) or (Ellipsis,)
        children = (SvgTitle(children=(str(title),)), *tail_children)
    super().__init__(*args, children=children, tag=tag, file=file, attrs=attrs, **kwargs)


  # SVG Elements.


  def circle(self, pos:Vec=None, r:Num=None, x:Num=None, y:Num=None, **attrs:Any) -> None:
    'Output an SVG `circle` element.'
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    add_opt_attrs(attrs, cx=fmt_num(x), cy=fmt_num(y), r=fmt_num(r))
    self.child(SvgWriter, tag='circle', attrs=attrs).close()


  def clipPath(self, **attrs:Any) -> 'SvgWriter':
    'Output an SVG `clipPath` element.'
    return self.child(SvgWriter, tag='clipPath', attrs=attrs)


  def defs(self, **attrs:Any) -> 'SvgWriter':
    'Output an SVG `defs` element.'
    return self.child(SvgWriter, tag='defs', attrs=attrs)


  def g(self, *transforms:str, **attrs:Any) -> 'SvgWriter':
    'Create an SVG `g` element for use in a context manager.'
    add_opt_attrs(attrs, transform=(' '.join(transforms) if transforms else None))
    return self.child(SvgWriter, tag='g', attrs=attrs)


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
    self.child(SvgWriter, tag='image', attrs=attrs).close()


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
    self.child(SvgWriter, tag='line', attrs=attrs).close()


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
    return self.child(SvgWriter, tag='marker', attrs=attrs)


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
    self.child(SvgWriter, tag='path', attrs=attrs).close()


  def polyline(self, points:Iterable[Vec], **attrs:Any) -> None:
    point_strs:List[str] = []
    assert 'points' not in attrs
    for p in points:
      if len(p) < 2: raise Exception(f'bad point for polyline: {p}')
      point_strs.append(f'{fmt_num(p[0])},{fmt_num(p[1])}')
    attrs['points'] = ' '.join(point_strs)
    self.child(SvgWriter, tag='polyline', attrs=attrs).close()


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
    self.child(SvgWriter, tag='rect', attrs=attrs).close()


  def style(self, *text:str, **attrs,) -> None:
    'Output an SVG `style` element.'
    self.child(SvgWriter, tag='style', attrs=attrs, children=text).close()


  def symbol(self, id:str, *, vx:Num=None, vy:Num=None, vw:Num=None, vh:Num=None, **attrs:Any) -> 'SvgWriter':
    'Output an SVG `symbol` element.'
    if vx is None: vx = 0
    if vy is None: vy = 0
    # TODO: figure out if no viewBox is legal and at all useful.
    assert vw >= 0 # type: ignore
    assert vh >= 0 # type: ignore
    add_opt_attrs(attrs, id=id, viewBox=f'{vx} {vy} {vw} {vh}')
    return self.child(SvgWriter, tag='symbol', attrs=attrs)


  def text(self, pos:Vec=None, *, x:Num=None, y:Num=None, alignment_baseline:str=None, text:str=None, **attrs:Any) -> None:
    'Output an SVG `text` element.'
    assert text is not None
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if alignment_baseline is not None and alignment_baseline not in alignment_baselines: raise ValueError(alignment_baseline)
    add_opt_attrs(attrs, x=fmt_num(x), y=fmt_num(y), alignment_baseline=alignment_baseline)
    self.child(SvgWriter, tag='text', attrs=attrs, children=[text]).close()


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
    self.child(SvgWriter, tag='use', attrs=attrs).close()


  # High level.

  def grid(self, pos:Vec=(0,0), size:VecOrNum=(256,256), *,
   step:VecOrNum=16, off:Vec=(0, 0), corner_radius:VecOrNum=None, **attrs:Any) -> None:
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
    with self.g(**attrs) as g:
      for tick in NumRange(x_start, x_end, sx): g.line((tick, y), (tick, y_end)) # Vertical lines.
      for tick in NumRange(y_start, y_end, sy): g.line((x, tick), (x_end, tick)) # Horizontal lines.
      g.rect(class_=class_+'-border', x=x, y=y, w=w, h=h, r=corner_radius, fill='none')


  def plot(self, pos:Vec=(0,0), size:Vec=(512,1024),
   *, series:Sequence['PlotSeries'],
   title:str=None,
   title_h:Num=0,
   tick_h:Num=0, tick_w:Num=0,
   min_x:Num=None, max_x:Num=None, min_y:Num=None, max_y:Num=None,
   visible_x0=False, visible_y0=False, symmetric_x=False, symmetric_y=False, symmetric_xy=False,
   corner_radius:VecOrNum=None,
   grid_step:VecOrNum=5,
   tick_step:VecOrNum=10,
   tick_x:Tick=False, tick_y:Tick=False,
   dbg=False,
   **attrs:Any) -> 'Plot':

    return self.child(Plot, attrs=attrs,
      pos=pos, size=size, series=series,
      title=title,
      title_h=title_h,
      tick_h=tick_h, tick_w=tick_w,
      min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y,
      visible_x0=visible_x0, visible_y0=visible_y0, symmetric_x=symmetric_x, symmetric_y=symmetric_y, symmetric_xy=symmetric_xy,
      corner_radius=corner_radius,
      grid_step=grid_step,
      tick_step=tick_step,
      tick_x=tick_x,
      tick_y=tick_y,
      dbg=dbg)


class Svg(SvgWriter):
  '''
  Svg is a ContextManager class that outputs SVG code to a file (stdout by default).
  Like its parent class XmlWriter, it uses the __enter__ and __exit__ methods to automatically output open and close tags.
  '''

  tag = 'svg'

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
    assert not isinstance(file, str)
    super().__init__(file=file, attrs=attrs)


# Plots.

Plotter = Callable[[SvgWriter, PointTransform, Tuple], None]

def circle_plotter(r:Num=1, **attrs:Any) -> Plotter:
  attrs.setdefault('class_', 'series')
  def plotter(svg:SvgWriter, transform:PointTransform, point:Tuple) -> None:
    svg.circle(transform(point), r=r, title=', '.join(str(f) for f in point))
  return plotter


class PlotSeries:

  bounds:Optional[Tuple[Vec, Vec]] = None # Overridden by subclasses.

  def render(self, plot:'Plot') -> None: raise NotImplementedError



class XYSeries(PlotSeries):

  def __init__(self, name:str, points:Sequence[Tuple], plotter:Optional[Plotter]=circle_plotter(), **attrs:Any) -> None:
    self.name = name
    self.points = list(points)
    self.plotter = plotter
    attrs.setdefault('id', name)
    attrs.setdefault('class_', 'series')
    self.attrs = attrs
    self.bounds:Optional[Tuple[F2, F2]] = None
    if self.points:
      x, y = self.points[0][:2]
      min_x = max_x = float(x)
      min_y = max_y = float(y)
      for p in self.points:
        x = float(p[0])
        y = float(p[1])
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
      self.bounds = ((min_x, min_y), (max_x, max_y))


  def render(self, plot:'Plot') -> None:
    # TODO: collect and return out-of-bounds points.
    assert self.plotter is not None
    with plot.g(clip_path=plot.plot_clip_path, **self.attrs) as g:
      for p in self.points: self.plotter(g, plot.transform, p)


class LineSeries(XYSeries):

  def __init__(self, name:str, points:Sequence[Tuple], plotter:Plotter=None, **attrs:Any) -> None:
    super().__init__(name=name, points=points, plotter=plotter, **attrs)


  def render(self, plot:'Plot') -> None:
    with plot.g(clip_path=plot.plot_clip_path, **self.attrs) as g:
      g.polyline(points=(plot.transform(p) for p in self.points), fill='none')
      # TODO: option to fill polylines.
      if self.plotter is not None:
        for p in self.points: self.plotter(g, plot.transform, p)


class Plot(SvgWriter):

  tag = 'g'

  def __init__(self, *, tag:str, file:TextIO, attrs:XmlAttrs=None, children:Iterable[Any],
   pos:Vec=(0,0), size:Vec=(512,1024),
   series:Sequence[PlotSeries],
   title:str=None,
   title_h:Num=0,
   tick_h:Num=0, tick_w:Num=0,
   min_x:Num=None, max_x:Num=None, min_y:Num=None, max_y:Num=None,
   visible_x0=False, visible_y0=False, symmetric_x=False, symmetric_y=False, symmetric_xy=False,
   corner_radius:VecOrNum=None,
   grid_step:VecOrNum=5,
   tick_step:VecOrNum=10,
   tick_x:Tick=False, tick_y:Tick=False,
   dbg=False) -> None:

    attrs = attrs or {}
    pos = f2_for_vec(pos)
    # Initialize as `g` element.
    attrs.setdefault('class_', 'plot')
    attrs['transform'] = translate(*pos)
    super().__init__(tag=tag, file=file, attrs=attrs)

    title_h = float(title_h)

    self.pos = pos
    self.size = size = f2_for_vec(size)
    self.series = series
    self.title = title
    self.title_h = title_h = float(title_h)
    self.tick_w = tick_w = float(tick_w)
    self.tick_h = tick_h = float(tick_h)
    self.visible_x0 = visible_x0
    self.visible_y0 = visible_y0
    self.symmetric_x = symmetric_x
    self.symmetric_y = symmetric_y
    self.symmetric_xy = symmetric_xy
    self.corner_radius = corner_radius
    self.grid_step = grid_step = unpack_VecOrNum(grid_step)
    self.tick_step = tick_step = unpack_VecOrNum(tick_step)

    self.tick_x = tick_x
    self.tick_y = tick_y
    self.w = size[0]
    self.h = size[1]

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

    if min_x is None: min_x = 0.0
    if min_y is None: min_y = 0.0
    if max_x is None or max_x <= min_x: max_x = min_x + 1.0
    if max_y is None or max_y <= min_y: max_y = min_y + 1.0

    if visible_x0:
      if min_x > 0.0: min_x = 0.0
      elif max_x < 0.0: max_x = 0.0
    if visible_y0:
      if min_y > 0.0: min_y = 0.0
      elif max_y < 0.0: max_y = 0.0

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


    min_x = float(min_x)
    max_x = float(max_x)
    min_y = float(min_y)
    max_y = float(max_y)

    self.min_x:float = min_x
    self.max_x:float = max_x
    self.min_y:float = min_y
    self.max_y:float = max_y

    self.data_w = data_w = max_x - min_x
    self.data_h = data_h = max_y - min_y

    self.grid_x = grid_x = tick_w
    self.grid_y = grid_y = title_h
    self.grid_pos = grid_pos = (grid_x, grid_y)

    self.grid_w = grid_w = self.w - tick_w - 1
    self.grid_h = grid_h = self.h - title_h - tick_h - 1
    self.grid_size = grid_size = (grid_w, grid_h)

    self.grid_r = grid_r = grid_x + grid_w
    self.grid_b = grid_b = grid_y + grid_h

    self.scale_x = scale_x = grid_w / data_w
    self.scale_x = scale_y = grid_h / data_h
    self.scale = (scale_x, scale_y)

    def transform(point:tuple) -> F2:
      'Translate a point to appear coincident with the data space.'
      x = float(point[0])
      y = float(point[1])
      return (round(grid_x + scale_x*(x-min_x), 1), round(grid_y + scale_y*(data_h - (y-min_y)), 1)) # type: ignore

    def transform_x(x:Num) -> float: return round(grid_x + scale_x*(float(x) - min_x), 1) # type: ignore
    def transform_y(y:Num) -> float: return round(grid_y + scale_y*(data_h - (float(y)-min_y)), 1) # type: ignore

    self.transform = transform
    self.transform_x = transform_x
    self.transform_y = transform_y

    if dbg:
      def dbg_rect(pos:Vec, size:Vec, fill:str) -> None:
        self.rect(pos, size, stroke=None, fill=fill, opacity=0.1)
    else:
      def dbg_rect(pos:Vec, size:Vec, fill:str) -> None: pass

    dbg_rect((0, 0), self.size, fill='#000')

    # Title.
    dbg_rect((0, 0), (self.w, title_h), fill='#F00')

    if self.title is not None:
      self.text((tick_w, title_h/2), text=self.title, class_='title', text_anchor='left', alignment_baseline='middle')

    # Grid.
    grid_trans = translate(grid_x, grid_y+grid_h)
    if grid_step is not None:
      gsx, gsy = unpack_VecOrNum(grid_step)
      g_start_x = (min_x//gsx + 1) * gsx # Skip line index 0 because it is always <= low border.
      g_start_y = (min_y//gsy + 1) * gsy # Skip line index 0 because it is always <= low border.
    # TODO: if we are really going to support rounded corners then the border rect should clip the interior lines.
    with self.g(class_='grid') as g:
      for gx in NumRange(g_start_x, max_x, gsx): # X axis.
        tgx = transform_x(gx)
        g.line((tgx, grid_y), (tgx, grid_b)) # Vertical lines.
      for gy in NumRange(g_start_y, max_y, gsy):
        tgy = transform_y(gy)
        g.line((grid_x, tgy), (grid_r, tgy)) # Horizontal lines.
      g.rect(class_='grid-border', pos=grid_pos, size=grid_size, r=corner_radius, fill='none')

    # Clip.
    with self.clipPath(id='plot-clip') as clipPath:
      clipPath.rect(pos=grid_pos, size=grid_size, r=corner_radius)
    self.plot_clip_path = 'url(#plot-clip)'

    # Axes.
    if min_y <= 0 and max_y >= 0: # Draw X axis.
      y0 = transform_y(0)
      self.line((grid_x, y0), (grid_r, y0), class_='axis', id='x-axis')
    if min_x <= 0 and max_x >= 0: # Draw Y axis.
      x0 = transform_x(0)
      self.line((x0, grid_y), (x0, grid_b), class_='axis', id='y-axis')

    # Ticks.
    dbg_rect((grid_x, grid_b), (grid_w, tick_h), fill='#088') # X axis ticks.
    dbg_rect((0, grid_y), (tick_w, grid_h), fill='#08F') # Y axis ticks.

    tsx, tsy = unpack_VecOrNum(tick_step)
    txi, txr = divmod(min_x, tsx)
    tyi, tyr = divmod(min_y, tsy)
    t_start_x = txi*tsx + (txr and tsx)
    t_start_y = tyi*tsy + (tyr and tsy)

    if tick_x:
      if not callable(tick_x): tick_x = str
      for x in NumRange(t_start_x, max_x, step=tsx, closed=False):
        tx = transform_x(x)
        self.line((tx, grid_b), (tx, grid_b+2), class_='tick')
        self.text((tx+1, grid_b+2), class_='tick', text=tick_x(x), alignment_baseline='hanging')
    if tick_y:
      if not callable(tick_y): tick_y = str
      for y in NumRange(t_start_y, max_y, step=tsy, closed=True):
        tx = grid_x - 2
        ty = transform_y(y)
        self.line((tx, ty), (grid_x, ty), class_='tick')
        self.text((tx-1, ty), class_='tick', text=tick_y(y), text_anchor='end', alignment_baseline='middle')

    # Series.
    for s in series:
      s.render(self)


# Elements.

class SvgTitle(SvgWriter):
  tag = 'title'


# Transforms.

def scale(x:Num=1, y:Num=1) -> str: return f'scale({x},{y})'
def rotate(degrees:Num, x:Num=0, y:Num=0) -> str: return f'rotate({fmt_num(degrees)},{fmt_num(x)},{fmt_num(y)})'
def translate(x:Num=0, y:Num=0) -> str: return f'translate({fmt_num(x)},{fmt_num(y)})'


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
  'Remove trailing ".0" from floats that can be represented as integers.'
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
