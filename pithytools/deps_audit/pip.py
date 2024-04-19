# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from packaging._parser import Op, Value, Variable
from packaging.requirements import Marker, Requirement
from packaging.utils import canonicalize_name
from pithy.argparse import Namespace
from pithy.io import outL, outM
from pithy.json import parse_json
from pithy.task import runO
from pithy.transtruct import Transtructor


def main_pip(args:Namespace) -> None:
  inspect_out = runO(['pip', 'inspect', '--disable-pip-version-check', '--no-color'])
  inspect_json = parse_json(inspect_out)
  #outM(inspect_json)

  inspect = transtructor.transtruct(PipInspect, inspect_json)
  #outM(inspect)

  # Map names (possibly including bracketed "extra" suffix) to names.
  deps = defaultdict[str,set[str]](set)
  for pkg in inspect.installed:
    name = canonicalize_name(pkg.metadata.name) # Not sure if canonicalize_name is necessary.
    for r_str in pkg.metadata.requires_dist:
      r = Requirement(r_str)
      if r.marker:
        extra = extract_extra(r.marker)
        env = {'extra': extra} if extra else {}
        if not r.marker.evaluate(env): continue # Skip irrelevant requirements, but try to respect all extra markers.
      else:
        extra = ''
      suffix = f'[{extra}]' if extra else ''
      full_name = f'{name}{suffix}'
      deps[full_name].add(r.name)

  outM(deps)


def extract_extra(marker:Marker|None) -> str:
  if marker is None: return ''
  if not marker._markers: return ''
  return extract_extra_from_list(marker._markers)


def extract_extra_from_list(l:list[str|list|tuple]) -> str:
  if 'or' in l: return '' # Cannot easily handle 'or' combinations.
  for m in l:
    if isinstance(m, str):
      assert m == 'and', m
      continue
    if isinstance(m, list):
      e = extract_extra_from_list(m)
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
  summary:str
  license:str|None = None
  requires_dist:list[str] = field(default_factory=list)

@dataclass
class PipPackage:
  metadata:PipMetadata

@dataclass
class PipInspect:
  version:str
  pip_version:str
  installed:list[PipPackage]
