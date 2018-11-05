# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
SVG writer.
SVG elements reference: https://developer.mozilla.org/en-US/docs/Web/SVG/Element.
'''

from .iterable import iter_unique, window_pairs
from .num import Num, NumRange
from .xml import _Counter, EscapedStr, XmlAttrs, XmlWriter, add_opt_attrs, esc_xml_attr, esc_xml_text
from functools import reduce
from html import escape as html_escape
from math import floor, log10
from types import TracebackType
from typing import Any, Callable, ContextManager, Dict, Hashable, Iterator, List, Mapping, \
Optional, Sequence, TextIO, Tuple, Type, Union, Iterable, overload


Dim = Union[int, float, str]
Vec = Tuple[Num, Num]
VecOrNum = Union[Vec, Num]
F2 = Tuple[float, float]
F2OrF = Union[F2, float]
BoundsF2 = Tuple[F2, F2]
PathCommand = Tuple

PointTransform = Callable[[Tuple], F2]

def _axis_transform_dummy(val:Num) -> float: raise Exception('missing transform')

TickFmt = Callable[[float], Any]


class SvgWriter(XmlWriter):

  replaced_attrs = {
    'href': 'xlink:href', # safari Version 11.1.1 requires this, even though xlink is deprecated in svg 2 standard.
    'w': 'width',
    'h': 'height',
    **XmlWriter.replaced_attrs,
  }

  def __init__(self, *children:Any, tag:str=None, title:Any=None, _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    'A `title` attribute gets converted into a child element, which renders in browsers as a tooltip.'
    super().__init__(*children, tag=tag, _counter=_counter, attrs=attrs, **kwargs)
    if title is not None:
      self.add(SvgTitle(title))


  def on_close(self) -> None:
    self.children.sort(key=lambda el: el.attrs.get('z_index', 0))


# Html and Svg share these classes.

class HtmlSvgWriter(XmlWriter):
  can_auto_close_tags = False # HTML5 dictates that each tag type either be self-closing or not.

class Script(XmlWriter):
  tag = 'script'

class Style(XmlWriter):
  tag = 'style'


# SVG leaf elements.

class Circle(SvgWriter):
  tag = 'circle'

  def __init__(self, pos:Vec=None, r:Num=None, x:Num=None, y:Num=None,
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    add_opt_attrs(kwargs, cx=fmt_num(x), cy=fmt_num(y), r=fmt_num(r))
    super().__init__(_counter=_counter, attrs=attrs, **kwargs)


class Image(SvgWriter):
  tag = 'image'

  def __init__(self, pos:Vec=None, size:VecOrNum=None, *, x:Num=None, y:Num=None, w:Num=None, h:Num=None,
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      w, h = unpack_VecOrNum(size)
    add_opt_attrs(kwargs, x=fmt_num(x), y=fmt_num(y), width=fmt_num(w), height=fmt_num(h))
    super().__init__(_counter=_counter, attrs=attrs, **kwargs)


class Line(SvgWriter):
  tag = 'line'

  def __init__(self, a:Vec=None, b:Vec=None, *, x1:Num=None, y1:Num=None, x2:Num=None, y2:Num=None,
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    if a is not None:
      assert x1 is None
      assert y1 is None
      x1, y1 = a
    if b is not None:
      assert x2 is None
      assert y2 is None
      x2, y2 = b
    add_opt_attrs(kwargs, x1=fmt_num(x1), y1=fmt_num(y1), x2=fmt_num(x2), y2=fmt_num(y2))
    super().__init__(_counter=_counter, attrs=attrs, **kwargs)


class Path(SvgWriter):
  tag = 'path'

  def __init__(self, commands:Iterable[PathCommand],
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    assert (attrs is None or 'd' not in attrs)
    assert 'd' not in kwargs
    cmd_strs:List[str] = []
    for c in commands:
      try: code = c[0]
      except IndexError: continue
      try: exp_len = _path_command_lens[code]
      except KeyError as e: raise Exception(f'bad path command code: {c!r}') from e
      if len(c) != exp_len + 1: raise Exception(f'path command requires {exp_len} arguments: {c}')
      cmd_strs.append(code + ','.join(fmt_num(n) for n in c[1:]))
    kwargs['d'] = ' '.join(cmd_strs)
    super().__init__(_counter=_counter, attrs=attrs, **kwargs)


class Poly(SvgWriter):

  def __init__(self, points:Iterable[Vec],
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    assert (attrs is None or 'points' not in attrs)
    assert 'points' not in kwargs
    point_strs:List[str] = []
    for p in points:
      if len(p) < 2: raise Exception(f'bad point for {self.tag}: {p}')
      point_strs.append(f'{fmt_num(p[0])},{fmt_num(p[1])}')
    kwargs['points'] = ' '.join(point_strs)
    super().__init__(_counter=_counter, attrs=attrs, **kwargs)


class Polygon(Poly):
  tag = 'polygon'

class Polyline(Poly):
  tag = 'polyline'


class Rect(SvgWriter):
  tag = 'rect'

  def __init__(self, pos:Vec=None, size:VecOrNum=None, *, x:Num=None, y:Num=None, w:Num=None, h:Num=None, r:VecOrNum=None,
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
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
    add_opt_attrs(kwargs, x=fmt_num(x), y=fmt_num(y), w=fmt_num(w), h=fmt_num(h), rx=fmt_num(rx), ry=fmt_num(ry))
    super().__init__(_counter=_counter, attrs=attrs, **kwargs)


class Text(SvgWriter):
  tag = 'text'

  def __init__(self, *text, pos:Vec=None, x:Num=None, y:Num=None, alignment_baseline:str=None,
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if alignment_baseline is not None and alignment_baseline not in alignment_baselines: raise ValueError(alignment_baseline)
    add_opt_attrs(kwargs, x=fmt_num(x), y=fmt_num(y), alignment_baseline=alignment_baseline)
    super().__init__(*text, _counter=_counter, attrs=attrs, **kwargs)


class TSpan(SvgWriter):
  tag = 'tspan'



class Use(SvgWriter):
  tag = 'use'

  def __init__(self, id:str, pos:Vec=None, size:VecOrNum=None, *, x:Num=None, y:Num=None, w:Num=None, h:Num=None,
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
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
    add_opt_attrs(kwargs, href=id, x=fmt_num(x), y=fmt_num(y), width=fmt_num(w), height=fmt_num(h))
    super().__init__(_counter=_counter, attrs=attrs, **kwargs)




class SvgBranch(SvgWriter):


  def circle(self, pos:Vec=None, r:Num=None, x:Num=None, y:Num=None, **attrs:Any) -> Circle:
    'Create a child `circle` element.'
    return self.child(Circle, pos=pos, r=r, x=x, y=y, **attrs)


  def clipPath(self, **attrs:Any) -> 'ClipPath':
    'Create a child `clipPath` element.'
    return self.child(ClipPath, **attrs)


  def defs(self, **attrs:Any) -> 'Defs':
    'Create a child `defs` element.'
    return self.child(Defs, **attrs)


  def g(self, transform:Iterable[str]='', **attrs:Any) -> 'G':
    'Create an SVG `g` element for use in a context manager.'
    return self.child(G, transform=transform, **attrs)


  def image(self, pos:Vec=None, size:VecOrNum=None, *, x:Num=None, y:Num=None, w:Num=None, h:Num=None, **attrs:Any) -> Image:
    'Create a child `defs` element.'
    return self.child(Image, pos=pos, size=size, x=x, y=y, w=w, h=h, **attrs)


  def line(self, a:Vec=None, b:Vec=None, *, x1:Num=None, y1:Num=None, x2:Num=None, y2:Num=None, **attrs:Any) -> Line:
    'Create a child `defs` element.'
    return self.child(Line, a=a, b=b, x1=x1, y1=y1, x2=x2, y2=y2, **attrs)


  def marker(self, *children:Any, id:str='', pos:Vec=None, size:VecOrNum=None, x:Num=None, y:Num=None, w:Num=None, h:Num=None,
   vx:Num=0, vy:Num=0, vw:Num=None, vh:Num=None, markerUnits='strokeWidth', orient:str='auto', **attrs:Any) -> 'Marker':
    'Create a child `marker` element.'
    return self.child(Marker, *children, id=id, pos=pos, size=size, x=x, y=y, w=w, h=h, vx=vx, vy=vy, vw=vw, vh=vh,
      markerUnits=markerUnits, orient=orient, **attrs)


  def path(self, commands:Iterable[PathCommand], **attrs:Any) -> Path:
    'Create a child `path` element.'
    return self.child(Path, commands=commands, **attrs)


  def polygon(self, points:Iterable[Vec], **attrs:Any) -> Polygon:
    return self.child(Polygon, points=points, **attrs)


  def polyline(self, points:Iterable[Vec], **attrs:Any) -> Polyline:
    return self.child(Polyline, points=points, **attrs)


  def rect(self, pos:Vec=None, size:VecOrNum=None, *, x:Num=None, y:Num=None, w:Num=None, h:Num=None, r:VecOrNum=None, **attrs:Any) -> Rect:
    return self.child(Rect, pos=pos, size=size, x=x, y=y, w=w, h=h, r=r, **attrs)


  def script(self, *text:str, **attrs,) -> Script:
    'Create a child `script` element.'
    return self.child(Script, *text, **attrs)


  def style(self, *text:str, **attrs,) -> Style:
    'Create a child `style` element.'
    return self.child(Style, *text, **attrs)


  def symbol(self, *children:Any, id:str, vx:Num=None, vy:Num=None, vw:Num=None, vh:Num=None, **attrs:Any) -> 'Symbol':
    'Create a child `symbol` element.'
    return self.child(Symbol, *children, id=id, vx=vx, vy=vy, vw=vw, vh=vh, **attrs)


  def text(self, *text:Any, pos:Vec=None, x:Num=None, y:Num=None, alignment_baseline:str=None, **attrs:Any) -> Text:
    'Create a child `text` element.'
    return self.child(Text, *text, pos=pos, x=x, y=y, alignment_baseline=alignment_baseline, **attrs)


  def use(self, id:str, pos:Vec=None, size:VecOrNum=None, *, x:Num=None, y:Num=None, w:Num=None, h:Num=None, **attrs:Any) -> Use:
    'Use a previously defined symbol'
    return self.child(Use, id=id, pos=pos, size=size, x=x, y=y, w=w, h=h, **attrs)


  # High level.

  def grid(self, pos:Vec=(0,0), size:VecOrNum=(256,256), *,
   step:VecOrNum=16, off:Vec=(0, 0), corner_radius:VecOrNum=None, **attrs:Any) -> 'G':
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
    g = self.g(**attrs)
    with g:
      for tick in NumRange(x_start, x_end, sx): g.line((tick, y), (tick, y_end)) # Vertical lines.
      for tick in NumRange(y_start, y_end, sy): g.line((x, tick), (x_end, tick)) # Horizontal lines.
      g.rect(class_=class_+'-border', x=x, y=y, w=w, h=h, r=corner_radius, fill='none')
    return g


  def plot(self, pos:Vec=(0,0), size:Vec=(512,1024), *,
   x:'PlotAxis'=None, y:'PlotAxis'=None,
   series:Sequence['PlotSeries']=(),
   title:str=None,
   title_h:Num=14,
   axis_label_h:Num=12,
   tick_h:Num=10,
   tick_len:Num=4,
   legend_pad:Num=8,
   legend_w:Num=128,
   legend_h:Num=16,
   corner_radius:VecOrNum=None,
   symmetric_xy=False,
   dbg=False,
   **attrs:Any) -> 'Plot':

    return self.child(Plot,
      pos=pos, size=size,
      x=x, y=y,
      series=series,
      title=title,
      title_h=title_h,
      axis_label_h=axis_label_h,
      tick_h=tick_h,
      tick_len=tick_len,
      legend_pad=legend_pad,
      legend_w=legend_w,
      legend_h=legend_h,
      corner_radius=corner_radius,
      symmetric_xy=symmetric_xy,
      dbg=dbg,
      **attrs)



class Svg(SvgBranch):
  '''
  Svg is an XmlWriter class that outputs SVG code.
  '''

  tag = 'svg'

  def __init__(self, pos:Vec=None, size:VecOrNum=None, *, x:Dim=None, y:Dim=None, w:Dim=None, h:Dim=None,
   vx:Num=0, vy:Num=0, vw:Num=None, vh:Num=None, _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
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
    kwargs = { # Put the xml nonsense up front.
      'xmlns': 'http://www.w3.org/2000/svg',
      'xmlns:xlink': 'http://www.w3.org/1999/xlink', # Safari does not yet support SVG 2.
      **kwargs
    }
    add_opt_attrs(kwargs, x=x, y=y, width=w, height=h, viewBox=self.viewBox)
    super().__init__(_counter=_counter, attrs=attrs, **kwargs)


# SVG branch elements.

class ClipPath(SvgBranch):
  tag = 'clipPath'

class Defs(SvgBranch):
  tag = 'defs'


class G(SvgBranch):
  tag = 'g'

  def __init__(self, *children:Any, transform:Iterable[str]='',
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    t:str = ''
    if isinstance(transform, str):
      t = transform
    else:
      t = ' '.join(transform)
    if t:
      kwargs['transform'] = t
    super().__init__(*children, _counter=_counter, attrs=attrs, **kwargs)


class Marker(SvgBranch):
  tag = 'marker'

  def __init__(self, *children:Any, id:str='', pos:Vec=None, size:VecOrNum=None, x:Num=None, y:Num=None, w:Num=None, h:Num=None,
   vx:Num=0, vy:Num=0, vw:Num=None, vh:Num=None, markerUnits='strokeWidth', orient:str='auto',
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    if not id: raise ValueError(f'Marker requires an `id` string')
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      w, h = unpack_VecOrNum(size)
    add_opt_attrs(kwargs, id=id, refX=fmt_num(x), refY=fmt_num(y), markerWidth=fmt_num(w), markerHeight=fmt_num(h),
      viewBox=fmt_viewBox(vx, vy, vw, vh), markerUnits=markerUnits, orient=orient)
    super().__init__(*children, _counter=_counter, attrs=attrs, **kwargs)


class Symbol(SvgBranch):
  tag = 'symbol'

  def __init__(self, *children:Any, id:str, vx:Num=None, vy:Num=None, vw:Num=None, vh:Num=None,
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    if vx is None: vx = 0
    if vy is None: vy = 0
    # TODO: figure out if no viewBox is legal and at all useful.
    assert vw >= 0 # type: ignore
    assert vh >= 0 # type: ignore
    add_opt_attrs(kwargs, id=id, viewBox=f'{vx} {vy} {vw} {vh}')
    super().__init__(*children, _counter=_counter, attrs=attrs, **kwargs)



# Plots.

Plotter = Callable[[G, PointTransform, Any], None]

def circle_plotter(r:Num=1, **attrs:Any) -> Plotter:
  attrs.setdefault('class_', 'series')
  def plotter(g:G, transform:PointTransform, point:Tuple) -> None:
    g.circle(transform(point), r=r, title=', '.join(str(f) for f in point))
  return plotter



class PlotSeries:

  name:str
  legend:str
  bounds:Optional[BoundsF2] = None # Overridden by subclasses.

  def render(self, plot:'Plot', series:G) -> None: raise NotImplementedError


class BarSeries(PlotSeries):

  def __init__(self, name:str, points:Iterable[Tuple], numeric:bool, legend:str='', width=1.0, plotter:Optional[Plotter]=None,
   title_fmt:Optional[Callable[[Tuple], str]]=None, **attrs:Any) -> None:

    self.name = name
    self.points = list(points)
    self.numeric = numeric
    self.legend = legend or name
    self.width = width
    self.plotter = plotter
    self.title_fmt = title_fmt
    attrs.setdefault('class_', name)
    self.attrs = attrs
    self.bounds:Optional[Tuple[F2, F2]] = None

    def float_from(val:Any, label:str) -> float:
      try: return float(val)
      except TypeError as e: raise TypeError(f'BarSeries received non-numeric point {label}: {val!r}') from e

    if self.points:
      for p in self.points:
        x = p[0]
        y = p[1]
        if numeric:
          x_min = x_max = float_from(x, 'key')
        y_min = y_max = float_from(y, 'value')
        break # Get first value, then iterate again.
      for p in self.points:
        x = p[0]
        y = p[1]
        if numeric:
          x = float_from(x, 'key')
          x_min = min(x_min, x)
          x_max = max(x_max, x)
        y = float_from(y, 'value')
        y_min = min(y_min, y)
        y_max = max(y_max, y)
      if numeric:
        half_w = self.width * 0.5
        self.bounds = ((x_min - half_w, 0.0), (x_max + half_w, y_max))
      else:
        self.bounds = ((0.0, 0.0), (float(len(self.points)), y_max))


  def render(self, plot:'Plot', series:G) -> None:
    assert self.plotter is None # TODO
    y0 = plot.y.transform(0)
    w = plot.x.scale * self.width
    # Do not place the bars in a group because we want to be able to z-index bars across multiple series.
    for i, p in enumerate(self.points):
      if not self.numeric:
        p = (i+0.5, p[1], p[0])
      (x_mid, y) = plot.transform(p)
      x_low = x_mid - w*0.5
      assert p[1] >= 0, f'negative bar values are not yet supported: {p!r}'
      kwargs:Dict[str,Any] = {}
      if self.title_fmt:
        kwargs['title'] = self.title_fmt(p)
      series.rect(x=x_low, y=y, w=w, h=y0-y, z_index=y, **kwargs, **self.attrs) # TODO: Custom format of title?


class XYSeries(PlotSeries):

  def __init__(self, name:str, points:Iterable[Tuple], legend:str='', plotter:Optional[Plotter]=circle_plotter(), **attrs:Any) -> None:
    self.name = name
    self.legend = legend or name
    self.points = list(points)
    self.plotter = plotter
    attrs.setdefault('class_', name)
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


  def render(self, plot:'Plot', series:G) -> None:
    # TODO: collect and return out-of-bounds points.
    assert self.plotter is not None
    with series.g(**self.attrs) as g:
      for p in self.points: self.plotter(g, plot.transform, p)



class LineSeries(XYSeries):

  def __init__(self, name:str, points:Iterable[Tuple], legend:str='', plotter:Plotter=None, use_segments=False, **attrs:Any) -> None:
    self.use_segments = use_segments
    super().__init__(name=name, points=points, legend=legend, plotter=plotter, **attrs)


  def render(self, plot:'Plot', series:G) -> None:
    with series.g(**self.attrs) as g:
      if self.use_segments:
        for (a, b) in window_pairs(plot.transform(p) for p in self.points):
          g.line(a, b)
      else:
        g.polyline(points=iter_unique(plot.transform(p) for p in self.points), fill='none')
        # TODO: option to fill polylines.
      if self.plotter is not None:
        for p in self.points: self.plotter(g, plot.transform, p)



class PlotAxis:

  def __init__(self, *,
   length:Num=0, # Screen length.
   min:Optional[Num]=None, max:Optional[Num]=None,
   visible_origin=False,
   symmetric=False,
   show_grid=True, grid:Iterable[Num]=(), grid_step:Num=0.0, grid_min:Num=16,
   show_ticks=True, ticks:Iterable[Num]=(), tick_step:Num=0.0, tick_space:Num=1,
   tick_w:Num=16, tick_fmt:Optional[TickFmt]=None) -> None:

    self.length = float(length) # For <=0 the screen length is calculated automatically.
    self._min = None if min is None else float(min)
    self._max = None if max is None else float(max)
    self.visible_origin = visible_origin
    self.symmetric = symmetric
    self.show_grid = show_grid
    self.grid = list(grid)
    self.grid_step = float(grid_step)
    self.grid_min = float(grid_min)
    self.show_ticks = show_ticks
    self.ticks = list(ticks)
    self.tick_step = float(tick_step)
    self.tick_space = float(tick_space)
    self.tick_w = float(tick_w)
    self.tick_fmt = tick_fmt

    # These attributes are filled in by Plot init.
    self.idx = -1
    self.data_len = 0.0
    self.min = 0.0
    self.max = 0.0
    self.partial_tick_len = 0.0
    self.transform = _axis_transform_dummy
    self.scale = 0.0

  def calc_min_max(self, data_bounds:Optional[BoundsF2]) -> None:
    # Determine data data_bounds.
    _min:Optional[float] = self._min
    _max:Optional[float] = self._max
    if _min is None: _min = 0.0   if data_bounds is None else data_bounds[0][self.idx]
    if _max is None: _max = _min if data_bounds is None else data_bounds[1][self.idx]
    if _max <= _min: _max = _min + 1.0
    if self.visible_origin:
      if _min > 0.0:   _min = 0.0
      elif _max < 0.0: _max = 0.0
    if self.symmetric:
      _max = max(_max, -_min)
      _min = -_max
    self.min = _min
    self.max = _max

  def calc_layout(self, plot_size:F2, title_h:float, tick_len:float, tick_h:float) -> None:
    assert self.length > 0
    self.data_len = self.max - self.min
    self.scale = self.length / self.data_len

    # Calculate tick step.
    tick_min_screen_step = (self.tick_w*1.5) if (self.idx == 0) else (tick_h*2.0)
    tick_mult = 1.0
    frac_w = 0
    fmt_w = 0
    if self.tick_step <= 0 and tick_min_screen_step > 0:
      step1, tick_mult = self.choose_step(tick_min_screen_step)
      self.tick_step = step1 * tick_mult
    if self.tick_step > 0 and not self.tick_fmt:
      exp = floor(log10(self.tick_step))
      frac_w = max(0, -exp)
      fmt_w = max(
        len(f'{self.min:,.{frac_w}f}'),
        len(f'{self.max:,.{frac_w}f}'))

      pad_str = f'{10**fmt_w:,.{frac_w}f}'[-fmt_w:] # Longer than necessary. Take pad chars from right to left.
      def tick_fmt(val:float) -> Any:
        s = f'{val:,.{frac_w}f}'
        return TSpan(pad_str[:-len(s)], class_='zpad'), s

      self.tick_fmt = tick_fmt

    # Calculate grid step.
    if self.grid_step <= 0:
      step1, mult = self.choose_step(min_screen_step=self.grid_min)
      if mult == 2 and tick_mult == 5: # Ticks will misalign to grid; bump grid to 2.5.
        mult = 2.5
      self.grid_step = step1 * mult

    if self.ticks:
      if not self.grid:
        self.grid = self.ticks
    else: # Calculate ticks.
      ti, tr = divmod(self.min, self.tick_step)
      if tr > 0.1: ti += 1 # If the remainder is visually significant, skip the first tick.
      t_start = ti*self.tick_step
      self.ticks = [t for t in NumRange(t_start, self.max, step=self.tick_step, closed=True)]
      if not self.grid: # Calculate grid.
        g_start = (self.min//self.grid_step + 1) * self.grid_step # Skip line index 0 because it is always <= low border.
        self.grid = [g for g in NumRange(g_start, self.max, self.grid_step)]



  def choose_step(self, min_screen_step:float) -> Tuple[float, float]:
    assert self.data_len > 0
    assert min_screen_step > 0
    cram_num = max(1.0, self.length // min_screen_step) # Maximum number of ticks that could be placed.
    assert cram_num > 0, (cram_num, self.length, min_screen_step)
    cram_step = self.data_len / cram_num # Minimum fractional data step.
    exp = floor(log10(cram_step))
    step1 = float(10**exp) # Low estimate of step.
    for mult in (1.0, 2.0, 5.0):
      step = step1 * mult
      if step >= cram_step: return step1, mult
    return step1, 10.0



class Plot(G):

  def __init__(self, *children:Any,
   pos:Vec=(0,0), size:Vec=(512,1024),
   x:PlotAxis=None, y:PlotAxis=None,
   series:Sequence[PlotSeries]=(),
   title:str=None,
   title_h:Num=14,
   axis_label_h:Num=12,
   tick_h:Num=10,
   tick_len:Num=4,
   legend_pad:Num=8,
   legend_w:Num=64,
   legend_h:Num=16,
   corner_radius:VecOrNum=None,
   symmetric_xy=False,
   dbg=False,
   _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs) -> None:

    attrs = attrs or {}
    pos = f2_for_vec(pos)
    # Initialize as `g` element.
    attrs.setdefault('class_', 'plot')
    super().__init__(*children, transform=translate(*pos), _counter=_counter, attrs=attrs, **kwargs)

    self.pos = pos
    self.size = size = f2_for_vec(size)
    self.x = x = PlotAxis() if x is None else x
    self.y = y = PlotAxis() if y is None else y
    self.series = series
    self.title = title
    self.title_h = title_h = max((0.0 if title is None else float(title_h)), float(tick_h))
    self.tick_len = tick_len = float(tick_len)
    self.axis_label_h = axis_label_h = float(axis_label_h)
    self.tick_h = tick_h = float(tick_h)
    self.legend_pad = float(legend_pad)
    self.legend_w = float(legend_w)
    self.legend_h = float(legend_h)
    self.corner_radius = corner_radius
    self.symmetric_xy = symmetric_xy
    self.w = size[0]
    self.h = size[1]

    x.idx = 0
    y.idx = 1
    x.partial_tick_len = tick_h
    y.partial_tick_len = x.tick_w

    data_bounds = reduce(expand_opt_bounds, (s.bounds for s in series), None)

    x.calc_min_max(data_bounds=data_bounds)
    y.calc_min_max(data_bounds=data_bounds)

    if symmetric_xy:
      x.min = min(x.min, y.min)
      y.min = x.min
      x.max = max(x.max, y.max)
      y.max = x.max

    # Calculate per-axis length as necessary.

    boundary_pad = 1 # Otherwise right/bottom can disappear.
    if x.length <= 0:
      y_total_tick_w = (tick_len + y.tick_space + y.tick_w) if y.show_ticks else 0.0
      x.length = size[0] - boundary_pad - max(x.tick_w, y_total_tick_w)
    if y.length <= 0:
      x_total_tick_h = (tick_len + x.tick_space + tick_h) if x.show_ticks else 0.0
      y.length = size[1] - boundary_pad - title_h - x_total_tick_h - (legend_pad+legend_h if legend_h else 0)

    x.calc_layout(plot_size=size, title_h=title_h, tick_len=tick_len, tick_h=tick_h)
    y.calc_layout(plot_size=size, title_h=title_h, tick_len=tick_len, tick_h=tick_h)

    self.data_size = data_size = (x.data_len, y.data_len)
    self.grid_size = grid_size = (x.length, y.length)
    self.scale = (x.scale, y.scale)

    assert x is not None
    assert y is not None
    ax = x # Hack around mypy.
    ay = y

    def transform(point:Sequence) -> F2:
      'Translate a point to appear coincident with the data space.'
      px = float(point[0])
      py = float(point[1])
      return (round(ax.scale*(px-ax.min), 1), round(ay.scale*(ay.data_len - (py-ay.min)), 1))

    def x_transform(val:Num) -> float: return round(ax.scale*(float(val) - ax.min), 1)
    def y_transform(val:Num) -> float: return round(ay.scale*(ay.data_len - (float(val)-ay.min)), 1)


    self.transform = transform
    x.transform = x_transform
    y.transform = y_transform

    if dbg:
      def dbg_rect(pos:Vec, size:Vec, stroke:str=None, fill:str=None, parent=self) -> None:
        parent.rect(pos, size, class_='DBG', stroke=stroke, fill=fill, opacity=0.2)
    else:
      def dbg_rect(pos:Vec, size:Vec, stroke:str=None, fill:str=None, parent=self) -> None: pass

    # Contents.
    self.style(
      _plot_style,
      f'text.title {{ font-size: {title_h}px; }}\n',
      f'text.axis-label {{ font-size: {axis_label_h}px; }}\n',
      f'text.tick {{ font-size: {tick_h}px; }}\n',
      f'tspan.zpad {{ opacity: 0; }}\n',
    )

    dbg_rect((0, 0), self.size, stroke='#000')

    # Title.
    dbg_rect((0, 0), (self.w, title_h), fill='#F00')

    if self.title is not None:
      self.text(self.title, pos=(0, 0), class_='title')

    with self.g(transform=translate(0, title_h)) as area:
      # Clip path is is defined to match grid.
      clip_path_id = area.gen_id()
      self.plot_clip_path = f'url(#{clip_path_id})'
      with area.clipPath(id=clip_path_id) as clipPath:
        clipPath.rect(size=grid_size, r=corner_radius)

      # Grid.
      # TODO: if we are really going to support rounded corners then the border rect should clip the interior lines.
      with area.g(class_='grid') as g:
        if x.show_grid:
          g_start_x = (x.min//x.grid_step + 1) * x.grid_step # Skip line index 0 because it is always <= low border.
          for gx in x.grid: # X axis.
            tgx = x.transform(gx)
            g.line((tgx, 0), (tgx, y.length)) # Vertical lines.
        if y.show_grid:
          g_start_y = (y.min//y.grid_step + 1) * y.grid_step # Skip line index 0 because it is always <= low border.
          for gy in y.grid:
            tgy = y.transform(gy)
            g.line((0, tgy), (x.length, tgy)) # Horizontal lines.
        g.rect(class_='grid-border', pos=(0,0), size=grid_size, r=corner_radius, fill='none')

      # Axes.
      if y.min <= 0 and y.max >= 0: # Draw X axis.
        y0 = y.transform(0)
        area.line((0, y0), (x.length, y0), class_='axis', id='x-axis')
      if x.min <= 0 and x.max >= 0: # Draw Y axis.
        x0 = x.transform(0)
        area.line((x0, 0), (x0, y.length), class_='axis', id='y-axis')

      def handle_rendered_tick(val:Any) -> Tuple:
        if isinstance(val, str): return (val,)
        try: return tuple(val)
        except TypeError: return (val,)

      # Ticks.
      if x.show_ticks:
        with area.g(class_='tick-x') as g:
          txi, txr = divmod(x.min, x.tick_step)
          if txr > 0.1: txi += 1 # If the remainder is visually significant, skip the first tick.
          t_start_x = txi*x.tick_step
          for _x in x.ticks:
            tx = x.transform(_x)
            ty = y.length
            tb = ty + tick_len
            tty = tb + x.tick_space
            g.line((tx, ty), (tx, tb), class_='tick')
            assert x.tick_fmt is not None
            dbg_rect((tx, tty), (x.tick_w, tick_h), fill='#008', parent=g)
            g.text(*handle_rendered_tick(x.tick_fmt(_x)), pos=(tx, tty), class_='tick')
      if y.show_ticks:
        with area.g(class_='tick-y') as g:
          tyi, tyr = divmod(y.min, y.tick_step)
          if tyr > 0.1: tyi += 1 # If the remainder is visually significant, skip the first tick.
          t_start_y = tyi*y.tick_step
          for _y in y.ticks:
            tx = x.length
            tr = tx + tick_len
            ttx = tr + y.tick_space
            ty = y.transform(_y)
            g.line((tx, ty), (tr, ty), class_='tick')
            assert y.tick_fmt is not None
            dbg_rect((ttx, ty-tick_h*0.75), (y.tick_w, tick_h), fill='#080', parent=g)
            g.text(*handle_rendered_tick(y.tick_fmt(_y)), pos=(ttx, ty), class_='tick')

      # Legend.
      leg_h = self.legend_h
      if leg_h > 0:
        leg_y = size[1] - title_h - self.legend_h - 1
        with area.g(class_='legend') as legend_g:
          for i, s in enumerate(series):
            with legend_g.g(id='legend-'+s.name) as g:
              leg_x = 1 + self.legend_w*i
              g.rect(pos=(leg_x, leg_y), size=(leg_h, leg_h))
              text_x = leg_x + leg_h * 1.25
              text_y = leg_y + leg_h * 0.5
              g.text(s.legend, pos=(text_x, text_y))

      # Series.
      with area.g(class_='series', clip_path=self.plot_clip_path) as series_g:
        for s in series:
          s.render(self, series=series_g)


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
g.legend rect {
  fill: none;
}
g.legend text {
  text-anchor: start;
  alignment-baseline: middle;
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
