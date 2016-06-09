# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter, defaultdict, namedtuple
from enum import Enum
from functools import singledispatch
from sys import argv, stderr, stdout

from .fs import *
from .io import *
from .seq import *
from .task import *
from .transform import *
from .type_util import *
from .util import *
