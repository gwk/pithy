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
from functools import reduce
from math import floor, log10
from typing import Any, Callable, ClassVar, Iterable, Union, TypeVar

from ...range import Num, NumRange
from .. import Div, Figcaption, Figure, InlineStyle, Span, MuChildOrChildrenLax


Dim = int|float|str
Vec = tuple[Num,Num]
V2F = tuple[float,float]
V2FOrF = Union[V2F,float]
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

    self.bounds = (
      self._compute_bounds(axis_key=self.x),
      self._compute_bounds(axis_key=self.y),
    )


  @property
  def data_class(self) -> str:
    cx = 'numerical' if self.bounds[0][0] else 'categorical'
    cy = 'numerical' if self.bounds[1][0] else 'categorical'
    return f'{cx}-{cy}'


  @property
  def kind_class(self) -> str: raise NotImplementedError # e.g. 'bar', 'line', 'scatter'.


  def _compute_bounds(self, axis_key:Any) -> Any:
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


  def make_vis_div(self, transform_x:Callable[[Any],Any], transform_y:Callable[[Any],Any]) -> Div:
    '''
    Creates the div for the series visualization.
    Subclasses should typically leave this as is and instead override `fill_vis_div`.
    '''
    div = Div(cl=('series', self.data_class, self.kind_class, self.cl))
    self.fill_vis_div(div=div, transform_x=transform_x, transform_y=transform_y)
    return div


  def make_legend_item_div(self) -> Div:
    '''
    Create the div for the series legend item.
    Subclasses should typically leave this as is and instead override `fill_legend_item_div`.
    '''
    div = Div(cl=('legend-item', self.data_class, self.kind_class, self.cl))
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


  def fill_vis_div(self, div:Div, transform_x:Callable[[Any],Any], transform_y:Callable[[Any],Any]) -> None:
    '''
    Fill the series visualization div with html representing the data.
    '''
    for p in self.points:
      match (transform_x(p[self.x]), transform_y(p[self.y])):
        case (vx, vy):
          style = f'--vx:{vx};--vy:{vy};'
        case (vx, None):
          style = f'--vx:{vx};'
        case (None, vy):
          style = f'--vy:{vy};'
        case (None, None):
          style = ''

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


  def transform(self, v:Any) -> Any:
    '''
    Transform a value on this axis for visualization.
    '''
    raise NotImplementedError


  def configure(self, series:list['ChartSeries']) -> None:
    '''
    Compute the bounds of the axis.
    '''
    raise NotImplementedError


  def tick_divs(self) -> list[Div]:
    '''
    Create divs for the axis ticks.
    '''
    raise NotImplementedError



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


  def transform(self, v:Any) -> Any:
    return self.labels.index(v)


  def configure(self, series:list['ChartSeries']) -> None:
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
        series_labels = s.bounds[self.idx][1]
        assert isinstance(series_labels, list)
        for label in series_labels:
          if label not in labels_set:
            labels_list.append(label)
            labels_set.add(label)
      self.labels = labels_list
    else:
      labels_set = set(self.labels)
      for s in series:
        series_labels = s.bounds[self.idx][1]
        assert isinstance(series_labels, list)
        labels_set.update(series_labels)
      self.labels = sorted(labels_set, key=self.label_sort_key)


  def tick_divs(self) -> list[Div]:
    return [Div(cl='tick', ch=str(label)) for label in self.labels]



class NumericalAxis(ChartAxis):
  '''
  An axis for quantative data. Both indepedent or dependent axes can be numerical.
  '''

  def __init__(self,
   visible_origin=False,
   symmetric=False,
   min:Num|None=None,
   max:Num|None=None,
   show_grid=True,
   grid:Iterable[Num]=(),
   grid_step:Num=0,
   show_ticks=True,
   ticks:Iterable[Num]=(),
   tick_count=8,
   tick_step:Num=0,
   tick_fmt:TickFmt=str,
  ) -> None:

    self.visible_origin = visible_origin
    self.symmetric = symmetric
    self._opt_min = None if min is None else float(min)
    self._opt_max = None if max is None else float(max)
    self.show_grid = show_grid
    self.grid = list(grid)
    self.grid_step = grid_step
    self.show_ticks = show_ticks
    self.ticks = list(ticks)
    self.tick_count = tick_count
    self.tick_step = tick_step
    self.tick_fmt = tick_fmt
    self.min = 0.0
    self.max = 1.0
    self.scale = 1.0
    super().__init__()

  @property
  def data_class(self) -> str: return 'numerical'


  def configure(self, series:list['ChartSeries']) -> None:
    min_, max_ = calc_min_max_of_ranges((s.bounds[self.idx][1] for s in series), min_=self._opt_min, max_=self._opt_max)

    if self.symmetric:
      max_ = max(max_, -min_)
      min_ = -max_
    elif self.visible_origin:
      if min_ > 0.0: min_ = 0.0
      elif max_ < 0.0: max_ = 0.0

    self.min = min_
    self.max = max_
    self.scale = 1.0 / (max_ - min_)



