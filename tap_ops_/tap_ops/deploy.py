# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Reconcile a deployment's systemd service and timer files against a persistent ownership manifest.
Run as root. Callers retain control of package installation, enablement, startup and migrations.
'''

import json
import os
import re
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from subprocess import CalledProcessError, PIPE, run
from tempfile import NamedTemporaryFile

from pithy.advisory_lock import acquire_advisory_lock, AdvisoryLockBusy, release_advisory_lock
from pithy.cmdparse import Cmd, flag, opt, pos
from pithy.filestatus import file_stat, is_dir, is_file, is_link, path_exists
from pithy.fs import abs_path, list_dir, make_dirs, real_path, remove_file, remove_file_if_exists
from pithy.io import read_bytes_from_path, read_from_path
from pithy.path import Path


_context_keywords_ = ['deploy', 'deployment', 'manifest', 'service', 'systemctl', 'systemd', 'timer', 'unit']


unit_mode = 0o644

# Systemd unit types that this tool does not manage. Their presence in the source directory is an error, not a skip.
unsupported_suffixes = frozenset({
  '.automount', '.device', '.mount', '.path', '.scope', '.slice', '.socket', '.swap', '.target'})


class DeployError(Exception):
  'Invalid deployment inputs, ownership conflicts, or a concurrent reconciliation.'


@dataclass(frozen=True)
class Reconciliation:
  '''
  The outcome of a reconciliation, or the plan of a dry run.
  Callers use `installed` and `changed` to decide which units to enable, start or restart.
  '''
  installed:list[str] # Unit files that did not exist before.
  changed:list[str] # Unit files replaced because their content or mode differed.
  unchanged:list[str] # Unit files left untouched.
  removed:list[str] # Obsolete units in removal order, timers first.

  def lines(self) -> list[str]:
    groups = (('Remove', self.removed), ('Install', self.installed), ('Update', self.changed), ('Unchanged', self.unchanged))
    return [f'{label}: {name}' for label, names in groups for name in names]


class Deploy(Cmd):
  'Install desired systemd units and stop, disable and remove obsolete managed units. Run as root.'
  source:str = pos(doc='Directory containing the complete desired set of .service and .timer files.')
  manifest:str = opt(default='/service/manifest.json', doc='Persistent ownership manifest; one per host.')
  unit_dir:str = opt('-unit-dir', default='/etc/systemd/system', doc='Systemd unit installation directory.')
  adopt:list[str] = opt(default_factory=list, doc='Claim a previously installed unit by name; repeat for multiple units.')
  adopt_existing:bool = flag('-adopt-existing', doc='Claim existing files whose names occur in the desired source set.')
  allow_empty:bool = flag('-allow-empty', doc='Allow an empty source directory to remove all managed units.')
  dry_run:bool = flag('-dry-run', doc='Print the proposed changes without writing files or calling systemctl.')


def main() -> None:
  args = Deploy.parse_or_exit()
  try:
    reconcile(Path(args.source), Path(args.manifest), Path(args.unit_dir), adopt=args.adopt,
      adopt_existing=args.adopt_existing, allow_empty=args.allow_empty, dry_run=args.dry_run, on_plan=print_plan)
  except (DeployError, OSError, CalledProcessError) as exc:
    raise SystemExit(f'tap_ops.deploy: {exc}') from exc


def print_plan(plan:Reconciliation) -> None:
  for line in plan.lines(): print(line, flush=True)


def unit_name(value:object) -> str:
  'Accept only literal service and timer basenames, never paths, options or glob patterns.'
  if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_:][A-Za-z0-9_.:-]*\.(service|timer)', value):
    raise DeployError(f'Invalid unit name: {value!r}.')
  return value


def read_source(source:Path) -> dict[str,bytes]:
  'Read the desired units. Files unrelated to systemd are ignored; unit types and drop-ins that are not managed are errors.'
  desired:dict[str,bytes] = {}
  for name in list_dir(source, hidden=True):
    path = source / name
    ext = path.ext
    if ext == '.d' and Path(path.name_stem).ext in ('.service', '.timer', *unsupported_suffixes):
      raise DeployError(f'Drop-in directories are not supported: {path}.')
    if ext in unsupported_suffixes: raise DeployError(f'Unsupported unit type: {path}.')
    if ext not in ('.service', '.timer'): continue
    name = unit_name(name)
    if is_link(path) or not is_file(path, follow=True): raise DeployError(f'Expected a regular source file: {path}.')
    desired[name] = read_bytes_from_path(path)
  return desired


def read_manifest(path:Path, unit_dir:Path) -> set[str]:
  try: data = json.loads(read_from_path(path))
  except FileNotFoundError: return set()
  except (ValueError, UnicodeError) as exc: raise DeployError(f'Invalid manifest: {path}: {exc}') from exc
  if not isinstance(data, dict): raise DeployError(f'Manifest is not a JSON object: {path}.')
  version = data.get('version')
  if type(version) is not int or version != 1: raise DeployError(f'Unsupported manifest version: {path}: {version!r}.')
  if set(data) != {'version', 'unit_dir', 'units'}: raise DeployError(f'Invalid manifest keys: {path}: {sorted(data)}.')
  if data['unit_dir'] != str(unit_dir):
    raise DeployError(f'Manifest unit directory mismatch: {path}: recorded {data['unit_dir']!r}; requested {str(unit_dir)!r}.')
  if not isinstance(data['units'], list): raise DeployError(f'Manifest units is not a list: {path}.')
  names = [unit_name(n) for n in data['units']]
  if len(set(names)) != len(names): raise DeployError(f'Duplicate unit names in manifest: {path}.')
  return set(names)


def atomic_write(path:Path, content:bytes, mode:int) -> None:
  'Replace a file atomically, syncing its contents and directory before returning.'
  with NamedTemporaryFile(dir=path.parent, prefix=f'.{path.name}.', delete=False) as f:
    temp = Path(f.name)
    try:
      f.write(content)
      f.flush()
      os.fchmod(f.fileno(), mode)
      os.fsync(f.fileno())
      os.replace(temp, path)
      fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
      try: os.fsync(fd)
      finally: os.close(fd)
    finally:
      remove_file_if_exists(temp)


def write_manifest(path:Path, unit_dir:Path, names:set[str]) -> None:
  data = dict(version=1, unit_dir=str(unit_dir), units=sorted(names))
  atomic_write(path, (json.dumps(data, indent=2) + '\n').encode(), 0o600)


def systemctl(args:Sequence[str]) -> str:
  return run(['systemctl', *args], check=True, stdout=PIPE, text=True).stdout


def is_installed(dest:Path, content:bytes) -> bool:
  return path_exists(dest, follow=True) and file_stat(dest, follow=True).st_mode & 0o777 == unit_mode \
    and read_bytes_from_path(dest) == content


@contextmanager
def reconcile_lock(manifest:Path) -> Iterator[None]:
  'Hold the nonblocking reconciliation lock beside the manifest, creating its directory if necessary.'
  make_dirs(manifest.parent)
  lock_path = str(manifest) + '.lock'
  try: fd = acquire_advisory_lock(lock_path, exclusive=True, blocking=False)
  except AdvisoryLockBusy as exc: raise DeployError(f'Another reconciliation holds the lock: {lock_path}.') from exc
  try: yield
  finally: release_advisory_lock(fd)


def reconcile(source:Path, manifest:Path, unit_dir:Path, *, adopt:Sequence[str]=(), adopt_existing:bool=False,
 allow_empty:bool=False, dry_run:bool=False, control:Callable[[Sequence[str]],str]=systemctl,
 on_plan:Callable[[Reconciliation],None]|None=None) -> Reconciliation:
  '''
  Reconcile only explicitly owned unit files. Symlinks, drop-ins, vendor units, users and service data are not managed.
  A pending manifest records old and new ownership before mutations, so failures are recoverable by rerunning.
  The lock covers this reconciliation only; the caller must serialize the larger deployment workflow.
  Dry runs do not acquire a lock and are advisory snapshots.
  `on_plan` receives the result after validation and before any mutation, so that a run failing partway has logged its intent.
  '''
  source = Path(real_path(source))
  unit_dir = Path(real_path(unit_dir))
  manifest = Path(abs_path(manifest))
  if not is_dir(source, follow=True) or not is_dir(unit_dir, follow=True):
    raise DeployError('Source and unit directory must be directories.')
  if source == unit_dir: raise DeployError('Source must differ from the unit installation directory.')
  desired = read_source(source)
  if not desired and not allow_empty: raise DeployError('No source units found; use -allow-empty for deliberate removal.')
  claimed = {unit_name(n) for n in adopt}
  if adopt_existing: claimed.update(desired)

  def active_state(name:str) -> str:
    # `show` reports units that systemd has forgotten or never loaded as inactive, without failing.
    return control(['show', '--property=ActiveState', '--value', '--', name]).strip()

  with nullcontext() if dry_run else reconcile_lock(manifest):
    if is_link(manifest): raise DeployError(f'Manifest must not be a symlink: {manifest}.')
    previous = read_manifest(manifest, unit_dir) | claimed
    names = set(desired)
    for name in previous | names:
      dest = unit_dir / name
      if is_link(dest) or (path_exists(dest, follow=True) and not is_file(dest, follow=True)):
        raise DeployError(f'Expected a regular installed file: {dest}.')
      if name not in previous and path_exists(dest, follow=True):
        raise DeployError(f'Unmanaged unit exists: {dest}; use -adopt {name} to claim it.')
    unchanged = [n for n in sorted(names) if is_installed(unit_dir / n, desired[n])]
    result = Reconciliation(
      installed=[n for n in sorted(names) if not path_exists(unit_dir / n, follow=True)],
      changed=[n for n in sorted(names) if path_exists(unit_dir / n, follow=True) and n not in unchanged],
      unchanged=unchanged,
      removed=sorted(previous - names, key=lambda n: (not n.endswith('.timer'), n)))
    if on_plan: on_plan(result)
    if dry_run: return result

    # Record ownership before touching systemd or files, including any new installs that could fail partway through.
    write_manifest(manifest, unit_dir, previous | names)
    for name in result.removed:
      dest = unit_dir / name
      # Stop by active state only. Systemd refuses to stop an inactive unit that is not-found or failed to load,
      # which would otherwise block retries and repeated adoption of names that other units still reference.
      if active_state(name) not in ('inactive', 'failed'): control(['stop', name])
      # Stopping can leave a unit failed; systemd retains failed units after their files are removed.
      if active_state(name) == 'failed': control(['reset-failed', name])
      if path_exists(dest, follow=True):
        control(['disable', '--no-reload', name])
        remove_file(dest)
    for name in result.installed + result.changed:
      atomic_write(unit_dir / name, desired[name], unit_mode)
    # Always reload: a prior run can have written every file and then failed before its reload.
    control(['daemon-reload'])
    write_manifest(manifest, unit_dir, names)
    return result


if __name__ == '__main__': main()
