# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import defaultdict
from dataclasses import dataclass, field

from packaging.requirements import Marker, Requirement
from packaging.utils import canonicalize_name
from pithy.ansi import BOLD_OUT, RST_OUT
from pithy.argparse import Namespace
from pithy.dict import dict_dag_inverse_with_all_keys
from pithy.io import outL
from pithy.json import parse_json
from pithy.task import runO
from pithy.transtruct import Transtructor


DepDict = dict[str,set[str]]


def main_pip(args:Namespace) -> None:
  simple_deps, detail_deps = parse_pkg_deps()
  out_deps(detail_deps, label='Packages/extras')
  out_deps(simple_deps, label='Package')



  # Now recompute the dependencies, but fold extras into the base package name.

def out_deps(pkg_deps:DepDict, label:str) -> None:
  pkg_dpdts = dict_dag_inverse_with_all_keys(pkg_deps)

  outL('\n', BOLD_OUT, f'{label} with dependencies:', RST_OUT)
  if any(pkg_deps.values()):
    for pkg, deps in sorted(pkg_deps.items()):
      if deps:
        outL(BOLD_OUT, pkg, RST_OUT, ': ', '  '.join(str(d) for d in sorted(deps)))
  else: outL('*none*')

  outL('\n', BOLD_OUT, f'{label} without dependencies:', RST_OUT)
  no_deps = [pkg for pkg, deps in pkg_deps.items() if not deps]
  if no_deps: outL('  '.join(str(p) for p in sorted(no_deps)))
  else: outL('*none*')

  outL('\n', BOLD_OUT, f'{label} without dependents:', RST_OUT)
  no_dpdts = [pkg for pkg, dpdts in pkg_dpdts.items() if not dpdts]
  if no_dpdts: outL('  '.join(str(p) for p in sorted(no_dpdts)))
  else: outL('*none*')


def parse_pkg_deps() -> tuple[DepDict,DepDict]:
  '''
  Returns two dicts mapping package names to dependencies.
  The first is detailed with extras; both dependent and dependency names may have bracketed "extra" suffixes.
  The second is simplified with extras folded into the base package name.

  This function invokes `pip inspect --disable-pip-version-check --no-color`.
  '''
  inspect_out = runO(['pip', 'inspect', '--disable-pip-version-check', '--no-color'])
  inspect_json = parse_json(inspect_out)

  inspect = transtructor.transtruct(PipInspect, inspect_json)

  simple_deps = defaultdict[str,set[str]](set)
  detail_deps = defaultdict[str,set[str]](set)

  for pkg in inspect.installed:
    pkg_name = canonicalize_name(pkg.metadata.name) # Not sure if canonicalize_name is necessary.
    _ = simple_deps[pkg_name] # Add this package to the dict if it is not already present.
    _ = detail_deps[pkg_name] # Add this package to the dict if it is not already present.

    for req_str in pkg.metadata.requires_dist:
      req = Requirement(req_str)
      req_name = canonicalize_name(req.name)

      simple_deps[pkg_name].add(req_name)

      # Now compute the detailed dependencies that account for extras on both sides.
      # The marker may describe an extra, which is the dependent extra in question.
      if req.marker:
        extra = extract_extra_from_marker(req.marker)
        env = {'extra': extra} if extra else {}
        if not req.marker.evaluate(env): continue # Skip irrelevant requirements, but try to respect all extra markers.
      else:
        extra = ''

      dpdt_name = f'{pkg_name}[{extra}]' if extra else pkg_name

      # Requirement.extras set describes the extras of the dependency, required by this dependent.
      # If there are multiple extras, then we list them out as separate dependencies.
      for req_extra in req.extras or {''}:
        dep_name = f'{req_name}[{req_extra}]' if req_extra else req_name
        detail_deps[dpdt_name].add(dep_name)

  return simple_deps, detail_deps


def extract_extra_from_marker(marker:Marker|None) -> str:
  if marker is None: return ''
  if not marker._markers: return ''
  return extract_extra_from_markers_list(marker._markers)


def extract_extra_from_markers_list(l:list[str|list|tuple]) -> str:
  if 'or' in l: return '' # Cannot easily handle 'or' combinations.
  for m in l:
    if isinstance(m, str):
      assert m == 'and', m
      continue
    if isinstance(m, list):
      e = extract_extra_from_markers_list(m)
      if e: return e
      continue
    else:
      assert isinstance(m, tuple), m
    var, op, val = m
    if var.value == 'extra' and op.value == '==': return str(val.value)
  return ''


transtructor = Transtructor()

@dataclass
class PipMetadata:
  metadata_version:str
  name:str
  version:str
  summary:str|None = None
  license:str|None = None
  requires_dist:list[str] = field(default_factory=list)
  provides_extras:list[str] = field(default_factory=list)

@dataclass
class PipPackage:
  metadata:PipMetadata

@dataclass
class PipInspect:
  version:str
  pip_version:str
  installed:list[PipPackage]
