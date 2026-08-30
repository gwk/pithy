# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from datetime import date

from pithy.web.routetree import RouteComponentPattern, RouteTree
from utest import utest, utest_exc, utest_run, utest_run_exc


@utest_run
def _() -> None:
  'RouteComponentPattern.parse.'

  def parse_attrs(text:str) -> tuple:
    p = RouteComponentPattern.parse(text)
    return (p.name, p.kind, p.is_opt, p.prefix, p.suffix)

  utest(('name', 'str', False, '', ''), parse_attrs, '{name}')
  utest(('n', 'nat', False, '', ''), parse_attrs, '{n:nat}')
  utest(('id', 'pos_int', False, '', ''), parse_attrs, '{id:pos_int}')
  utest(('id', 'int', False, '', ''), parse_attrs, '{id:int}')
  utest(('h', 'hex', False, '', ''), parse_attrs, '{h:hex}')
  utest(('d', 'date', False, '', ''), parse_attrs, '{d:date}')
  utest(('p', 'path', False, '', ''), parse_attrs, '{p:path}')
  utest(('name', 'str', True, '', ''), parse_attrs, '{name:str?}')
  utest(('id', 'int', False, 'item-', ''), parse_attrs, 'item-{id:int}')
  utest(('id', 'int', False, '', '-details'), parse_attrs, '{id:int}-details')
  utest(('id', 'int', False, 'item-', '-details'), parse_attrs, 'item-{id:int}-details')

  utest_exc(ValueError, RouteComponentPattern.parse, '{name:}')
  utest_exc(ValueError, RouteComponentPattern.parse, '{name:bogus}')


@utest_run
def _() -> None:
  'RouteComponentPattern.match.'

  def match_comp(pattern_text:str, *components:str) -> object:
    'Parse a pattern and match it against the given components at index 0.'
    p = RouteComponentPattern.parse(pattern_text)
    return p.match(list(components), 0)

  # nat.
  utest(0, match_comp, '{n:nat}', '0')
  utest(42, match_comp, '{n:nat}', '42')
  utest(None, match_comp, '{n:nat}', '-1')
  utest(None, match_comp, '{n:nat}', 'abc')

  # pos_int.
  utest(1, match_comp, '{id:pos_int}', '1')
  utest(42, match_comp, '{id:pos_int}', '42')
  utest(None, match_comp, '{id:pos_int}', '0')
  utest(None, match_comp, '{id:pos_int}', '-1')
  utest(None, match_comp, '{id:pos_int}', 'abc')

  # int.
  utest(42, match_comp, '{id:int}', '42')
  utest(-1, match_comp, '{id:int}', '-1')
  utest(None, match_comp, '{id:int}', 'abc')

  # hex.
  utest('0123456789ABCDEFabcdef', match_comp, '{h:hex}', '0123456789ABCDEFabcdef')
  utest(None, match_comp, '{h:hex}', 'xyz')

  # date.
  utest(date(2024, 1, 15), match_comp, '{d:date}', '2024-01-15')
  utest(None, match_comp, '{d:date}', 'not-a-date')

  # str.
  utest('hello', match_comp, '{s}', 'hello')
  utest('anything-goes', match_comp, '{s}', 'anything-goes')

  # Prefix and suffix.
  utest(42, match_comp, 'item-{id:int}', 'item-42')
  utest(None, match_comp, 'item-{id:int}', '42')
  utest(None, match_comp, 'item-{id:int}', 'other-42')
  utest(42, match_comp, '{id:int}-details', '42-details')
  utest(None, match_comp, '{id:int}-details', '42')

  # path kind: consumes all remaining components.
  def match_path(pattern_text:str, components:list[str], idx:int=0) -> object:
    p = RouteComponentPattern.parse(pattern_text)
    return p.match(components, idx)

  utest('a/b/c.txt', match_path, '{p:path}', ['a', 'b', 'c.txt'], 0)
  utest('b/c.txt', match_path, '{p:path}', ['a', 'b', 'c.txt'], 1)


@utest_run
def _() -> None:
  'RouteTree: basic insertion and lookup.'
  tree:RouteTree[str] = RouteTree()
  tree.insert('/users', 'users')
  tree.insert('/users/{id:int}', 'user')
  tree.insert('/users/{id:int}/posts', 'user_posts')
  tree.finalize()

  utest(('users', {}), tree.get, '/users')
  utest(('user', {'id': 42}), tree.get, '/users/42')
  utest(('user', {'id': -1}), tree.get, '/users/-1')
  utest(('user_posts', {'id': 42}), tree.get, '/users/42/posts')
  utest(None, tree.get, '/users/abc') # int pattern doesn't match.
  utest(None, tree.get, '/nonexistent')
  utest(None, tree.get, '/users/42/unknown')


