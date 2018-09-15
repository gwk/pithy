# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
SVG writer.
SVG elements reference: https://developer.mozilla.org/en-US/docs/Web/SVG/Element.
'''

from .iterable import iter_unique
from .num import Num, NumRange
from .xml import _Counter, XmlAttrs, XmlWriter, add_opt_attrs, esc_xml_attr, esc_xml_text
from functools import reduce
from html import escape as html_escape
from math import floor, log10
from types import TracebackType
from typing import Any, Callable, ContextManager, Dict, Iterator, List, Optional, Sequence, TextIO, Tuple, Type, Union, Iterable, overload


Dim = Union[int, float, str]
Vec = Tuple[Num, Num]
VecOrNum = Union[Vec, Num]
F2 = Tuple[float, float]
F2OrF = Union[F2, float]
BoundsF2 = Tuple[F2, F2]
PathCommand = Tuple

PointTransform = Callable[[Tuple], F2]

TickFmt = Callable[[float], Any]


class SvgWriter(XmlWriter):

  replaced_attrs = {
    'href': 'xlink:href', # safari Version 11.1.1 requires this, even though xlink is deprecated in svg 2 standard.
    **XmlWriter.replaced_attrs,
  }

  def __init__(self, *args:Any, children:Iterable[Any]=(), tag:str=None, file:TextIO=None, attrs:XmlAttrs=None,
   _id_counter:_Counter=None, _class_counter:_Counter=None, **kwargs:Any) -> None:
    '`title` attribute gets converted into a child element (renders in browsers as a tooltip).'
    if attrs:
      try: title = attrs.pop('title')
      except KeyError: pass
      else:
        tail_children = tuple(children) or (Ellipsis,)
        children = (SvgTitle(children=(str(title),)), *tail_children)
    super().__init__(*args, children=children, tag=tag, file=file, attrs=attrs,
      _id_counter=_id_counter, _class_counter=_class_counter, **kwargs)


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


  def plot(self, pos:Vec=(0,0), size:Vec=(512,1024), *,
   x:'PlotAxis'=None, y:'PlotAxis'=None,
   series:Sequence['PlotSeries'],
   title:str=None,
   title_h:Num=14,
   axis_label_h:Num=12,
   tick_h:Num=10,
   tick_len:Num=4,
   corner_radius:VecOrNum=None,
   symmetric_xy=False,
   dbg=False,
   **attrs:Any) -> 'Plot':

    return self.child(Plot, attrs=attrs,
      pos=pos, size=size,
      x=x, y=y,
      series=series,
      title=title,
      title_h=title_h,
      axis_label_h=axis_label_h,
      tick_h=tick_h,
      tick_len=tick_len,
      corner_radius=corner_radius,
      symmetric_xy=symmetric_xy,
      dbg=dbg)



class Svg(SvgWriter):
  '''
  Svg is a ContextManager class that outputs SVG code to a file (stdout by default).
  Like its parent class XmlWriter, it uses the __enter__ and __exit__ methods to automatically output open and close tags.
  '''

  tag = 'svg'

  def __init__(self, file:TextIO=None, pos:Vec=None, size:VecOrNum=None, *, x:Dim=None, y:Dim=None, w:Dim=None, h:Dim=None,
   vx:Num=0, vy:Num=0, vw:Num=None, vh:Num=None,
   _id_counter:_Counter=None, _class_counter:_Counter=None, **attrs:Any) -> None:
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
    super().__init__(file=file, attrs=attrs, _id_counter=_id_counter, _class_counter=_class_counter)


# Plots.

Plotter = Callable[[SvgWriter, PointTransform, Any], None]

def circle_plotter(r:Num=1, **attrs:Any) -> Plotter:
  attrs.setdefault('class_', 'series')
  def plotter(svg:SvgWriter, transform:PointTransform, point:Tuple) -> None:
    svg.circle(transform(point), r=r, title=', '.join(str(f) for f in point))
  return plotter



class PlotSeries:

  bounds:Optional[BoundsF2] = None # Overridden by subclasses.

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
      x_min = x_max = float(x)
      y_min = y_max = float(y)
      for p in self.points:
        x = float(p[0])
        y = float(p[1])
        x_min = min(x_min, x)
        x_max = max(x_max, x)
        y_min = min(y_min, y)
        y_max = max(y_max, y)
      self.bounds = ((x_min, y_min), (x_max, y_max))


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
      g.polyline(points=iter_unique(plot.transform(p) for p in self.points), fill='none')
      # TODO: option to fill polylines.
      if self.plotter is not None:
        for p in self.points: self.plotter(g, plot.transform, p)



class PlotAxis:
  def __init__(self, *,
   length:Num=0,
   min:Optional[Num]=None, max:Optional[Num]=None,
   visible_origin=False,
   symmetric=False,
   show_grid=True, grid_step:Optional[Num]=None, grid_min:Num=16,
   show_ticks=True, tick_step:Optional[Num]=None, tick_space:Num=1, tick_w:Num=16, tick_fmt:Optional[TickFmt]=None) -> None:
    self.length = float(length) # For <=0 the screen length is calculated automatically.
    self.min = min if min is None else float(min)
    self.max = max if max is None else float(max)
    self.visible_origin = visible_origin
    self.symmetric = symmetric
    self.show_grid = show_grid
    self.grid_step:Optional[float] = grid_step if grid_step is None else float(grid_step)
    self.grid_min = float(grid_min)
    self.show_ticks = show_ticks
    self.tick_step:Optional[float] = tick_step if tick_step is None else float(tick_step)
    self.tick_space = float(tick_space)
    self.tick_w = float(tick_w)
    self.tick_fmt = tick_fmt

  def x_axis_tick_h(self, tick_len:float, tick_h:float) -> float:
    return (tick_len + self.tick_space + tick_h) if self.show_ticks else 0.0

  def y_axis_tick_w(self, tick_len:float) -> float:
    return (tick_len + self.tick_space + self.tick_w) if self.show_ticks else 0.0



class Plot(SvgWriter):

  tag = 'g'

  def __init__(self, *, tag:str, file:TextIO, attrs:XmlAttrs=None, children:Iterable[Any],
   pos:Vec=(0,0), size:Vec=(512,1024),
   x:PlotAxis=None, y:PlotAxis=None,
   series:Sequence[PlotSeries],
   title:str=None,
   title_h:Num=14,
   axis_label_h:Num=12,
   tick_h:Num=10,
   tick_len:Num=4,
   corner_radius:VecOrNum=None,
   symmetric_xy=False,
   dbg=False,
   _id_counter:_Counter=None, _class_counter:_Counter=None) -> None:

    attrs = attrs or {}
    pos = f2_for_vec(pos)
    # Initialize as `g` element.
    attrs.setdefault('class_', 'plot')
    attrs['transform'] = translate(*pos)
    super().__init__(tag=tag, file=file, attrs=attrs, _id_counter=_id_counter, _class_counter=_class_counter)

    self.pos = pos
    self.size = size = f2_for_vec(size)
    self.x = x = PlotAxis() if x is None else x
    self.y = y = PlotAxis() if y is None else y
    self.series = series
    self.title = title
    self.title_h = title_h = 0.0 if title is None else float(title_h)
    self.tick_len = tick_len = float(tick_len)
    self.axis_label_h = axis_label_h = float(axis_label_h)
    self.tick_h = tick_h = float(tick_h)
    self.corner_radius = corner_radius
    self.symmetric_xy = symmetric_xy
    self.w = size[0]
    self.h = size[1]

    # Determine data bounds.
    x_min:Optional[float] = x.min
    x_max:Optional[float] = x.max
    y_min:Optional[float] = y.min
    y_max:Optional[float] = y.max
    b = reduce(expand_opt_bounds, (s.bounds for s in series), None)
    if x_min is None: x_min = 0.0 if b is None else b[0][0]
    if y_min is None: y_min = 0.0 if b is None else b[0][1]
    if x_max is None: x_max = x_min + 1.0 if b is None else b[1][0]
    if y_max is None: y_max = y_min + 1.0 if b is None else b[1][1]

    if x.visible_origin:
      if x_min > 0.0:   x_min = 0.0
      elif x_max < 0.0: x_max = 0.0
    if self.y.visible_origin:
      if y_min > 0.0:   y_min = 0.0
      elif y_max < 0.0: y_max = 0.0

    if x.symmetric:
      x_max = max(x_max, -x_min)
      x_min = -x_max
    if y.symmetric:
      y_max = max(y_max, -y_min)
      y_min = -y_max
    if symmetric_xy:
      x_min = y_min = min(x_min, y_min)
      x_max = y_max = max(x_max, y_max)

    self.x_min = x_min
    self.x_max = x_max
    self.y_min = y_min
    self.y_max = y_max

    self.data_w = data_w = x_max - x_min
    self.data_h = data_h = y_max - y_min
    self.data_size = data_size = (data_w, data_h)

    # Layout measurements.
    self.grid_x = grid_x = 0
    self.grid_y = grid_y = title_h
    self.grid_pos = grid_pos = (grid_x, grid_y)

    boundary_pad = 1 # Otherwise right/bottom can disappear.
    x_axis_tick_h = x.x_axis_tick_h(tick_len, tick_h)
    y_axis_tick_w = y.y_axis_tick_w(tick_len)
    self.grid_w = grid_w = x.length or (self.w - boundary_pad - max(x.tick_w, y_axis_tick_w))
    self.grid_h = grid_h = y.length or (self.h - boundary_pad - x_axis_tick_h - title_h)
    self.grid_size = grid_size = (grid_w, grid_h)

    self.grid_r = grid_r = grid_x + grid_w
    self.grid_b = grid_b = grid_y + grid_h

    self.scale_x = scale_x = grid_w / data_w
    self.scale_y = scale_y = grid_h / data_h
    self.scale = (scale_x, scale_y)

    def choose_step(data_len:float, grid_len:float, min_screen_step:float) -> Tuple[float, int]:
      assert data_len > 0
      assert min_screen_step > 0
      cram_num = max(1.0, grid_len // min_screen_step) # Maximum number of ticks that could be placed.
      assert cram_num > 0, (cram_num, grid_len, min_screen_step)
      cram_step = data_len / cram_num # Minimum fractional data step.
      exp = floor(log10(cram_step))
      step1 = float(10**exp) # Low estimate of step.
      for mult in (1, 2, 5):
        step = step1 * mult
        if step >= cram_step: return step1, mult
      return step1, 10

    def calc_tick_step_and_fmt(axis:PlotAxis, data_low:float, data_len:float, grid_len:float, min_screen_step:float) -> Tuple[float, int, int, int]:
      assert grid_len > 0
      if axis.tick_step is not None:
        tick_step = axis.tick_step
        mult = 1 # Fake; just means that misaligned grid won't be fixed automatically.
      elif min_screen_step <= 0:
        return (0.0, 0, 0, 0)
      else:
        step1, mult = choose_step(data_len, grid_len, min_screen_step)
        tick_step = step1 * mult
      exp = floor(log10(tick_step))
      frac_w = max(0, -exp)
      f = '{:0.{}f}'
      fmt_w = max(
        len(f.format(data_low, frac_w)),
        len(f.format(data_low+data_len, frac_w)))
      return (tick_step, mult, fmt_w, frac_w)

    def calc_grid_step(axis:PlotAxis, data_len:float, grid_len:float, tick_mult:int) -> float:
      assert grid_len > 0
      if axis.grid_step is not None:
        assert axis.grid_step >= 0
        return axis.grid_step
      min_screen_step = axis.grid_min
      step1, mult = choose_step(data_len, grid_len, min_screen_step)
      if mult == 2 and tick_mult == 5: # Ticks will misalign to grid; bump grid to 2.5.
        return step1 * 2.5
      return step1 * mult

    tick_step_x, tick_mult_x, fmt_w_x, frac_w_x = \
    calc_tick_step_and_fmt(axis=x, data_low=x_min, data_len=data_w, grid_len=grid_w, min_screen_step=x.tick_w * 1.5)

    tick_step_y, tick_mult_y, fmt_w_y, frac_w_y = \
    calc_tick_step_and_fmt(axis=y, data_low=y_min, data_len=data_h, grid_len=grid_h, min_screen_step=tick_h * 2.0)

    self.tick_step_x = tick_step_x
    self.tick_step_y = tick_step_y
    self.tick_fmt_x = x.tick_fmt or (lambda t: f'{t:{fmt_w_x}.{frac_w_x}f}')
    self.tick_fmt_y = y.tick_fmt or (lambda t: f'{t:{fmt_w_y}.{frac_w_y}f}')

    self.grid_step_x = grid_step_x = calc_grid_step(axis=x, data_len=data_w, grid_len=grid_w, tick_mult=tick_mult_x)
    self.grid_step_y = grid_step_y = calc_grid_step(axis=y, data_len=data_h, grid_len=grid_h, tick_mult=tick_mult_y)

    def transform(point:Sequence) -> F2:
      'Translate a point to appear coincident with the data space.'
      x = float(point[0])
      y = float(point[1])
      return (round(grid_x + scale_x*(x-x_min), 1), round(grid_y + scale_y*(data_h - (y-y_min)), 1)) # type: ignore

    def transform_x(x:Num) -> float: return round(grid_x + scale_x*(float(x) - x_min), 1) # type: ignore
    def transform_y(y:Num) -> float: return round(grid_y + scale_y*(data_h - (float(y)-y_min)), 1) # type: ignore

    self.transform = transform
    self.transform_x = transform_x
    self.transform_y = transform_y

    if dbg:
      def dbg_rect(pos:Vec, size:Vec, stroke:str=None, fill:str=None, parent=self) -> None:
        parent.rect(pos, size, class_='DBG', stroke=stroke, fill=fill, opacity=0.2)
    else:
      def dbg_rect(pos:Vec, size:Vec, stroke:str=None, fill:str=None, parent=self) -> None: pass

    # Contents.
    self.style(
      _plot_style,
      f'text.title {{ font-size: {title_h}; }}\n',
      f'text.axis-label {{ font-size: {axis_label_h}; }}\n',
      f'text.tick {{ font-size: {tick_h}; }}\n',
    )

    dbg_rect((0, 0), self.size, stroke='#000')

    # Title.
    dbg_rect((0, 0), (self.w, title_h), fill='#F00')

    if self.title is not None:
      self.text((grid_x, 0), text=self.title, class_='title')

    # Clip path is is defined to match grid.
    clip_path_id = self.gen_id()
    self.plot_clip_path = f'url(#{clip_path_id})'
    with self.clipPath(id=clip_path_id) as clipPath:
      clipPath.rect(pos=grid_pos, size=grid_size, r=corner_radius)

    # Grid.
    # TODO: if we are really going to support rounded corners then the border rect should clip the interior lines.
    with self.g(class_='grid') as g:
      if x.show_grid:
        g_start_x = (x_min//grid_step_x + 1) * grid_step_x # Skip line index 0 because it is always <= low border.
        for gx in NumRange(g_start_x, x_max, grid_step_x): # X axis.
          tgx = transform_x(gx)
          g.line((tgx, grid_y), (tgx, grid_b)) # Vertical lines.
      if y.show_grid:
        g_start_y = (y_min//grid_step_y + 1) * grid_step_y # Skip line index 0 because it is always <= low border.
        for gy in NumRange(g_start_y, y_max, grid_step_y):
          tgy = transform_y(gy)
          g.line((grid_x, tgy), (grid_r, tgy)) # Horizontal lines.
      g.rect(class_='grid-border', pos=grid_pos, size=grid_size, r=corner_radius, fill='none')

    # Axes.
    if y_min <= 0 and y_max >= 0: # Draw X axis.
      y0 = transform_y(0)
      self.line((grid_x, y0), (grid_r, y0), class_='axis', id='x-axis')
    if x_min <= 0 and x_max >= 0: # Draw Y axis.
      x0 = transform_x(0)
      self.line((x0, grid_y), (x0, grid_b), class_='axis', id='y-axis')

    # Ticks.
    if x.show_ticks:
      with self.g(class_='tick-x') as g:
        txi, txr = divmod(x_min, tick_step_x)
        if txr > 0.1: txi += 1 # If the remainder is visually significant, skip the first tick.
        t_start_x = txi*tick_step_x
        for _x in NumRange(t_start_x, x_max, step=tick_step_x, closed=True):
          tx = transform_x(_x)
          ty = grid_b
          tb = ty + tick_len
          tty = tb + x.tick_space
          g.line((tx, ty), (tx, tb), class_='tick')
          dbg_rect((tx, tb), (x.tick_w, tick_h), fill='#008', parent=g)
          g.text((tx, tty), class_='tick', text=self.tick_fmt_x(_x))
    if y.show_ticks:
      with self.g(class_='tick-y') as g:
        tyi, tyr = divmod(y_min, tick_step_y)
        if tyr > 0.1: tyi += 1 # If the remainder is visually significant, skip the first tick.
        t_start_y = tyi*tick_step_y
        for _y in NumRange(t_start_y, y_max, step=tick_step_y, closed=True):
          tx = grid_r
          tr = tx + tick_len
          ttx = tr + y.tick_space
          ty = transform_y(_y)
          g.line((tx, ty), (tr, ty), class_='tick')
          dbg_rect((ttx, ty-tick_h*0.75), (y.tick_w, tick_h), fill='#080', parent=g)
          g.text((ttx, ty), class_='tick', text=self.tick_fmt_y(_y))

    # Series.
    for s in series:
      s.render(self)


_plot_style = '''
text {
  stroke: none;
  fill: currentColor;
}
text.title {
  text-anchor: start;
  alignment-baseline: hanging;
}
g.tick-x text.tick {
  white-space: pre;
  text-anchor: start;
  alignment-baseline: hanging;
}
g.tick-y text.tick {
  white-space: pre;
  text-anchor: start;
  alignment-baseline: alphabetic;
}
'''


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
def fmt_num(n:None) -> None: ...

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


def expand_opt_bounds(l:Optional[BoundsF2], r:Optional[BoundsF2]) -> Optional[BoundsF2]:
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
