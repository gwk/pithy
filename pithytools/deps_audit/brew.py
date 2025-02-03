# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from pithy.ansi import BOLD_OUT, RST_OUT
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
  pkg_dpdts = dict_dag_inverse_with_all_keys(pkg_deps)

  outL('\n', BOLD_OUT, 'Package dependencies:', RST_OUT)
  if any(pkg_deps.values()):
    for pkg, deps in sorted(pkg_deps.items()):
      if deps:
        outL(BOLD_OUT, pkg, RST_OUT, ': ', '  '.join(str(d) for d in sorted(deps)))
  else: outL('*none*')

  outL('\n', BOLD_OUT, 'Packages without dependencies:', RST_OUT)
  no_deps = [pkg for pkg, deps in pkg_deps.items() if not deps]
  if no_deps: outL('  '.join(str(p) for p in sorted(no_deps)))
  else: outL('*none*')

  outL('\n', BOLD_OUT, 'Packages without dependents:', RST_OUT)
  no_dpdts = [pkg for pkg, dpdts in pkg_dpdts.items() if not dpdts]
  if no_dpdts: outL('  '.join(str(p) for p in sorted(no_dpdts)))
  else: outL('*none*')



def parse_brew_deps_line(line:str) -> tuple[str,list[str]]:
  pkg, _, deps_str = line.partition(': ')
  deps_str = platform_dep_re.sub('', deps_str)
  deps = deps_str.split()
  return pkg, deps


platform_dep_re = re.compile(r':macOS >= \d+\.\d+(?: \(or Linux\))?')
