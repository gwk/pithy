# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ast import parse as parse_ast

from pithy.path import path_dir
from pithy.python.sem import (ast_to_sem_types, Sem, sem_for_source, SemExpression, SemFunctionType, SemInteractive, SemMatch,
  SemMatchAs, SemMatchCase, SemMatchClass, SemMatchMapping, SemMatchOr, SemMatchSequence, SemMatchSingleton, SemMatchStar,
  SemMatchValue, SemModule)
from pithy.python.sem.scopes import build_scope_info
from tolkien import Source
from utest import utest_run, utest_type, utest_val


def _collect_sem_types(sem:Sem) -> set[type[Sem]]:
  'Walk the the sem tree and return the set of all distinct Sem types found.'
  return { type(el) for el in sem.walk() }


concrete_sem_types = set(t for t in ast_to_sem_types.values() if hasattr(t, 'ast_key'))


# The following three types are never produced by `sem_for_source` so we minimally test them here.
# They could be supported rather easily by passing the mode through.
mode_specific_sem_types = { SemExpression, SemInteractive, SemFunctionType }

utest_type(SemExpression, Sem, parse_ast('x + 1', mode='eval'))
utest_type(SemInteractive, Sem, parse_ast('x = 1\n', mode='single'))
utest_type(SemFunctionType, Sem, parse_ast('() -> int', mode='func_type'))

exec_sem_types = concrete_sem_types - mode_specific_sem_types # All the types that can be covered in a module.

# -- Match statement: exercises all match-related Sem types --

# Sem types that require match statements or non-exec parse modes are tested separately below.
match_sem_types:set[type[Sem]] = {SemMatch, SemMatchAs, SemMatchCase, SemMatchClass,
  SemMatchMapping, SemMatchOr, SemMatchSequence, SemMatchSingleton, SemMatchStar, SemMatchValue}

match_code = '''
cmd = None
match cmd:
  case Color.RED:
    pass
  case None:
    pass
  case True | False:
    pass
  case [first, *rest]:
    pass
  case {'key': val}:
    pass
  case Point(y=0):
    pass
  case x as alias_name:
    pass
'''

@utest_run
def _() -> None:
  match_source = Source('<match>', match_code)
  match_module = sem_for_source(match_source)
  collected_match_sem_types = _collect_sem_types(match_module)
  utest_val(set(), match_sem_types - collected_match_sem_types, desc='Match sem types not found in match module.')

  scope_info = build_scope_info(match_module, source=match_source)
  pattern_names = {n for n, u in scope_info.usages.items() if u.kind == 'pattern'}
  utest_val({'first', 'rest', 'val', 'x', 'alias_name'}, pattern_names, desc='Match pattern capture names.')


@utest_run
def _() -> None:
  'Load the `example` module and check that it contains all of the known Sem types.'

  example_path = path_dir(__file__) + '/example.py'
  example_source = Source.from_path(example_path)
  example_module = sem_for_source(example_source)
  example_types = _collect_sem_types(example_module)

  assert isinstance(example_module, SemModule)
  _ = build_scope_info(example_module, source=example_source)

  utest_val(exec_sem_types - match_sem_types, example_types, desc='Sem types in `example` module.')
