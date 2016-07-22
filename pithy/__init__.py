# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter, defaultdict, namedtuple
from enum import Enum
from functools import lru_cache, partial, partialmethod, reduce, singledispatch
from itertools import chain, dropwhile, filterfalse, groupby, islice, repeat, takewhile, tee, zip_longest
from sys import argv, stderr, stdout

from .dicts import *
from .fs import *
from .immutable import *
from .io import *
from .seq import *
from .strings import *
from .task import *
from .transform import *
from .type_util import *
from .util import *
