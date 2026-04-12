# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.vec import V
from pithy.vec.line import intersect_lines, project_point_onto_line
from utest import utest


utest(V(0,0), intersect_lines, (V(0,0), V(1,0)), (V(0,0), V(0,1)))
utest(V(0,0), intersect_lines, (V(0,0), V(1,0)), (V(0,0), V(0,1)))

utest(V(0,0), intersect_lines, (V(1,2), V(2,4)), (V(2,-1), V(4,-2)))

utest(V(0,0), project_point_onto_line, V(0,0), V(0,0), V(1,0))
utest(V(0,0), project_point_onto_line, V(0,1), V(-1,0), V(1,0))
utest(V(1,1), project_point_onto_line, V(2,0), V(0,0), V(2,2))
utest(V(4,3), project_point_onto_line, V(2,7), V(6,4), V(2,2))
