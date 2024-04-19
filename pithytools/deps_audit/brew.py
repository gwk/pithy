# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.argparse import Namespace
from pithy.dict import dict_dag_inverse_with_all_keys
from pithy.io import outL
from pithy.task import runO


def main_brew(args:Namespace) -> None:
  '''
  Brew's terminology regarding dependencies vs requirements is confusing.
  Apparently a requirement is a dependency that is not strictly versioned.
  Note: this was helpful: https://blog.jpalardy.com/posts/untangling-your-homebrew-dependencies/.
  '''

  deps_lines = runO(['brew', 'deps', '--installed', '--include-requirements', '--full-name']).splitlines()
  pkg_deps = dict(parse_brew_deps_line(line) for line in sorted(deps_lines))
  pkg_dependents = dict_dag_inverse_with_all_keys(pkg_deps)
  outL('\nPackage dependencies:', ('' if any(pkg_deps.values()) else ' none.'))
  for pkg, deps in sorted(pkg_deps.items()):
    if deps:
      outL(pkg, ': ', ' '.join(deps))

  outL('\nPackages without dependencies: ',
    ' '.join(pkg for pkg, deps in pkg_deps.items() if not deps) or '*none*',
    '.')

  outL('\nPackages without dependents: ',
    ' '.join(pkg for pkg, dependents in pkg_dependents.items() if not dependents) or '*none*',
    '.')



def parse_brew_deps_line(line:str) -> tuple[str,list[str]]:
  pkg, _, deps_str = line.partition(':')
  deps = deps_str.split()
  return pkg, deps
