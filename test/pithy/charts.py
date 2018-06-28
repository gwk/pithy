from sys import stdout
from pithy.charts import *


chart = XYChart(
  ('A', [(-20,0), (100,-100), (120,400)]),
  ('B', [(0,0), (50,300)]),
  ('C', [(0,1), (140,350)]),
  ('D', [(40,1), (89,60)]),
  ('E', [(50,1), (175,79)]), w=1000, h=600, title_height=20, label_height=10, label_width=40, legend_width=40,
  title='Test Chart', x_label='x axis', y_label='y axis', numb_y_labels=4
)

chart.render(file=stdout)
