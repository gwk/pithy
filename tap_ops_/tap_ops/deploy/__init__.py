# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Deploy immutable builds beneath a service root, by default `/service`.

A build is a complete directory tree that is created at its final path and never moved or modified once finalized:
```
/service/
  builds/BUILD/
    build.json        Written last by `finalize`; a build without it cannot be activated.
    deploy.toml       The unit inventory, enablement, startup and readiness policy for this build.
    venv/             The python environment.
    units/            The complete desired set of systemd .service and .timer files.
    users/USER/       Configuration and credentials owned by one service user.
  current             A relative symlink to the active build.
  systemd-units.json  Ownership record of the installed systemd units; see `tap_ops.systemd.reconciliation`.
  USER/               Service user home directories. They hold persistent state only and are not touched here.
```
Unit files refer to the active build through `/service/current`.

A deployment is a sequence of steps. The caller creates and populates a build directory while services are running.
`finalize` then validates it and sets ownership. `stop`, `activate` and `start` perform the switch.
The caller runs any work that requires stopped services, such as database migrations, between `activate` and `start`.
Each CLI step holds an advisory lock; the caller must also serialize the whole workflow, including build creation and pruning.

A process started through `current` keeps the unresolved path in its python search path.
If it outlived a switch, its later imports would come from the new build.
`activate` therefore refuses to run while any managed unit is active.
'''

import json
import os
import re
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, UTC
from pwd import getpwnam
from shutil import rmtree, which
from stat import S_IMODE, S_ISDIR, S_ISLNK, S_ISREG
from subprocess import run

from pithy.advisory_lock import acquire_advisory_lock, AdvisoryLockBusy, release_advisory_lock
from pithy.filestatus import is_dir, is_link, path_exists
from pithy.fs import list_dir, make_dirs, remove_file_if_exists
from pithy.io import read_from_path
from pithy.path import Path

from ..systemd.reconciliation import (atomic_write, is_installed, read_manifest, read_source, reconcile, Reconciliation,
  ReconciliationError, systemctl)
from ..systemd.watch import unit_name as watch_unit_name, Watcher
from .config import DeployConfig, read_config
from .errors import DeployError as DeployError


_context_keywords_ = ['activate', 'build', 'deployment', 'rollback', 'service', 'symlink', 'systemd', 'venv']


build_version = 1
build_names = frozenset({'deploy.toml', 'units', 'users', 'venv'})

type Control = Callable[[Sequence[str]],str] # Runs systemctl with the given arguments and returns its output.
type Chown = Callable[[str,int,int],None] # Sets the owner and group of a path without following symlinks.
type UserInfo = Callable[[str],tuple[int,int,str]] # Maps a user name to its uid, gid and home directory.


@dataclass(frozen=True)
class Layout:
  'The locations of a deployment: the service root and the systemd unit directory.'
  root:Path
  unit_dir:Path

  @property
  def builds(self) -> Path: return self.root / 'builds'

  @property
  def current(self) -> Path: return self.root / 'current'

  @property
  def manifest(self) -> Path: return self.root / 'systemd-units.json'

  def build_dir(self, build_id:str) -> Path:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', build_id): raise DeployError(f'Invalid build id: {build_id!r}.')
    return self.builds / build_id


@dataclass(frozen=True)
class Build:
  'The record that `finalize` writes to `build.json`.'
  id:str
  finalized:str # UTC timestamp in ISO format.
  label:str # Free-form description supplied by the caller, typically the source revision.
  units:list[str]
  users:list[str]


@contextmanager
def deploy_lock(layout:Layout) -> Iterator[None]:
  'Hold the nonblocking lock that serializes deployment steps on a host.'
  make_dirs(layout.root)
  lock_path = str(layout.root / 'deploy.lock')
  try: fd = acquire_advisory_lock(lock_path, exclusive=True, blocking=False)
  except AdvisoryLockBusy as exc: raise DeployError(f'Another deployment step holds the lock: {lock_path}.') from exc
  try: yield
  finally: release_advisory_lock(fd)


def finalize(layout:Layout, build_id:str, *, label:str='', user_info:UserInfo|None=None, chown:Chown=os.lchown,
 relabel:Callable[[Path],None]|None=None) -> Build:
  '''
  Validate a populated build directory, set its ownership and permissions, and mark it complete.
  The caller creates the directory with a restrictive mode, because it holds credentials before ownership is set.
  `venv` and `units` become root-owned and readable by all. Each `users/USER` tree becomes private to that user and group.
  `relabel` restores security contexts; the default runs `restorecon` when it is installed.
  '''
  build_dir = layout.build_dir(build_id)
  if is_link(build_dir) or not is_dir(build_dir, follow=False): raise DeployError(f'Build directory not found: {build_dir}.')
  if path_exists(build_dir / 'build.json', follow=False): raise DeployError(f'Build is already finalized: {build_dir}.')
  if unexpected := sorted(set(list_dir(build_dir, hidden=True)) - build_names):
    raise DeployError(f'Unexpected entries in build: {build_dir}: {unexpected}.')
  for name in ('units', 'venv'): _require_dir(build_dir / name)
  if not path_exists(build_dir / 'venv/bin/python', follow=True):
    raise DeployError(f'Build has no python executable: {build_dir / 'venv/bin/python'}.')
  config = read_config(build_dir / 'deploy.toml', build_dir / 'units')

  users_dir = build_dir / 'users'
  has_users = path_exists(users_dir, follow=False)
  if has_users: _require_dir(users_dir)
  users = list_dir(users_dir, hidden=True) if has_users else []
  owners:dict[str,tuple[int,int]] = {}
  for user in users:
    _require_dir(users_dir / user)
    uid, gid, home = (user_info or _user_info)(user)
    # Only service users homed beneath the root may own part of a build; this excludes root and login accounts.
    if home != str(layout.root / user): raise DeployError(f'User {user!r} is not a service user: home is {home!r}.')
    owners[user] = (uid, gid)

  # Changing the owner of a hard link changes every other link, such as the installer's package cache.
  for path, st in _walk(build_dir / 'venv'):
    if S_ISREG(st.st_mode) and st.st_nlink > 1:
      raise DeployError(f'Build venv contains hard links; install with copies instead: {path}.')

  _set_tree(build_dir / 'venv', 0, 0, chown, private=False)
  _set_tree(build_dir / 'units', 0, 0, chown, private=False)
  _set_tree(build_dir / 'deploy.toml', 0, 0, chown, private=False)
  for user, (uid, gid) in owners.items(): _set_tree(users_dir / user, uid, gid, chown, private=True)
  if has_users:
    chown(str(users_dir), 0, 0)
    os.chmod(users_dir, 0o755)
  (relabel or _restorecon)(build_dir)

  build = Build(id=build_id, finalized=datetime.now(UTC).isoformat(timespec='seconds'), label=label, units=sorted(config.units),
    users=users)
  data = dict(version=build_version, id=build.id, finalized=build.finalized, label=build.label, units=build.units,
    users=build.users)
  atomic_write(build_dir / 'build.json', (json.dumps(data, indent=2) + '\n').encode(), 0o644)
  # Open the build directory last, so that its contents are never exposed with their initial ownership.
  chown(str(build_dir), 0, 0)
  os.chmod(build_dir, 0o755)
  return build


def read_build(layout:Layout, build_id:str) -> Build:
  'Read the record of a finalized build.'
  path = layout.build_dir(build_id) / 'build.json'
  try: data = json.loads(read_from_path(path))
  except FileNotFoundError as exc: raise DeployError(f'Build is not finalized: {path.parent}.') from exc
  except (ValueError, UnicodeError) as exc: raise DeployError(f'Invalid build record: {path}: {exc}') from exc
  if not isinstance(data, dict) or data.get('version') != build_version or data.get('id') != build_id:
    raise DeployError(f'Invalid build record: {path}.')
  try: return Build(id=build_id, finalized=_str(data['finalized']), label=_str(data['label']),
    units=[_str(n) for n in data['units']], users=[_str(n) for n in data['users']])
  except (KeyError, TypeError) as exc: raise DeployError(f'Invalid build record: {path}.') from exc


def list_builds(layout:Layout) -> list[tuple[str,Build|None]]:
  'Return every build directory by id; the build is None if it is not finalized.'
  if not path_exists(layout.builds, follow=True): return []
  builds:list[tuple[str,Build|None]] = []
  for build_id in list_dir(layout.builds, hidden=True):
    finalized = path_exists(layout.build_dir(build_id) / 'build.json', follow=False)
    builds.append((build_id, read_build(layout, build_id) if finalized else None))
  return builds


def current_id(layout:Layout) -> str|None:
  'Return the id of the active build, or None if no build has been activated.'
  link = layout.current
  if not path_exists(link, follow=False): return None
  if not is_link(link): raise DeployError(f'Expected a symlink: {link}.')
  target = Path(os.readlink(link))
  if target.parent != Path('builds'): raise DeployError(f'Unexpected target of {link}: {str(target)!r}.')
  return target.name


def managed_units(layout:Layout) -> set[str]:
  'The units that can be running code from a build: those installed, and those of every finalized build.'
  try: names = read_manifest(layout.manifest, layout.unit_dir)
  except ReconciliationError as exc: raise DeployError(str(exc)) from exc
  for _, build in list_builds(layout):
    if build: names.update(build.units)
  return names


def active_units(names:Sequence[str], control:Control=systemctl) -> list[str]:
  'Return the units that are neither inactive nor failed. A unit that is waiting to restart is active.'
  # `show` reports units that systemd has forgotten or never loaded as inactive, without failing.
  return [n for n in names
    if control(['show', '--property=ActiveState', '--value', '--', n]).strip() not in ('inactive', 'failed')]


def stop(layout:Layout, *, control:Control=systemctl) -> list[str]:
  '''
  Stop every managed unit and return those that were active. Timers are stopped first, so that they cannot start a service.
  Stopping a unit also cancels its pending automatic restart.
  '''
  names = sorted(managed_units(layout))
  stopped:list[str] = []
  for is_timer in (True, False):
    # Systemd refuses to stop an inactive unit that is not loaded, so only active units are named.
    if active := active_units([n for n in names if n.endswith('.timer') == is_timer], control):
      control(['stop', *active])
      stopped.extend(active)
  if remaining := active_units(names, control): raise DeployError(f'Units are still active after stop: {remaining}.')
  return stopped


def activate(layout:Layout, build_id:str, *, adopt:Sequence[str]=(), adopt_existing:bool=False, control:Control=systemctl,
 on_plan:Callable[[Reconciliation],None]|None=None) -> str|None:
  '''
  Make a finalized build current, install its units and apply its enablement policy.
  Return the id of the previously active build. All managed units must be stopped.
  The step is idempotent; rerun it after a failure, or activate the previous build to roll back.
  '''
  config = build_config(layout, build_id)
  units_dir = layout.build_dir(build_id) / 'units'
  if active := active_units(sorted(managed_units(layout)), control):
    raise DeployError(f'Units are active; stop them before activating a build: {active}.')
  try:
    # Validate the unit changes before switching, so that an ownership conflict leaves the previous build current.
    reconcile(units_dir, layout.manifest, layout.unit_dir, adopt=adopt, adopt_existing=adopt_existing, dry_run=True,
      control=control)
    previous = current_id(layout)
    if previous != build_id: _set_current(layout, build_id)
    reconcile(units_dir, layout.manifest, layout.unit_dir, adopt=adopt, adopt_existing=adopt_existing, control=control,
      on_plan=on_plan)
  except ReconciliationError as exc: raise DeployError(str(exc)) from exc
  _enable_units(config, control)
  return previous


def start(layout:Layout, *, control:Control=systemctl) -> list[str]:
  'Check the active build, then start only the units declared for direct startup.'
  config = check(layout, control=control)
  names = config.started
  if names: control(['start', *names])
  return names


def build_config(layout:Layout, build_id:str|None=None) -> DeployConfig:
  'Read and validate a finalized build policy; default to the active build, never the checkout.'
  build_id = build_id or current_id(layout)
  if build_id is None: raise DeployError(f'No build is active: {layout.current}.')
  build = read_build(layout, build_id)
  build_dir = layout.build_dir(build_id)
  config = read_config(build_dir / 'deploy.toml', build_dir / 'units')
  if sorted(config.units) != build.units: raise DeployError(f'Build inventory differs from its policy: {build_id}.')
  return config


def plan(layout:Layout, build_id:str, *, adopt:Sequence[str]=(), adopt_existing:bool=False,
 control:Control=systemctl) -> tuple[Reconciliation,list[str],list[str]]:
  'Compare a target build against installed files, ownership, and live enablement without changing anything.'
  config = build_config(layout, build_id)
  try:
    files = reconcile(layout.build_dir(build_id) / 'units', layout.manifest, layout.unit_dir, adopt=adopt,
      adopt_existing=adopt_existing, dry_run=True, control=control)
  except ReconciliationError as exc: raise DeployError(str(exc)) from exc
  enable, disable = _enablement_changes(config, control)
  return files, enable, disable


def check(layout:Layout, *, control:Control=systemctl) -> DeployConfig:
  'Require installed unit files, ownership, and enablement to match the active build.'
  config = build_config(layout)
  build_id = current_id(layout)
  assert build_id is not None
  try: owned = read_manifest(layout.manifest, layout.unit_dir)
  except ReconciliationError as exc: raise DeployError(str(exc)) from exc
  if owned != set(config.units): raise DeployError('Installed unit inventory differs from the active build; activate it again.')
  for name, content in _read_units(layout.build_dir(build_id) / 'units').items():
    dest = layout.unit_dir / name
    if is_link(dest) or not is_installed(dest, content):
      raise DeployError(f'Installed unit differs from the active build: {name}; activate it again.')
  enable, disable = _enablement_changes(config, control)
  if enable or disable: raise DeployError(f'Unit enablement differs from the active build: enable {enable}; disable {disable}.')
  return config


def enable(layout:Layout, *, control:Control=systemctl) -> None:
  'Apply the active build enablement policy, including disabling units whose policy changed.'
  _enable_units(build_config(layout), control)


def disable(layout:Layout, *, control:Control=systemctl) -> None:
  'Disable all units in the active build that have persistent or runtime enablement.'
  names = [n for n in sorted(build_config(layout).units) if _is_enabled(n, control)]
  if names: control(['disable', *names])


def reload(layout:Layout, *, control:Control=systemctl) -> None:
  'Reload systemd and reload or restart the active build direct-start units.'
  config = check(layout, control=control)
  control(['daemon-reload'])
  if config.started: control(['reload-or-restart', *config.started])


def status(layout:Layout, *, control:Control=systemctl) -> str:
  'Show live state for every unit of the active build, including timer-triggered services.'
  return control(['show', '--no-pager', '--property=Id,LoadState,ActiveState,SubState,UnitFileState,Result',
    '--', *sorted(build_config(layout).units)])


def verify(layout:Layout, *, control:Control=systemctl, watch:Callable[[DeployConfig],int]|None=None) -> int:
  'Check installed state, then watch direct-start units using the active build readiness policy.'
  config = check(layout, control=control)
  if not config.started: return 0
  return (watch or _watch)(config)


def _watch(config:DeployConfig) -> int:
  watcher = Watcher(units=[watch_unit_name(n) for n in config.started],
    ready_patterns={watch_unit_name(n): re.compile(u.ready_log) for n, u in config.units.items() if u.start and u.ready_log},
    message_keys={watch_unit_name(n): u.message_key for n, u in config.units.items() if u.start},
    settle=config.settle, timeout=config.timeout, interval=1)
  try: return watcher.run(since=None)
  finally: watcher.finish()


def _is_enabled(name:str, control:Control) -> bool:
  return control(['show', '--property=UnitFileState', '--value', '--', name]).strip() in ('enabled', 'enabled-runtime')


def _enablement_changes(config:DeployConfig, control:Control) -> tuple[list[str],list[str]]:
  enable:list[str] = []
  disable:list[str] = []
  for name, unit in sorted(config.units.items()):
    state = control(['show', '--property=UnitFileState', '--value', '--', name]).strip()
    if unit.enable and state != 'enabled': enable.append(name)
    elif not unit.enable and state in ('enabled', 'enabled-runtime'): disable.append(name)
  return enable, disable


def _enable_units(config:DeployConfig, control:Control) -> None:
  enable, disable = _enablement_changes(config, control)
  if disable: control(['disable', *disable])
  if enable: control(['enable', *enable])


def prune(layout:Layout, keep:int) -> list[str]:
  '''
  Remove old builds and return their ids. The current build and the `keep` most recently finalized other builds are retained.
  Unfinalized builds are removed, so this must not run while another build is being populated.
  '''
  if keep < 0: raise DeployError(f'Invalid keep count: {keep}.')
  current = current_id(layout)
  builds = list_builds(layout)
  finalized = sorted((b for _, b in builds if b and b.id != current), key=lambda b: (b.finalized, b.id), reverse=True)
  retained = {b.id for b in finalized[:keep]}
  removed = [build_id for build_id, _ in builds if build_id != current and build_id not in retained]
  for build_id in removed: rmtree(layout.build_dir(build_id))
  return removed


def _require_dir(path:Path) -> None:
  if is_link(path) or not is_dir(path, follow=False): raise DeployError(f'Expected a directory: {path}.')


def _read_units(units_dir:Path) -> dict[str,bytes]:
  try: return read_source(units_dir)
  except ReconciliationError as exc: raise DeployError(str(exc)) from exc


def _str(value:object) -> str:
  if not isinstance(value, str): raise TypeError(value)
  return value


def _user_info(name:str) -> tuple[int,int,str]:
  try: entry = getpwnam(name)
  except KeyError as exc: raise DeployError(f'Unknown user: {name!r}.') from exc
  return entry.pw_uid, entry.pw_gid, entry.pw_dir


def _walk(path:Path) -> Iterator[tuple[str,os.stat_result]]:
  'Yield the path and status of `path` and every descendant, without following symlinks.'
  st = os.lstat(path)
  yield str(path), st
  if S_ISDIR(st.st_mode):
    for name in list_dir(path, hidden=True): yield from _walk(path / name)


def _set_tree(path:Path, uid:int, gid:int, chown:Chown, *, private:bool) -> None:
  '''
  Set the owner of a tree and remove write access for group and others, along with the setuid and setgid bits.
  A private tree is also closed to others. Any other tree is made readable by all.
  '''
  for p, st in _walk(path):
    chown(p, uid, gid)
    if S_ISLNK(st.st_mode): continue
    mode = S_IMODE(st.st_mode)
    if private: new_mode = mode & ~0o7027
    else: new_mode = (mode & ~0o7022) | 0o444 | (0o111 if S_ISDIR(st.st_mode) or mode & 0o100 else 0)
    if new_mode != mode: os.chmod(p, new_mode)


def _restorecon(path:Path) -> None:
  'Restore SELinux file contexts, where SELinux tools are installed.'
  if which('restorecon'): run(['restorecon', '-R', str(path)], check=True)


def _set_current(layout:Layout, build_id:str) -> None:
  'Atomically replace the `current` symlink.'
  temp = layout.root / f'.current.{os.getpid()}'
  remove_file_if_exists(temp)
  os.symlink(f'builds/{build_id}', temp)
  try: os.replace(temp, layout.current)
  finally: remove_file_if_exists(temp)
  fd = os.open(layout.root, os.O_RDONLY | os.O_DIRECTORY)
  try: os.fsync(fd)
  finally: os.close(fd)