class LinearAxis(NumericalAxis):
  '''
  An axis for quantative data.
  LinearAxis can be used for either indepedent or dependent axes.
  '''

  @property
  def kind_class(self) -> str: return 'linear'


  def configure(self, series:list['ChartSeries']) -> None:
    super().configure(series)


  def transform(self, v:Any) -> Any:
    return round((v - self.min) * self.scale, 4)


  def tick_divs(self) -> list[Div]:
    ticks = self.ticks
    if not ticks:
      if not self.tick_step:
        if self.tick_count < 2: raise ValueError('tick_count must be at least 2')
        self.tick_step = (self.max - self.min) / self.tick_count
      ticks.extend(NumRange(self.min, self.max, self.tick_step, closed=True))
    return [Div(style=f'--v:{self.transform(v)}', ch=Div(ch=str(self.tick_fmt(v)))) for v in ticks]




def chart_figure(*,
 cl:Iterable[str]|None=None,
 title:MuChildOrChildrenLax=(),
 x:ChartAxis|None=None,
 y:ChartAxis|None=None,
 series:Iterable[ChartSeries]=(),
 symmetric_xy=False,
 dbg=False,
 **kw_attrs:Any) -> Figure:

  '''
  Generate a Figure that renders a pure HTML chart.
  `title` is an optional string subtree that is inserted into a <figcaption> element.
    `x` and `y` are optional ChartAxis objects that define the chart axes.
    `series` is a sequence of ChartSeries objects that define the chart data.
    `symmetric_xy` is a boolean that, if True, forces the x and y axes to have the same min and max values.
  '''

  series = list(series)

  data_class = ''

  is_x_numeric = all(s.bounds[0][0] for s in series)
  is_y_numeric = all(s.bounds[1][0] for s in series)

  if not is_x_numeric and any(s.bounds[0][0] for s in series): raise ValueError('x axis mixes categorical and numerical series')
  if not is_y_numeric and any(s.bounds[1][0] for s in series): raise ValueError('y axis mixes categorical and numerical series')

  if x is None: x = LinearAxis() if is_x_numeric else CategoricalAxis()
  if y is None: y = LinearAxis() if is_y_numeric else CategoricalAxis()

  x.idx = 0
  y.idx = 1

  x.configure(series=series)
  y.configure(series=series)

  if symmetric_xy:
    if isinstance(x, NumericalAxis) and isinstance(y, NumericalAxis):
      x.min = min(x.min, y.min)
      y.min = x.min
      x.max = max(x.max, y.max)
      y.max = x.max
    else: raise ValueError('cannot force symmetric axes for categorical data')

  chart = Figure(cl=cl, attrs=kw_attrs)
  chart.prepend_class('chart')

  if title is not None: chart.append(Figcaption(ch=title))

  grid = chart.append(Div(cl='vis-grid'))
  legend = chart.append(Div(cl='legend'))

  grid.append(Div(cl='origin')) # By default this box is empty.
  grid.append(Div(cl=['ticks-x', x.data_class, x.kind_class], ch=x.tick_divs()))
  grid.append(Div(cl=['ticks-y', y.data_class, y.kind_class], ch=y.tick_divs()))
  print(x, x.kind_class)
  print(y, y.kind_class)
  grid.append(Div(cl='vis', ch=[s.make_vis_div(transform_x=x.transform, transform_y=y.transform) for s in series]))

  legend.ch = [s.make_legend_item_div() for s in series]

  return chart



def clean_class_for_name(name:str) -> str:
  'Return a class name that is valid in HTML.'
  cl = re.sub(r'[^-_\w]+', '_', name)
  if cl[0].isdigit(): cl = f'_{cl}'
  return cl


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
  return (min_, max_)



