# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
HTML charts.

Terminology:
Categorical data can be nominal (unordered labels) or ordinal (ordered labels).
Numerical data can be discrete (integers) or continuous (floats).

An axis can be independent or dependent.
An axis can be categorical or numeric.
'''

import re
from math import ceil, floor, isclose, log10
from typing import Any, Callable, Iterable, Self

from ...markup import MuChildOrChildrenLax
from ...range import NumRange
from .. import Div, Figcaption, Figure, Span


Dim = int|float|str
Vec = tuple[float,float]
V2F = tuple[float,float]
V2FOrF = V2F|float
BoundsF2 = tuple[V2F,V2F]
PathCommand = tuple

PointTransform = Callable[[tuple], V2F]
TickFmt = Callable[[float], Any]
Plotter = Callable[[Div, PointTransform, Any], None]



class ChartSeries:
  '''
  Base class for chart series.
  A series represents a sequence of data elements and parameters for the desired visualization of those elements.
  '''

  def __init__(self, *, name:str, cl:str='', legend:str='', x:Any=0, y:Any=1, points:Iterable[Any],
   plotter:Plotter|None=None, attrs:dict[str,Any]|None=None) -> None:

    self.name = name
    self.cl = cl or clean_class_for_name(name)
    self.legend = legend or name
    self.x = x
    self.y = y
    self.points = list(points)
    self.plotter = plotter
    self.attrs = attrs
    self.kind_idx = 0
    self.kind_count = 1

    self.bounds = (
      self._compute_bounds(axis_key=self.x),
      self._compute_bounds(axis_key=self.y),
    )


  @property
  def kind_class(self) -> str: raise NotImplementedError # e.g. 'bar', 'line', 'scatter'.


  @property
  def is_categorical_x(self) -> bool:
    'Whether this kind of series requires a categorical x axis, regardless of the type of the x values.'
    return False


  def axis_values(self, axis_idx:int) -> list[Any]:
    'The raw point values for the given axis index, in point order.'
    return [p[self.x if axis_idx == 0 else self.y] for p in self.points]


  def _compute_bounds(self, axis_key:Any) -> tuple[bool,Any]:
    '''
    Returns (is_numeric, bounds).
    (True, (min, max)) if the axis is numeric.
    (False, set(labels)) if the axis is categorical/categorical.
    '''
    els = [p[axis_key] for p in self.points]
    if all(isinstance(e, (int, float)) for e in els):
      return (True, calc_min_max(els))
    else:
      labels = set()
      for el in els:
        if el in labels: raise ValueError(f'duplicate label: {el!r}')
        labels.add(el)
      return (False, els)


  def make_series_div(self, transform_x:Callable[[Any],Any], transform_y:Callable[[Any],Any]) -> Div:
    '''
    Creates the div for the series visualization.
    Subclasses should typically leave this as is and instead override `fill_vis_div`.
    '''
    div = Div(cl=('series', self.kind_class, self.cl))
    self.fill_vis_div(div=div, transform_x=transform_x, transform_y=transform_y)
    return div


  def make_legend_item_div(self) -> Div:
    '''
    Create the div for the series legend item.
    Subclasses should typically leave this as is and instead override `fill_legend_item_div`.
    '''
    div = Div(cl=('legend-item', self.kind_class, self.cl))
    self.fill_legend_item_div(div)
    return div


  def fill_vis_div(self, div:Div, transform_x:Callable[[Any],Any], transform_y:Callable[[Any],Any]) -> None:
    '''
    Fill the given div with the visual representation of the series.
    Subclasses must override this method.
    '''
    raise NotImplementedError


  def fill_legend_item_div(self, div:Div) -> None:
    '''
    Fill the given div with the legend representation of the series.
    Subclasses may override this method.
    The default implementation inserts a swatch div and the series legend content.
    '''
    div.extend(Div(cl='swatch'), self.legend)



class BarSeries(ChartSeries):
  '''
  A series that renders categorical data as a vertical bar chart.
  Multiple bar series will be interleaved to show a cluster of bars for each label/category.
  '''

  @property
  def kind_class(self) -> str: return 'bar'


  @property
  def is_categorical_x(self) -> bool: return True # Bars are always spaced evenly, one cluster per distinct x value.


  def fill_vis_div(self, div:Div, transform_x:Callable[[Any],Any], transform_y:Callable[[Any],Any]) -> None:
    '''
    Fill the series visualization div with html representing the data.
    '''
    for p in self.points:
      i = transform_x(p[self.x])
      v = transform_y(p[self.y])
      origin = transform_y(0)
      v_min = min(v, origin)
      v_size = abs(v - origin)
      style = f'--i:{i};--v-min:{v_min:.4f};--v-size:{v_size:.4f};--series-i:{self.kind_idx};--series-n:{self.kind_count};'
      div.append(Div(style=style))



class ChartAxis:
  '''
  Configuration for an axis of a chart. This is an abstract base class.
  Use CategoricalAxis, LinearAxis, LogarithmicAxis, etc to specify a customized axis.
  '''

  def __init__(self) -> None:
    self.idx = -1

  @property
  def data_class(self) -> str:
    '''
    I.e. 'categorical', 'numerical'.
    '''
    raise NotImplementedError


  @property
  def kind_class(self) -> str:
    '''
    I.e. 'linear', 'logarithmic'.
    '''
    raise NotImplementedError


  def transform(self, v:Any) -> float:
    '''
    Transform a value on this axis for visualization.
    '''
    raise NotImplementedError


  def configure(self, series:list['ChartSeries']) -> Self:
    '''
    Compute the bounds of the axis.
    '''
    raise NotImplementedError


  def style(self) -> str:
    return ''


  def tick_divs(self) -> list[Div]:
    '''
    Create divs for the axis ticks.
    '''
    raise NotImplementedError


  def grid_divs(self) -> list[Div]:
    'Create divs for grid lines associated with the axis.'
    return []



class CategoricalAxis(ChartAxis):
  '''
  An independent axis for categorical data.
  This axis type is used for a set of distinct labels, which will be spaced evenly.
  '''

  @property
  def data_class(self) -> str: return 'categorical'


  def __init__(self,
   labels:Iterable[Any]=(),
   label_sort_key:Callable[[Any],Any]|None=None):
    '''
    `labels`: a set of label values (typically str, int, date, datetime, or similar) that will be included in the categorical set.
    `label_sort_key`: a key function to use when sorting the label set.
    '''
    self.labels = list(labels)
    self.label_sort_key = label_sort_key
    super().__init__()


  @property
  def kind_class(self) -> str: return '' # No kind class for categorical axes.


  def transform(self, v:Any) -> float:
    'Categorical axis returns the index of the category label.'
    return self.labels.index(v)


  def configure(self, series:list['ChartSeries']) -> Self:
    '''
    Compute the bounds of the categorical axis.
    '''

    if self.label_sort_key is None: # Maintain the presented order of labels while deduplicating.
      labels_set = set()
      labels_list = []
      for label in self.labels:
        if label not in labels_set:
          labels_list.append(label)
          labels_set.add(label)
      for s in series:
        for label in s.axis_values(self.idx):
          if label not in labels_set:
            labels_list.append(label)
            labels_set.add(label)
      self.labels = labels_list

    else:
      labels_set = set(self.labels)
      for s in series:
        labels_set.update(s.axis_values(self.idx))
      self.labels = sorted(labels_set, key=self.label_sort_key)

    return self


  def style(self) -> str:
    d = 'x' if self.idx == 0 else 'y'
    lll = ''
    if self.idx == 0:
      last_len = len(str(self.labels[-1])) if self.labels else 0
      lll = f'--{d}-last-label-len:{last_len}ch;'
    return f'--n{d}:{len(self.labels)};{lll}'


  def tick_divs(self) -> list[Div]:
    return [
      Div(style=f'--i:{i}',  _=[Span(cl='tick'), Span(cl='label', _=str(label))])
     for (i, label) in enumerate(self.labels)]



class NumericalAxis(ChartAxis):
  '''
  An axis for quantative data. Both indepedent or dependent axes can be numerical.
  '''

  def __init__(self,
   show_origin:bool=False,
   symmetric:bool=False,
   min:float|None=None,
   max:float|None=None,
   show_grid:bool=True,
   grid:Iterable[float]=(),
   grid_step:float=0,
   show_ticks:bool=True,
   ticks:Iterable[float]=(),
   ticks_max:int=11,
   tick_step:float=0,
   tick_fmt:TickFmt|None=None,
  ) -> None:
    '''
    `tick_fmt` formats each tick value as a label.
    If None, a decimal format is chosen with just enough fractional digits to distinguish adjacent ticks.
    '''

    if ticks_max < 0: raise ValueError(f'ticks_max must be >= 0: {ticks_max!r}.')

    self.show_origin = show_origin
    self.symmetric = symmetric
    self._opt_min = None if min is None else float(min)
    self._opt_max = None if max is None else float(max)
    self.show_grid = show_grid
    self.grid = list(grid)
    self.grid_step = grid_step
    self.show_ticks = show_ticks
    self.ticks = list(ticks)
    self._ticks_are_explicit = bool(self.ticks)
    self.ticks_max = ticks_max
    self.tick_step = tick_step
    self.tick_fmt = tick_fmt
    self.scale = 1.0
    super().__init__()

  @property
  def data_class(self) -> str: return 'numerical'


  def calc_tick_fmt(self) -> TickFmt:
    '''
    Choose a tick format with enough fractional digits to distinguish adjacent ticks.
    Formatting fractional ticks as integers would produce duplicate labels.
    Call this only after the ticks have been filled in.
    '''
    if self.tick_fmt is not None: return self.tick_fmt
    if self._ticks_are_explicit: # Explicit ticks are arbitrary values, so show each one.
      frac_len = calc_frac_len(self.ticks)
    else: # Generated ticks are multiples of the step, so the step alone determines the precision.
      # The generated ticks themselves accumulate float error and would demand excess digits.
      frac_len = calc_frac_len([self.tick_step]) if self.tick_step > 0 else 0
    return lambda v: f'{v:,.{frac_len}f}'


  def configure(self, series:list['ChartSeries']) -> Self:
    min_, max_ = calc_min_max_of_ranges((s.bounds[self.idx][1] for s in series), min_=self._opt_min, max_=self._opt_max)

    if self.symmetric:
      max_ = max(max_, -min_)
      min_ = -max_
    elif self.show_origin:
      if min_ > 0.0: min_ = 0.0
      elif max_ < 0.0: max_ = 0.0

    if min_ == max_:
      if min_ == 0.0:
        min_ = 0.0 if self.show_origin and not self.symmetric else -1.0
        max_ = 1.0
      else:
        padding = abs(min_) * 0.5
        min_ -= padding
        max_ += padding

    self.min = min_
    self.max = max_
    self.scale = 1.0 / (max_ - min_)

    return self



class LinearAxis(NumericalAxis):
  '''
  An axis for quantative data.
  LinearAxis can be used for either indepedent or dependent axes.
  '''

  @property
  def kind_class(self) -> str: return 'linear'


  def transform(self, v:Any) -> float:
    assert isinstance(v, (int, float))
    return round((v - self.min) * self.scale, 4)


  def tick_divs(self) -> list[Div]:
    if not self.show_ticks: return []
    ticks = self.ticks
    if not ticks:
      self.fill_ticks()
    tick_fmt = self.calc_tick_fmt()
    return [
      Div(style=f'--v:{self.transform(v):.4f}', _=[Span(cl='tick'), Span(cl='label', _=str(tick_fmt(v)))])
     for v in ticks]


  def grid_divs(self) -> list[Div]:
    if not self.show_grid: return []
    grid = self.grid
    if not grid:
      if self.grid_step:
        grid.extend(NumRange(self.tick_min(self.grid_step), self.tick_max(self.grid_step), self.grid_step, closed=True))
      else:
        if not self.ticks: self.fill_ticks()
        grid.extend(self.ticks)
    return [Div(style=f'--v:{self.transform(v):.4f}') for v in grid]


  def tick_min(self, step:float) -> float:
    '''
    The tick cannot be less than min or else it would not be visible.
    '''
    return ceil(self.min / step) * step


  def tick_max(self, step:float) -> float:
    '''
    The tick cannot be greater than max or else it would not be visible.
    '''
    return floor(self.max / step) * step


  def fill_ticks(self) -> None:
    if self.ticks_max < 1:
      self.ticks = []
      return
    if not self.tick_step:
      self.choose_ticks_step()
    self.ticks.extend(NumRange(self.tick_min(self.tick_step), self.tick_max(self.tick_step), self.tick_step, closed=True))


  def choose_ticks_step(self) -> float:
    delta = self.max - self.min
    perfect_step = delta / self.ticks_max
    mag = 10 ** floor(log10(perfect_step))
    for scale in (1, 2, 5, 10):
      step:float = scale * mag
      min_ = self.tick_min(step)
      max_ = self.tick_max(step)
      count = floor((max_ - min_) / step) + 1
      if count <= self.ticks_max: break
    self.tick_step = step
    return step


def get_tick_div_label_len(div:Div) -> int:
  label_span = div._[1]
  assert isinstance(label_span, Span)
  label_text = label_span._[0]
  assert isinstance(label_text, str)
  return len(label_text)


def chart_figure(*,
 cl:Iterable[str]|None=None,
 title:MuChildOrChildrenLax=(),
 x:ChartAxis|None=None,
 y:ChartAxis|None=None,
 series:Iterable[ChartSeries]=(),
 symmetric_xy:bool=False,
 dbg:bool=False,
 **kw_attrs:Any) -> Figure:

  '''
  Generate a Figure that renders a pure HTML chart.
  `title` is an optional string subtree that is inserted into a <figcaption> element.
    `x` and `y` are optional ChartAxis objects that define the chart axes.
    `series` is a sequence of ChartSeries objects that define the chart data.
    `symmetric_xy` is a boolean that, if True, forces the x and y axes to have the same min and max values.
  '''

  series = list(series)

  is_x_numeric = all(s.bounds[0][0] for s in series)
  is_y_numeric = all(s.bounds[1][0] for s in series)

  if not is_x_numeric and any(s.bounds[0][0] for s in series): raise ValueError('x axis mixes categorical and numerical series')
  if not is_y_numeric and any(s.bounds[1][0] for s in series): raise ValueError('y axis mixes categorical and numerical series')

  # Some series kinds, e.g. bars, must always plotted against evenly spaced categories, even when the x values are numbers.
  is_x_categorical = any(s.is_categorical_x for s in series)

  if x is None: x = LinearAxis() if (is_x_numeric and not is_x_categorical) else CategoricalAxis()
  if y is None: y = LinearAxis() if is_y_numeric else CategoricalAxis()

  if isinstance(y, NumericalAxis) and any(isinstance(s, BarSeries) for s in series): y.show_origin = True

  x.idx = 0
  y.idx = 1

  x.configure(series=series)
  y.configure(series=series)

  series_by_kind:dict[str,list[ChartSeries]] = {}
  for s in series: series_by_kind.setdefault(s.kind_class, []).append(s)
  for kind_series in series_by_kind.values():
    for i, s in enumerate(kind_series):
      s.kind_idx = i
      s.kind_count = len(kind_series)

  if symmetric_xy:
    if isinstance(x, NumericalAxis) and isinstance(y, NumericalAxis):
      x.min = y.min = min(x.min, y.min)
      x.max = y.max = max(x.max, y.max)
      x.scale = y.scale = 1.0 / (x.max - x.min)
    else: raise ValueError('cannot force symmetric axes for categorical data')

  x_tick_divs = x.tick_divs()
  y_tick_divs = y.tick_divs()

  max_tick_x_label_len = max((get_tick_div_label_len(d) for d in x_tick_divs), default=0)

  data_class = f'{x.data_class}-{y.data_class}'
  _cl = [data_class]
  if isinstance(cl, str): _cl.append(cl)
  elif cl is not None: _cl.extend(cl)
  attrs_style = kw_attrs.pop('style', '')
  style = f'{x.style()}{y.style()}{attrs_style}'

  chart = Figure(cl=_cl, style=style, **kw_attrs)
  chart.prepend_class('chart')

  if title is not None: chart.append(Figcaption(_=title))

  row = chart.append(Div(cl='vis-row',
    style=f'--max-tick-x-label-len:{max_tick_x_label_len}ch; --tick-y-count:{len(y_tick_divs)}'))

  legend = chart.append(Div(cl='legend'))

  gutter_left = row.append(Div(cl='gutter-left'))

  gutter_left.append(Div(cl='origin')) # Empty box.

  gutter_left.append(Div(cl=['ticks', 'y', y.data_class, y.kind_class], _=y_tick_divs))
  for d in y_tick_divs: d._.reverse() # Flip the tick and label so that the tick is on the right.

  vis_wrap = row.append(Div(cl='vis-wrap'))
  vis_scroll = vis_wrap.append(Div(cl='vis-scroll'))

  vis_scroll.append(Div(cl=['ticks', 'x', x.data_class, x.kind_class], _=x_tick_divs))

  vis = vis_scroll.append(Div(cl='vis', _=[
    Div(cl=['grid', 'x'], _=x.grid_divs()),
    Div(cl=['grid', 'y'], _=y.grid_divs()),
    *[s.make_series_div(transform_x=x.transform, transform_y=y.transform) for s in series],
  ]))

  if dbg:
    vis.extend([
      Div(cl='dbg packed-bar-step'),
      Div(cl='dbg bar-step')])

  legend._ = [s.make_legend_item_div() for s in series]

  return chart


def clean_class_for_name(name:str) -> str:
  'Return a class name that is valid in HTML.'
  cl = re.sub(r'[^-_\w]+', '_', name)
  if cl[0].isdigit(): cl = f'_{cl}'
  return cl


def calc_frac_len(values:Iterable[float], max_frac_len:int=12, rel_tol:float=1e-9) -> int:
  '''
  The fewest fractional digits that render every value in `values` without visible loss of precision.
  The comparison is relative so that float representation error, e.g. 0.30000000000000004, does not demand excess digits.
  Values that still do not match within `max_frac_len` digits, e.g. one third, are truncated to that limit.
  '''
  frac_len = 0
  for v in values:
    while frac_len < max_frac_len and not isclose(float(f'{v:.{frac_len}f}'), v, rel_tol=rel_tol): frac_len += 1
  return frac_len


def calc_min_max(values:list[Any]) -> V2F|None:
  it = iter(values)
  try: v0 = next(it)
  except StopIteration: return None
  min_ = max_ = v0
  for v in it:
    if min_ > v: min_ = v
    if max_ < v: max_ = v
  return (min_, max_)


def calc_min_max_keyed(points:list[Any], key:Any) -> V2F|None:
  it = iter(points)
  try: p0 = next(it)
  except StopIteration: return None
  min_ = max_ = p0[key]
  for p in it:
    v = p[key]
    if min_ > v: min_ = v
    if max_ < v: max_ = v
  return (min_, max_)


def calc_min_max_of_ranges(ranges:Iterable[V2F|None], min_:float|None=None, max_:float|None=None) -> V2F:
  for r in ranges:
    if r is None: continue
    r_min_, r_max_ = r
    if min_ is None or min_ > r_min_: min_ = r_min_
    if max_ is None or max_ < r_max_: max_ = r_max_
  if min_ is None:
    assert max_ is None
    return (0, 1)
  assert max_ is not None
  return (min_, max_)
