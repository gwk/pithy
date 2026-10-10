# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Compare installed, approved and upstream versions, with ready-to-paste checksums for newer releases.
Python, Vector and uv use git tags listed with `git ls-remote`, which transfers a few tens of kilobytes.
When a newer tag exists, the tool fetches that one release's checksums: the python.org downloads API for Python,
or the asset digests of the GitHub release for Vector and uv. A tag whose download is not yet published is reported as such.
SQLite uses the PRODUCT table that sqlite.org embeds in its download page for scripts to read.
Nothing is installed or rewritten.
'''

import json
import os
import re
import shlex
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from http.client import IncompleteRead
from pathlib import Path
from subprocess import run
from sys import stderr
from typing import cast
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pithy.cmdparse import Cmd, opt


_context_keywords_ = ['github', 'release', 'upgrade', 'version']


@dataclass(frozen=True)
class Upstream:
  '''
  Versions found upstream.
  `values` holds ready-to-paste versions.sh assignments for the version to approve, when one is newer and published.
  `note` explains why values are absent although a newer version exists.
  '''
  versions:set[str]
  values:dict[str,str] = field(default_factory=dict)
  note:str = ''


@dataclass(frozen=True)
class Component:
  name:str
  variable:str
  executable:str
  lookup:Callable[[str],Upstream] # Takes the approved version.
  review_url:str


def installed_version(component:Component) -> str|None:
  'Read the version of the executable on PATH; return None if it is not installed.'
  try:
    proc = run([component.executable, '--version'], capture_output=True, text=True, timeout=10, check=True)
  except FileNotFoundError: return None
  pattern = r'(?:Python |vector |uv )?(\d+\.\d+\.\d+(?:\.\d+)?[^\s]*)'
  if not (m := re.match(pattern + r'(?:\s|$)', proc.stdout.strip())):
    raise ValueError(f'Unrecognized version output from {component.executable}: {proc.stdout!r}')
  return m[1]


def version_key(version:str) -> tuple[int,...]:
  if not (m := re.fullmatch(r'(\d+\.\d+\.\d+(?:\.\d+)?)(?:(a|b|rc)(\d+))?', version)):
    raise ValueError(f'Invalid version: {version!r}')
  parts = tuple(map(int, m[1].split('.')))
  stage = {'a': 0, 'b': 1, 'rc': 2, None: 3}[m[2]]
  return parts + (0,) * (4 - len(parts)) + (stage, int(m[3] or 0))


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


def fetch(url:str, headers:dict[str,str]) -> bytes:
  'Fetch a small resource, retrying once if the connection drops mid-body.'
  request = Request(url, headers={'User-Agent': 'pithy-release-check', **headers})
  for attempt in range(2):
    try:
      with urlopen(request, timeout=30) as response:
        return cast(bytes, response.read())
    except IncompleteRead:
      if attempt: raise
  raise AssertionError('unreachable')


def fetch_json(url:str, headers:dict[str,str]) -> object:
  'Return None when the resource does not exist.'
  try: return cast(object, json.loads(fetch(url, headers)))
  except HTTPError as exc:
    if exc.code == 404: return None
    raise


def github_json(url:str) -> object:
  headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
  if token := os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN'):
    headers['Authorization'] = f'Bearer {token}'
  return fetch_json(url, headers)


def parse_tags(text:str, pattern:str) -> set[str]:
  versions:set[str] = set()
  for line in text.splitlines():
    fields = line.split()
    if len(fields) != 2: raise ValueError('Malformed git ls-remote output.')
    if m := re.fullmatch('refs/tags/' + pattern, fields[1]): versions.add(m[1])
  return versions


def github_tags(repo:str, pattern:str) -> set[str]:
  'List the tags of a GitHub repository without cloning it; `pattern` must capture the version as group 1.'
  proc = run(['git', 'ls-remote', '--tags', '--refs', f'https://github.com/{repo}.git'],
    capture_output=True, text=True, timeout=30, check=True)
  versions = parse_tags(proc.stdout, pattern)
  if not versions: raise ValueError('No matching version tags found.')
  return versions


def sha256_or_raise(value:object, what:str) -> str:
  if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
    raise ValueError(f'Malformed SHA-256 for {what}: {value!r}')
  return value


def parse_release_digests(data:object, asset_names:dict[str,str]) -> dict[str,str]:
  'Map each key of `asset_names` to the SHA-256 digest that GitHub records for the named release asset.'
  if not isinstance(data, dict) or not isinstance(data.get('assets'), list): raise ValueError('Malformed GitHub release.')
  if data.get('draft') or data.get('prerelease'): raise ValueError('GitHub release is a draft or prerelease.')
  digests = {a.get('name'): a.get('digest') for a in data['assets'] if isinstance(a, dict)}
  values:dict[str,str] = {}
  for key, name in asset_names.items():
    digest = digests.get(name)
    if not isinstance(digest, str) or not digest.startswith('sha256:'):
      raise ValueError(f'Missing or malformed digest for asset {name}.')
    values[key] = sha256_or_raise(digest.removeprefix('sha256:'), name)
  return values


def github_tool(repo:str, tag_pattern:str, tag_format:str, prefix:str, asset_formats:dict[str,str], approved:str) -> Upstream:
  'Versions from tags; when newer, platform tarball checksums from the release assets of the latest tag.'
  versions = github_tags(repo, tag_pattern)
  latest = max(versions, key=version_key)
  if version_key(latest) <= version_key(approved): return Upstream(versions)
  tag = tag_format.format(version=latest)
  data = github_json(f'https://api.github.com/repos/{repo}/releases/tags/{tag}')
  if data is None: return Upstream(versions, note=f'Tag {tag} has no published release yet.')
  asset_names = {f'{prefix}_sha256_{platform}': fmt.format(version=latest) for platform, fmt in asset_formats.items()}
  return Upstream(versions, {f'{prefix}_version': latest, **parse_release_digests(data, asset_names)})


python_api_url = 'https://www.python.org/api/v2/downloads'


def parse_python_release(data:object, version:str) -> int|None:
  'Return the python.org release id for a version, or None if the release is not published.'
  if not isinstance(data, list): raise ValueError('python.org release response is not a list.')
  for release in data:
    if not isinstance(release, dict) or release.get('name') != f'Python {version}': continue
    if not release.get('is_published'): return None
    if release.get('pre_release') and not re.search(r'(a|b|rc)\d+$', version): return None
    if not (m := re.fullmatch(r'.*/release/(\d+)/?', str(release.get('resource_uri')))):
      raise ValueError('python.org release has no resource_uri.')
    return int(m[1])
  return None


def parse_python_sha256(data:object, version:str) -> str:
  'Extract the SHA-256 of the xz source tarball from a python.org release file list.'
  if not isinstance(data, list): raise ValueError('python.org release file response is not a list.')
  for file in data:
    if isinstance(file, dict) and str(file.get('url')).endswith(f'/Python-{version}.tar.xz'):
      return sha256_or_raise(str(file.get('sha256_sum')).lower(), f'Python-{version}.tar.xz')
  raise ValueError(f'python.org lists no xz source tarball for Python {version}.')


def python_versions(approved:str) -> Upstream:
  '''
  Versions from cpython tags. Only a newer patch in the approved minor series gets a checksum;
  a new series requires a separate upgrade decision. The checksum comes from the python.org downloads API.
  '''
  # An approved prerelease opts its own minor series into prerelease updates.
  series = version_key(approved)[:2]
  prerelease = bool(re.search(r'(a|b|rc)\d+$', approved))
  tags = github_tags('python/cpython', r'v(\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?)')
  versions = {v for v in tags if not re.search(r'(a|b|rc)\d+$', v)
    or (prerelease and version_key(v)[:2] == series)}
  patches = [v for v in versions if version_key(v)[:2] == series]
  if not patches: raise ValueError(f'No eligible Python tags found for approved series {approved.rsplit(".", 1)[0]}.')
  patch = max(patches, key=version_key)
  if version_key(patch) <= version_key(approved): return Upstream(versions)
  release_id = parse_python_release(fetch_json(f'{python_api_url}/release/?name=Python%20{patch}', {}), patch)
  if release_id is None: return Upstream(versions, note=f'Tag v{patch} has no published release yet.')
  sha256 = parse_python_sha256(fetch_json(f'{python_api_url}/release_file/?release={release_id}', {}), patch)
  return Upstream(versions, {'py_point_version': patch, 'py_sha256': sha256})


sqlite_download_url = 'https://www.sqlite.org/download.html'
sqlite_product_header = 'PRODUCT,VERSION,RELATIVE-URL,SIZE-IN-BYTES,SHA3-HASH'


def parse_sqlite_products(text:str) -> Upstream:
  'Parse the PRODUCT table that the SQLite download page embeds in an HTML comment for scripts to read.'
  lines = [line for line in text.splitlines() if line.startswith('PRODUCT,')]
  if not lines or lines[0] != sqlite_product_header: raise ValueError('SQLite download page has no PRODUCT table.')
  for line in lines[1:]:
    fields = line.split(',')
    if len(fields) != 5: raise ValueError(f'Malformed SQLite PRODUCT line: {line!r}')
    _, version, path, _, sha3 = fields
    if not re.fullmatch(r'\d{4}/sqlite-src-\d+\.zip', path): continue
    version_key(version)
    if not re.fullmatch(r'[0-9a-f]{64}', sha3): raise ValueError(f'Malformed SQLite SHA3: {sha3!r}')
    return Upstream({version}, {'sqlite_version': version, 'sqlite_zip_remote_path': path, 'sqlite_sha3': sha3})
  raise ValueError('SQLite download page lists no source archive.')


def sqlite_versions(approved:str) -> Upstream:
  return parse_sqlite_products(fetch(sqlite_download_url, {}).decode())


components = (
  Component('Python', 'py_point_version', 'python3', python_versions,
    'https://www.python.org/downloads/source/'),
  Component('SQLite', 'sqlite_version', 'sqlite3', sqlite_versions,
    sqlite_download_url),
  Component('Vector', 'vector_version', 'vector',
    partial(github_tool, 'vectordotdev/vector', r'v(\d+\.\d+\.\d+)', 'v{version}', 'vector',
      {'linux_x86_64': 'vector-{version}-x86_64-unknown-linux-gnu.tar.gz',
       'linux_aarch64': 'vector-{version}-aarch64-unknown-linux-gnu.tar.gz',
       'macos_arm64': 'vector-{version}-arm64-apple-darwin.tar.gz'}),
    'https://github.com/vectordotdev/vector/releases'),
  Component('uv', 'uv_version', 'uv',
    partial(github_tool, 'astral-sh/uv', r'(\d+\.\d+\.\d+)', '{version}', 'uv',
      {'linux_x86_64': 'uv-x86_64-unknown-linux-gnu.tar.gz',
       'linux_aarch64': 'uv-aarch64-unknown-linux-gnu.tar.gz',
       'macos_arm64': 'uv-aarch64-apple-darwin.tar.gz',
       'macos_x86_64': 'uv-x86_64-apple-darwin.tar.gz'}),
    'https://github.com/astral-sh/uv/releases'),
)


class CheckReleases(Cmd):
  'Compare installed, approved and upstream versions; never change versions or install anything.'
  versions:str = opt(default='ops/versions.sh', doc='Shared version file in a Pithy checkout.')


def describe(component:Component, values:dict[str,str], upstream:Upstream, installed:str|None) -> list[str]:
  approved = values[component.variable]
  versions = upstream.versions
  if not versions: raise ValueError('No matching release versions found.')
  latest = max(versions, key=version_key)
  newer = version_key(latest) > version_key(approved)
  actions:list[str] = []
  if newer: actions.append(f'review and approve {latest}')
  elif approved != latest: actions.append('verify upstream version against approved version')
  target = latest if newer and not upstream.note else approved
  if installed != target:
    action = 'install' if installed is None else 'update installation to'
    actions.append(f'{action} {target}')
  changes = {key: value for key, value in upstream.values.items() if values.get(key) != value}
  if version_key(upstream.values.get(component.variable, approved)) < version_key(approved): changes = {}
  if changes: actions.append('update versions.sh')
  suffix = '; ' + '; '.join(actions) if actions else ''
  lines = [f'{component.name}: installed {installed or "none"}; approved {approved}; latest {latest}{suffix}.']
  if approved != latest: lines.append(f'  Review: {component.review_url}')
  if component.name == 'Python':
    series = version_key(approved)[:2]
    patch = max((v for v in versions if version_key(v)[:2] == series), key=version_key, default=approved)
    if version_key(patch) > version_key(approved): lines.append(f'  New patch tag in approved series: {patch}.')
    if version_key(latest)[:2] > series:
      lines.append(f'  New major/minor series: {latest}.')
  if upstream.note: lines.append(f'  {upstream.note}')
  if changes:
    lines.append('  Updated values for versions.sh:')
    lines.extend(f"  {key}='{value}'" for key, value in changes.items())
  return lines


def report(values:dict[str,str], components:tuple[Component,...]=components) -> bool:
  'Check all components even if one lookup fails; return whether every lookup succeeded.'
  success = True
  with ThreadPoolExecutor(max_workers=len(components)) as executor:
    futures = [executor.submit(component.lookup, values[component.variable]) for component in components]
    for component, future in zip(components, futures):
      try: lines = describe(component, values, future.result(), installed_version(component))
      except Exception as exc:
        print(f'{component.name}: lookup failed: {exc}', file=stderr, flush=True)
        success = False
      else:
        for line in lines: print(line, flush=True)
  return success


def main() -> None:
  args = CheckReleases.parse_or_exit()
  try: values = read_versions(Path(args.versions))
  except (OSError, ValueError) as exc: raise SystemExit(str(exc)) from exc
  if not report(values): raise SystemExit(1)


if __name__ == '__main__': main()
