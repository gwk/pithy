# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Report upstream versions newer than the approved releases in ops/versions.sh.
Python and SQLite use final-looking GitHub tags, not proof of published downloads.
Vector and uv use non-draft, non-prerelease GitHub releases. Nothing is installed or rewritten.
'''

import json
import os
import re
import shlex
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from subprocess import run
from sys import stderr
from typing import cast
from urllib.request import Request, urlopen

from pithy.cmdparse import Cmd, opt


_context_keywords_ = ['github', 'release', 'upgrade', 'version']


@dataclass(frozen=True)
class Component:
  name:str
  variable:str
  repo:str
  tag_pattern:str
  tags:bool
  review_url:str


components = (
  Component('Python', 'py_point_version', 'python/cpython', r'v(\d+\.\d+\.\d+)', True,
    'https://www.python.org/downloads/source/'),
  Component('SQLite', 'sqlite_version', 'sqlite/sqlite', r'version-(\d+\.\d+\.\d+(?:\.\d+)?)', True,
    'https://www.sqlite.org/download.html'),
  Component('Vector', 'vector_version', 'vectordotdev/vector', r'v(\d+\.\d+\.\d+)', False,
    'https://github.com/vectordotdev/vector/releases'),
  Component('uv', 'uv_version', 'astral-sh/uv', r'v?(\d+\.\d+\.\d+)', False,
    'https://github.com/astral-sh/uv/releases'),
)


class CheckReleases(Cmd):
  'Report newer upstream releases or version tags; never change approved versions or install anything.'
  versions:str = opt(default='ops/versions.sh', doc='Shared version file in a Pithy checkout.')


def version_key(version:str) -> tuple[int,...]:
  if not re.fullmatch(r'\d+\.\d+\.\d+(?:\.\d+)?', version):
    raise ValueError(f'Invalid version: {version!r}')
  parts = tuple(map(int, version.split('.')))
  return parts + (0,) * (4 - len(parts))


def read_versions(path:Path) -> dict[str,str]:
  'Read literal shell assignments without executing the file. Reject duplicate or nonliteral declarations.'
  values:dict[str,str] = {}
  for number, line in enumerate(path.read_text().splitlines(), 1):
    words = shlex.split(line, comments=True)
    if not words: continue
    if len(words) != 1 or not (m := re.fullmatch(r'([a-z][a-z0-9_]*)=([A-Za-z0-9_./:-]+)', words[0])):
      raise ValueError(f'{path}:{number}: expected a literal variable assignment.')
    key, value = m.groups()
    if key in values: raise ValueError(f'{path}:{number}: duplicate variable {key}.')
    values[key] = value
  for component in components:
    if component.variable not in values: raise ValueError(f'{path}: missing {component.variable}.')
    version_key(values[component.variable])
  return values


def parse_tags(text:str, pattern:str) -> set[str]:
  versions:set[str] = set()
  for line in text.splitlines():
    fields = line.split()
    if len(fields) != 2: raise ValueError('Malformed git ls-remote output.')
    if m := re.fullmatch('refs/tags/' + pattern, fields[1]): versions.add(m[1])
  return versions


def parse_releases(data:object, pattern:str) -> tuple[set[str],int]:
  if not isinstance(data, list): raise ValueError('GitHub releases response is not a list.')
  versions:set[str] = set()
  for release in data:
    if not isinstance(release, dict): raise ValueError('Malformed GitHub release.')
    if not isinstance(release.get('tag_name'), str): raise ValueError('GitHub release has no tag_name.')
    if not isinstance(release.get('draft'), bool) or not isinstance(release.get('prerelease'), bool):
      raise ValueError('GitHub release has no draft/prerelease flags.')
    if release['draft'] or release['prerelease']: continue
    if m := re.fullmatch(pattern, release['tag_name']): versions.add(m[1])
  return versions, len(data)


def github_json(url:str) -> object:
  headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'pithy-release-check',
    'X-GitHub-Api-Version': '2022-11-28'}
  if token := os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN'):
    headers['Authorization'] = f'Bearer {token}'
  with urlopen(Request(url, headers=headers), timeout=30) as response:
    return cast(object, json.load(response))


def upstream_versions(component:Component) -> set[str]:
  if component.tags:
    proc = run(['git', 'ls-remote', '--tags', '--refs', f'https://github.com/{component.repo}.git'],
      capture_output=True, text=True, timeout=30, check=True)
    versions = parse_tags(proc.stdout, component.tag_pattern)
  else:
    versions = set()
    page = 1
    while True:
      data = github_json(f'https://api.github.com/repos/{component.repo}/releases?per_page=100&page={page}')
      found, count = parse_releases(data, component.tag_pattern)
      versions.update(found)
      if count < 100: break
      page += 1
  if not versions: raise ValueError('No matching stable release versions found.')
  return versions


def describe(component:Component, approved:str, versions:set[str]) -> list[str]:
  latest = max(versions, key=version_key)
  newer = version_key(latest) > version_key(approved)
  status = ('new version tag detected' if component.tags else 'new stable release available') if newer else 'no newer version found'
  lines = [f'{component.name}: approved {approved}; latest {latest}; {status}.']
  if component.name == 'Python':
    series = version_key(approved)[:2]
    patches = [v for v in versions if version_key(v)[:2] == series]
    if not patches: raise ValueError(f'No final Python tags found for approved series {approved.rsplit(".", 1)[0]}.')
    patch = max(patches, key=version_key)
    if version_key(patch) > version_key(approved): lines.append(f'  New patch tag in approved series: {patch}.')
    if version_key(latest)[:2] > series: lines.append(f'  New major/minor series: {latest}; requires a separate upgrade decision.')
  lines.append(f'  Review: {component.review_url}')
  return lines


def report(values:dict[str,str]) -> bool:
  'Check all components even if one lookup fails; return whether every lookup succeeded.'
  success = True
  with ThreadPoolExecutor(max_workers=len(components)) as executor:
    futures = [executor.submit(upstream_versions, component) for component in components]
    for component, future in zip(components, futures):
      try: lines = describe(component, values[component.variable], future.result())
      except Exception as exc:
        print(f'{component.name}: lookup failed: {exc}', file=stderr)
        success = False
      else:
        for line in lines: print(line)
  return success


def main() -> None:
  args = CheckReleases.parse_or_exit()
  try: values = read_versions(Path(args.versions))
  except (OSError, ValueError) as exc: raise SystemExit(str(exc)) from exc
  if not report(values): raise SystemExit(1)


if __name__ == '__main__': main()
