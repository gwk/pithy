# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from operator import eq
from types import GenericAlias

from pithy.frozendicts import frozendict
from utest import utest, utest_exc, utest_repr, utest_type, utest_val, utest_val_type


# Construction.
utest_repr("frozendict({})", frozendict)
utest_repr("frozendict({'a': 1})", frozendict, {'a': 1})
utest_repr("frozendict({'a': 1})", frozendict, [('a', 1)])
utest_repr("frozendict({'a': 1})", frozendict, a=1)

# Kwargs-only construction type-checks as frozendict[str,V]; the utest calls above are dynamic and do not exercise the overloads.
_kwargs_only:frozendict[str,int] = frozendict(a=1)
utest_val(frozendict({'a': 1}), _kwargs_only, 'kwargs-only construction')

# Immutability: frozendict extends Mapping (not MutableMapping), so __setitem__ is absent.
utest_exc(AttributeError, lambda fd: fd.__setitem__('x', 0), frozendict({'a': 1}))

# Equality with frozendict.
utest(True, eq, frozendict({'a': 1}), frozendict({'a': 1}))
utest(False, eq, frozendict({'a': 1}), frozendict({'a': 2}))
utest(False, eq, frozendict({'a': 1}), frozendict({'b': 1}))

# Equality with plain dict (PEP 814 semantics).
utest(True, eq, frozendict({'a': 1}), {'a': 1})
utest(False, eq, frozendict({'a': 1}), {'a': 2})
utest(False, eq, frozendict({'a': 1}), {})

# Not equal to non-Mapping.
utest(False, eq, frozendict({'a': 1}), [('a', 1)])
utest(False, eq, frozendict(), None)

# Hashability.
utest_type(int, hash, frozendict())
utest_type(int, hash, frozendict({'a': 1}))

d_a1_b2 = {'a':1, 'b':2}
d_b2_a1 = {'b':2, 'a': 1}
fd_a1_b2 = frozendict(d_a1_b2)
fd_b2_a1 = frozendict(d_b2_a1)

utest(True, eq, fd_a1_b2, fd_b2_a1)
utest_val(hash(fd_a1_b2), hash(fd_b2_a1), 'equal frozendicts have equal hashes')

# Can be used as a dict key.
d = {fd_a1_b2: 'x'}
utest_val('x', d[fd_b2_a1], 'frozendict as dict key')

# len, iter, getitem.
utest(2, len, fd_a1_b2)
utest(['a', 'b'], list, fd_a1_b2)
utest(['b', 'a'], list, fd_b2_a1) # Order preservation.
utest(1, fd_a1_b2.__getitem__, 'a')
utest_exc(KeyError('z'), fd_a1_b2.__getitem__, 'z')

# get.
utest(1, fd_a1_b2.get, 'a')
utest(None, fd_a1_b2.get, 'z')
utest(99, fd_a1_b2.get, 'z', 99)

# keys, values, items.
utest(['a', 'b'], list, fd_a1_b2.keys())
utest([1, 2], list, fd_a1_b2.values())
utest([('a', 1), ('b', 2)], list, fd_a1_b2.items())

# copy.
utest_type(frozendict, fd_a1_b2.copy)
utest(fd_a1_b2, fd_a1_b2.copy)

# fromkeys.
utest(frozendict({'a': None, 'b': None}), frozendict.fromkeys, ['a', 'b'])
utest(frozendict({'a': 0, 'b': 0}), frozendict.fromkeys, ['a', 'b'], 0)

# __or__ (frozendict | dict and frozendict | frozendict → frozendict).
fd_a1 = frozendict({'a': 1})
fd_b2 = frozendict({'b': 2})
utest(frozendict({'a': 1, 'b': 2}), fd_a1.__or__, fd_b2)
utest(frozendict({'a': 1, 'b': 2}), fd_a1.__or__, {'b': 2})
# Right operand wins on collision.
utest(frozendict({'a': 99}), fd_a1.__or__, frozendict({'a': 99}))

# __ror__ (dict | frozendict → dict; frozendict | frozendict handled by __or__).
result = {'b': 2} | fd_a1
utest_val_type(dict, result, '__ror__ with dict returns dict')
utest({'a': 1, 'b': 2}, lambda: {'b': 2} | fd_a1)

# __reversed__.
utest(['b', 'a'], list, reversed(fd_a1_b2))

# __class_getitem__.
utest_val_type(GenericAlias, frozendict[str, int], '__class_getitem__')
