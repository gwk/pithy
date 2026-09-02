# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from copy import replace
from typing import Any

from pithy.markup import Mu, TagMu
from utest import utest, utest_exc, utest_run


utest(Mu(), Mu)

utest(TagMu(tag='div'), TagMu, tag='div')

utest(Mu(_=['x', 'y'], attrs_by_ref={'a': 'a1'}), Mu, 'x', 'y', a='a1')
utest_exc(ValueError('Positional children and `_` are mutually exclusive.'), Mu, 'a', _=[])

def mu_with_normalized_attr_collision() -> Mu:
  attrs:dict[str,Any] = {'some_attr':'#a', 'some-attr':'#b'}
  return Mu(**attrs)

utest_exc(ValueError("Keyword attributes 'some_attr' and 'some-attr' both normalize to 'some-attr'."),
  mu_with_normalized_attr_collision)


@utest_run
def attrs_by_ref() -> None:
  attrs = {'a':'a1'}

  direct = Mu(attrs_by_ref=attrs)
  assert direct.attrs is attrs
  utest_exc(ValueError('`attrs_by_ref` cannot be combined with keyword attributes or `cl`.'), Mu, attrs_by_ref=attrs, a='a2')
  utest_exc(ValueError('`attrs_by_ref` cannot be combined with keyword attributes or `cl`.'), Mu, attrs_by_ref=attrs, cl='c')


@utest_run
def children_by_ref() -> None:
  children = ['a', 'b']
  node = Mu(_=children)
  assert node._ is children

utest(TagMu(tag='r'), replace, TagMu(tag='o'), tag='r')
utest(Mu(cl='r'), replace, Mu(cl='o'), cl='r')

utest(Mu(_=['x']), replace, Mu(_=['a', 'b']), _=['x'])

utest(Mu(a='a2', b='b'), replace, Mu(a='a1', b='b'), a='a2')
