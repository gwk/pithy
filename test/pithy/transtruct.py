#!/usr/bin/env python3

from collections import Counter, defaultdict, namedtuple
from dataclasses import dataclass
from typing import NamedTuple

from pithy.io import outM
from pithy.transtruct import *
from utest import *


ttor = Transtructor()

# Primitive types.

utest(1, ttor.transtruct, object, 1) # object passes any value through.


@dataclass
class DC1:
  a:int
  b:str

class NT1(NamedTuple):
  a:int
  b:str

NTU1 = namedtuple('NTU1', 'a b') # Untyped namedtuple.


dc1 = DC1(1, 'a')
nt1 = NT1(1, 'a')
ntu1 = NTU1(1, 'a')


utest(dc1, ttor.transtruct, DC1, nt1)
utest(dc1, ttor.transtruct, DC1, ntu1)

utest(nt1, ttor.transtruct, NT1, dc1)
utest(nt1, ttor.transtruct, NT1, ntu1)

utest(ntu1, ttor.transtruct, NTU1, dc1)
utest(ntu1, ttor.transtruct, NTU1, nt1)


utest([dc1], ttor.transtruct, list[DC1], [nt1])
utest([dc1], ttor.transtruct, list[DC1], [ntu1])

utest([nt1], ttor.transtruct, list[NT1], [dc1])
utest([nt1], ttor.transtruct, list[NT1], [ntu1])

utest([ntu1], ttor.transtruct, list[NTU1], [dc1])
utest([ntu1], ttor.transtruct, list[NTU1], [nt1])

utest({'a':1}, ttor.transtruct, dict[str,int], Counter({'a':1}))
utest({'a':1}, ttor.transtruct, dict[str,int], defaultdict(lambda: 0, {'a':1}))

utest(Counter({'a':1}), ttor.transtruct, Counter[str], {'a':'1'})
