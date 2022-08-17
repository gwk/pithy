# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Iterable, Iterator, Protocol, Sized, runtime_checkable, TypeVar

_El = TypeVar('_El', covariant=True)


@runtime_checkable
class SizedIterable(Sized, Iterable[_El], Protocol):
  '''
  A protocol for iterables that also have a length.
  '''


def iter_pairs_of_el_is_last(sized_iterable:SizedIterable[_El]) -> Iterator[tuple[_El, bool]]:
  last = len(sized_iterable) - 1
  return ((el, i==last) for i, el in enumerate(sized_iterable))
