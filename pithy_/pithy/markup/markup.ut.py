# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from copy import replace
from typing import Any

from pithy.markup import Mu, normalize_attr_key, TagMu, xml_pred
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

utest('for', normalize_attr_key, 'for_')
utest('hx-get', normalize_attr_key, 'hx_get')
utest('data-x', normalize_attr_key, 'data_x_')
utest('a--', normalize_attr_key, 'a__')
utest({'for': 'x', 'hx-get': '/y'}, lambda: Mu(for_='x', hx_get='/y').attrs)
utest(True, lambda: xml_pred(attrs={'for_': 'x'})(Mu(for_='x')))

@utest_run
def update_normalizes_keys() -> None:
  mu = Mu()
  mu.update(for_='x')
  utest({'for': 'x'}, lambda: mu.attrs)


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