chart_style = '''
/* Chart layout. */
figure.chart {
}
figure.chart > figcaption {
}
figure.chart > div.legend {
}
figure.chart > div.vis-grid {
  /* This CSS grid allocates minimum space for the gutter/tick areas,
  and devotes the remaining space to the data visualization area. */
  display: grid;
  grid-template-columns: min-content auto; /* Left gutter, vis. */
  grid-template-rows: auto min-content; /* vis, bottom gutter. */
  grid-column-gap: 0px;
  grid-row-gap: 0px;
}
figure.chart div.ticks-y { /* The y-axis tick marks on the left. */
  grid-area: 1 / 1 / 2 / 2; /* row-start / column-start / row-end / column-end */
}
figure.chart div.vis { /* The data visualization area. */
  grid-area: 1 / 2 / 2 / 3;
}
figure.chart div.origin { /* The small square at the origin. */
  grid-area: 2 / 1 / 3 / 2;
}
figure.chart div.ticks-x { /* The x-axis tick marks on the bottom. */
  grid-area: 2 / 2 / 3 / 3;
}

figure.chart div.ticks-x.categorical {
  display: flex;
}
figure.chart div.ticks-x.categorical > div { /* These rules kep the bars from collapsing. */
  flex-grow: 1;
  flex-shrink: 1;
}
figure.chart div.ticks-x.numerical {
  /* TODO. */
}

figure.chart div.ticks-y > div {
}
figure.chart div.ticks-y.categorical {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
figure.chart div.ticks-y.categorical > div {
  /* TODO. */
}
figure.chart div.ticks-y.numerical > div {
  /* This is tricky:
  we use relative positioning so that the tick elements participate in document layout
  and influence the width of the gutter.
  The zero height lets us use the CSS variable to position the tick mark itself. */
  position: relative;
  height: 0px;
  top: calc(100% * calc(1 - var(--v)));
}
figure.chart div.ticks-y.numerical > div > div {
  /* We are obliged to use a child div to hold the text.
  Because the parent div has zero height, the text hangs below the specified vertical position.
  The child div allows us to transform the text and center it around the specified position. */
  transform: translateY(-50%);
}
figure.chart div.ticks-y.numerical > div > div::after {
  /* This ::after element is used to render the tick mark. */
  content: '\\a0'; /* A nonbreaking space to prevent the div from collapsing. */
  clip-path: polygon(0 calc(50% - 0.5px), 0 calc(50% + 0.5px), 100% calc(50% + 0.5px), 100% calc(50% - 0.5px));
}

figure.chart div.vis { /* The data visualization area. */
  position: relative;
  overflow: hidden;
}
figure.chart div.vis > div.series {
  position: absolute;
  display: flex;
  flex-direction: row;
  align-items: flex-end;
  width: 100%;
  height: 100%;
}
figure.chart div.vis > div.series > div {
  flex: 1 1 auto;
  height: calc(100% * calc(var(--vy)));
  background-color: var(--series-color);
}
div.swatch {
  display: inline-block;
  background-color: var(--series-color);
}

/* User style. */
figure.chart {
  width: 96%;
  margin: 0 auto;
  background-color: red;
  --series-color: gray; /* Default, can be overridden per series. */
}
figure.chart > figcaption {
  padding: 0.5em 0;
  background-color: #8D6;
}
figure.chart > div.legend {
  padding: 0.5em 0;
  background-color: lightgray;
}
figure.chart div.vis-grid {
  background-color: yellow;
}
figure.chart div.origin {
  background-color: #DDF;
}
figure.chart div.vis {
  height: 24em;
}
figure.chart div.ticks-x {
  background-color: lightgreen;
}
figure.chart div.ticks-x.categorical {
  text-align: center;
}
figure.chart div.ticks-y {
  background-color: #8DD;
}
figure.chart div.ticks-y > div {
  text-align: right;
}
figure.chart div.ticks-y.numerical > div > div::after {
  /* This ::after element is used to render the tick mark. */
  width: 0.25em;
  background-color: black;
}
figure.chart div.series {
  column-gap: 4px;
}
figure.chart .Series0 {
  --series-color: coral;
}
figure.chart .Series1 {
  --series-color: lightblue;
}
div.swatch {
  width: 1em;
  height: 1em;
  margin-right: 0.5em;
  vertical-align: middle;
  border-radius: 0.25em;
}
'''