@utest_run
def _() -> None:
  'RouteTree: path kind consumes all remaining components.'
  tree:RouteTree[str] = RouteTree()
  tree.insert('/files/{p:path}', 'files')
  tree.finalize()

  utest(('files', {'p': 'readme.txt'}), tree.get, '/files/readme.txt')
  utest(('files', {'p': 'a/b/c.txt'}), tree.get, '/files/a/b/c.txt')


@utest_run
def _() -> None:
  'RouteTree: fixed takes priority over pattern, with backtracking.'
  tree:RouteTree[str] = RouteTree()
  tree.insert('/items/special', 'special')
  tree.insert('/items/{id:int}', 'item')
  tree.finalize()

  utest(('special', {}), tree.get, '/items/special') # Fixed wins.
  utest(('item', {'id': 99}), tree.get, '/items/99') # Pattern matches.
  utest(None, tree.get, '/items/special/extra') # Fixed "special" has no children.


@utest_run
def _() -> None:
  'RouteTree: nat pattern.'
  tree:RouteTree[str] = RouteTree()
  tree.insert('/pages/{n:nat}', 'page')
  tree.finalize()

  utest(('page', {'n': 0}), tree.get, '/pages/0')
  utest(('page', {'n': 42}), tree.get, '/pages/42')
  utest(None, tree.get, '/pages/-1')
  utest(None, tree.get, '/pages/abc')


@utest_run
def _() -> None:
  'RouteTree: pos_int pattern.'
  tree:RouteTree[str] = RouteTree()
  tree.insert('/items/{id:pos_int}', 'item')
  tree.finalize()

  utest(('item', {'id': 1}), tree.get, '/items/1')
  utest(('item', {'id': 42}), tree.get, '/items/42')
  utest(None, tree.get, '/items/0')
  utest(None, tree.get, '/items/-1')
  utest(None, tree.get, '/items/abc')


@utest_run
def _() -> None:
  'RouteTree: date pattern.'
  tree:RouteTree[str] = RouteTree()
  tree.insert('/events/{d:date}', 'event')
  tree.finalize()

  utest(('event', {'d': date(2025, 3, 14)}), tree.get, '/events/2025-03-14')
  utest(None, tree.get, '/events/not-a-date')


@utest_run
def _() -> None:
  'RouteTree: prefix-differentiated patterns (different prefix groups, no overlap).'
  tree:RouteTree[str] = RouteTree()
  tree.insert('/things/item-{id:int}', 'prefixed')
  tree.insert('/things/code-{h:hex}', 'suffixed')
  tree.finalize()

  utest(('prefixed', {'id': 5}), tree.get, '/things/item-5')
  utest(('suffixed', {'h': 'ff'}), tree.get, '/things/code-ff')
  utest(None, tree.get, '/things/other-5')


@utest_run
def _() -> None:
  'RouteTree: equivalent pattern reuse (same pattern, different terminal depths).'
  tree:RouteTree[str] = RouteTree()
  tree.insert('/a/{id:int}', 'item')
  tree.insert('/a/{id:int}/sub', 'item_sub')
  tree.finalize()

  utest(('item', {'id': 1}), tree.get, '/a/1')
  utest(('item_sub', {'id': 1}), tree.get, '/a/1/sub')


@utest_run_exc(ValueError)
def _() -> None:
  'Validation: duplicate route.'
  t:RouteTree[str] = RouteTree()
  t.insert('/x/{id:int}', 'a')
  t.insert('/x/{id:int}', 'b')


@utest_run_exc(ValueError)
def _() -> None:
  'Validation: overlapping patterns - shared characters (int vs hex both have digits).'
  t:RouteTree[str] = RouteTree()
  t.insert('/x/{id:int}', 'a')
  t.insert('/x/{h:hex}', 'b')


@utest_run_exc(ValueError)
def _() -> None:
  'Validation: overlapping patterns - one pattern matches all characters.'
  t:RouteTree[str] = RouteTree()
  t.insert('/x/{name}', 'a')
  t.insert('/x/{id:int}', 'b')


@utest_run_exc(ValueError)
def _() -> None:
  'Validation: path pattern must be the last component.'
  t:RouteTree[str] = RouteTree()
  t.insert('/x/{p:path}/y', 'a')


@utest_run_exc(ValueError)
def _() -> None:
  'Validation: route must start with a slash.'
  t:RouteTree[str] = RouteTree()
  t.insert('no-slash', 'a')
