# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Implementation for `craft-deps`.
'''


import json
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from os import chmod, getuid, lstat, makedirs, readlink, remove, symlink
from os.path import abspath, expanduser, isdir, islink, join, lexists, normpath
from stat import S_ISLNK, S_ISREG
from subprocess import run
from typing import Any


deps_config_name = '_deps.json'
deps_local_config_name = '_deps.local.json'
deps_dir_name = 'deps'


class DepsConfigError(Exception):
  'A local dependency declaration or location config is malformed.'


@dataclass(frozen=True)
class DepLocation:
  path:str
  writable:bool = False

  def __post_init__(self) -> None:
    if not self.path: raise ValueError('path must be a non-empty string')
    if not isinstance(self.writable, bool): raise ValueError(f'writable must be a boolean: {self.writable!r}')


@dataclass(frozen=True)
class ResolvedDep:
  name:str
  path:str
  writable:bool = False


def parse_deps_config(text:str, path:str=deps_config_name) -> tuple[str,...]:
  'Parse a checked-in dependency declaration.'
  data = parse_json_object(text, path)
  if set(data) != {'deps'}:
    raise DepsConfigError(f'{path}: expected only the key \'deps\'')
  names = data['deps']
  if not isinstance(names, list): raise DepsConfigError(f'{path}: \'deps\' must be a list')
  for name in names:
    if not isinstance(name, str) or not valid_dep_name(name):
      raise DepsConfigError(f'{path}: invalid dependency name: {name!r}')
  if len(set(names)) != len(names): raise DepsConfigError(f'{path}: dependency names must be unique')
  return tuple(names)


def parse_deps_local_config(text:str, path:str=deps_local_config_name) -> dict[str,DepLocation]:
  'Parse the machine-specific mapping from dependency names to directory paths.'
  data = parse_json_object(text, path)
  locations:dict[str,DepLocation] = {}
  for name, value in data.items():
    if not valid_dep_name(name): raise DepsConfigError(f'{path}: invalid dependency name: {name!r}')
    if not isinstance(value, Mapping) or not set(value) <= {'path', 'writable'} or 'path' not in value:
      raise DepsConfigError(f'{path}: dependency {name!r} must contain \'path\' and optional \'writable\'')
    dep_path = value['path']
    if not isinstance(dep_path, str) or not dep_path:
      raise DepsConfigError(f'{path}: dependency {name!r} path must be a non-empty string')
    writable = value.get('writable', False)
    if not isinstance(writable, bool):
      raise DepsConfigError(f'{path}: dependency {name!r} writable value must be a boolean: {writable!r}')
    locations[name] = DepLocation(dep_path, writable)
  return locations


def parse_json_object(text:str, path:str) -> dict[str,Any]:
  try: data = json.loads(text)
  except json.JSONDecodeError as e: raise DepsConfigError(f'{path}: invalid JSON: {e}') from e
  if not isinstance(data, dict): raise DepsConfigError(f'{path}: expected a JSON object')
  return data


def valid_dep_name(name:object) -> bool:
  return isinstance(name, str) and bool(name) and '/' not in name and name not in ('.', '..')


def load_deps_config(project_dir:str) -> tuple[str,...]:
  path = join(project_dir, deps_config_name)
  try:
    with open(path) as f: return parse_deps_config(f.read(), path)
  except FileNotFoundError: raise DepsConfigError(f'no {deps_config_name} in project directory: {project_dir}') from None


def load_deps_local_config(project_dir:str) -> dict[str,DepLocation]:
  path = join(project_dir, deps_local_config_name)
  try:
    with open(path) as f: return parse_deps_local_config(f.read(), path)
  except FileNotFoundError: return {}


def deps_local_config_trust_problem(project_dir:str) -> str|None:
  '''
  Why the local config is unsafe for a command to rewrite without reconfirming every declared entry.
  Ownership and permissions matter because consumers may use the paths and modes to open access across a security
  boundary. macOS ACLs require an additional check beyond the portable mode bits.
  '''
  path = join(project_dir, deps_local_config_name)
  try: st = lstat(path)
  except FileNotFoundError: return None
  if S_ISLNK(st.st_mode): return f'{path}: the local config is a symlink'
  if not S_ISREG(st.st_mode): return f'{path}: the local config is not a regular file'
  if st.st_uid != getuid(): return f'{path}: the local config is not owned by the invoking user'
  if st.st_mode & 0o022: return f'{path}: the local config is writable by group or other'
  if sys.platform == 'darwin' and macos_acl_entries(path): return f'{path}: the local config carries ACL entries'
  return None


def macos_acl_entries(path:str) -> list[str]:
  result = run(['/bin/ls', '-lde', path], capture_output=True, text=True)
  if result.returncode: raise DepsConfigError(f'could not inspect local config ACLs: {result.stderr.strip()}')
  return [match.group(1) for line in result.stdout.splitlines() if (match := re.match(r'\s*\d+: (.+)', line))]


def resolve_dep(project_dir:str, name:str, location:DepLocation) -> ResolvedDep:
  resolved = normpath(join(abspath(project_dir), expanduser(location.path)))
  if not isdir(resolved): raise DepsConfigError(f'dependency {name!r} target is not a directory: {resolved}')
  return ResolvedDep(name, resolved, location.writable)


def write_deps_local_config(project_dir:str, locations:Mapping[str,DepLocation]) -> None:
  path = join(project_dir, deps_local_config_name)
  data = {name: {'path': location.path, 'writable': location.writable} for name, location in locations.items()}
  if lexists(path): remove(path)
  with open(path, 'x') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
  chmod(path, 0o644)
  if sys.platform == 'darwin':
    result = run(['/bin/chmod', '-N', path], capture_output=True, text=True)
    if result.returncode: raise DepsConfigError(f'could not remove local config ACLs: {result.stderr.strip()}')


def ensure_dep_symlinks(project_dir:str, deps:list[ResolvedDep]) -> None:
  deps_dir = join(project_dir, deps_dir_name)
  makedirs(deps_dir, exist_ok=True)
  for dep in deps:
    link = join(deps_dir, dep.name)
    if islink(link):
      if readlink(link) == dep.path:
        print(f'ok      {deps_dir_name}/{dep.name} -> {dep.path}')
        continue
      remove(link)
    elif lexists(link):
      raise DepsConfigError(f'{link} exists and is not a symlink; remove it and rerun')
    symlink(dep.path, link)
    print(f'linked  {deps_dir_name}/{dep.name} -> {dep.path}')


def suggest_dep_path(project_dir:str, name:str) -> str:
  for candidate in (f'../../{name}/main', f'../{name}'):
    if isdir(normpath(join(project_dir, candidate))): return candidate
  return ''
