# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import json
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from subprocess import CalledProcessError, PIPE, Popen
from tempfile import TemporaryDirectory

from tap_ops.deploy import DeployError, read_manifest, reconcile, Reconciliation, unit_name, write_manifest
from utest import utest_exc, utest_run, utest_val


class Systemd:
  '''
  A fake systemctl that tracks the active state of each unit and enforces the constraints that matter to reconciliation:
  systemd refuses to stop an inactive unit that is not loaded, and cannot disable a unit whose file is gone.
  '''

  def __init__(self, unit_dir:Path) -> None:
    self.unit_dir = unit_dir
    self.calls:list[list[str]] = [] # All calls except `show` queries.
    self.active:dict[str,str] = {} # Unit name to ActiveState; absent units are inactive.
    self.fail_on_stop:set[str] = set() # Units that enter the failed state when stopped.
    self.fail = '' # A verb that fails outright.
    self.reload_files:dict[str,str] = {} # Unit directory contents at the last daemon-reload.

  def __call__(self, args:Sequence[str]) -> str:
    verb, name = args[0], args[-1]
    if verb == 'show': return self.active.get(name, 'inactive') + '\n'
    self.calls.append(list(args))
    if verb == self.fail: raise CalledProcessError(1, ['systemctl', *args])
    match verb:
      case 'stop':
        if self.active.get(name, 'inactive') == 'inactive': raise CalledProcessError(5, ['systemctl', *args])
        self.active[name] = 'failed' if name in self.fail_on_stop else 'inactive'
      case 'reset-failed': self.active[name] = 'inactive'
      case 'disable':
        if not (self.unit_dir / name).exists(): raise CalledProcessError(1, ['systemctl', *args])
      case 'daemon-reload': self.reload_files = {p.name: p.read_text() for p in self.unit_dir.iterdir()}
      case _: raise ValueError(args)
    return ''

  def take_calls(self) -> list[list[str]]:
    calls = self.calls
    self.calls = []
    return calls


@contextmanager
def fixture() -> Iterator[tuple[Path,Path,Path,Systemd]]:
  'Yield a source directory, manifest path, unit directory and fake systemctl.'
  with TemporaryDirectory() as tmp:
    root = Path(tmp).resolve()
    source = root / 'source'
    units = root / 'units'
    source.mkdir()
    units.mkdir()
    yield source, root / 'state' / 'manifest.json', units, Systemd(units)


@utest_run
def test_install_update_unchanged() -> None:
  with fixture() as (source, manifest, units, control):
    (source / 'web.service').write_text('V1.')
    (source / 'notes.txt').write_text('Ignored.')
    (units / 'unrelated.service').write_text('Unmanaged.')
    result = reconcile(source, manifest, units, control=control)
    utest_val(Reconciliation(installed=['web.service'], changed=[], unchanged=[], removed=[]), result)
    utest_val({'web.service'}, read_manifest(manifest, units))
    utest_val(0o644, (units / 'web.service').stat().st_mode & 0o777)
    utest_val(0o600, manifest.stat().st_mode & 0o777)
    utest_val({'web.service': 'V1.', 'unrelated.service': 'Unmanaged.'}, control.reload_files, 'files present at reload')
    utest_val(False, (units / 'notes.txt').exists())

    # An unchanged unit is not rewritten, but systemd is still reloaded in case a prior run failed before its reload.
    inode = (units / 'web.service').stat().st_ino
    control.take_calls()
    result = reconcile(source, manifest, units, control=control)
    utest_val(Reconciliation(installed=[], changed=[], unchanged=['web.service'], removed=[]), result)
    utest_val(inode, (units / 'web.service').stat().st_ino)
    utest_val([['daemon-reload']], control.take_calls())

    (source / 'web.service').write_text('V2.')
    utest_val(['web.service'], reconcile(source, manifest, units, control=control).changed)
    utest_val('V2.', (units / 'web.service').read_text())
    (units / 'web.service').chmod(0o600)
    utest_val(['web.service'], reconcile(source, manifest, units, control=control).changed, 'mode repair')
    utest_val(0o644, (units / 'web.service').stat().st_mode & 0o777)
    utest_val('Unmanaged.', (units / 'unrelated.service').read_text())


@utest_run
def test_remove_obsolete_and_retry() -> None:
  'A deployment that installed a service and its timer is followed by one that removes both; the reload fails once.'
  with fixture() as (source, manifest, units, control):
    (source / 'web.service').write_text('Web.')
    for name in ('web.service', 'jobs.service', 'jobs.timer'): (units / name).write_text('Old.')
    manifest.parent.mkdir()
    write_manifest(manifest, units, {'web.service', 'jobs.service', 'jobs.timer'})
    control.active = {'jobs.service': 'active', 'jobs.timer': 'active'}
    control.fail = 'daemon-reload'
    utest_exc(CalledProcessError, reconcile, source, manifest, units, control=control)
    utest_val({'web.service', 'jobs.service', 'jobs.timer'}, read_manifest(manifest, units), 'pending ownership')
    # The fake rejects a disable that follows deletion, so this sequence also establishes that ordering.
    utest_val([['stop', 'jobs.timer'], ['disable', '--no-reload', 'jobs.timer'], ['stop', 'jobs.service'],
      ['disable', '--no-reload', 'jobs.service'], ['daemon-reload']], control.take_calls())
    utest_val(['web.service'], sorted(p.name for p in units.iterdir()))

    # Retry after systemd has forgotten the deleted units.
    control.fail = ''
    result = reconcile(source, manifest, units, control=control)
    utest_val(['jobs.timer', 'jobs.service'], result.removed)
    utest_val([['daemon-reload']], control.take_calls())
    utest_val({'web.service'}, read_manifest(manifest, units))


@utest_run
def test_obsolete_unit_states() -> None:
  with fixture() as (source, manifest, units, control):
    (source / 'web.service').write_text('Web.')
    # `gone` has no file and is inactive, as when another unit still references a deleted unit; it must not be stopped.
    names = ['broken.service', 'crashy.service', 'gone.service', 'idle.service']
    for name in names:
      if name != 'gone.service': (units / name).write_text('Old.')
    control.active = {'broken.service': 'failed', 'crashy.service': 'active'}
    control.fail_on_stop = {'crashy.service'}
    reconcile(source, manifest, units, adopt=names, control=control)
    utest_val([
      ['reset-failed', 'broken.service'], ['disable', '--no-reload', 'broken.service'],
      ['stop', 'crashy.service'], ['reset-failed', 'crashy.service'], ['disable', '--no-reload', 'crashy.service'],
      ['disable', '--no-reload', 'idle.service'],
      ['daemon-reload']], control.take_calls())
    utest_val(['web.service'], sorted(p.name for p in units.iterdir()))

    # Repeating the adoption of removed names is harmless.
    reconcile(source, manifest, units, adopt=names, control=control)
    utest_val([['daemon-reload']], control.take_calls())


@utest_run
def test_stop_failure_retains_ownership() -> None:
  with fixture() as (source, manifest, units, control):
    (source / 'web.service').write_text('Web.')
    (units / 'jobs.service').write_text('Retired.')
    control.active = {'jobs.service': 'active'}
    control.fail = 'stop'
    plans:list[Reconciliation] = []
    utest_exc(CalledProcessError, reconcile, source, manifest, units, adopt=['jobs.service'], control=control,
      on_plan=plans.append)
    utest_val([Reconciliation(installed=['web.service'], changed=[], unchanged=[], removed=['jobs.service'])], plans,
      'plan delivered before the failure')
    utest_val(True, (units / 'jobs.service').exists())
    utest_val({'web.service', 'jobs.service'}, read_manifest(manifest, units))


@utest_run
def test_adoption_and_dry_run() -> None:
  with fixture() as (source, manifest, units, control):
    (source / 'web.service').write_text('New.')
    (units / 'web.service').write_text('Old.')
    dest = units / 'web.service'
    utest_exc(DeployError(f'Unmanaged unit exists: {dest}; use -adopt web.service to claim it.'),
      reconcile, source, manifest, units, control=control)
    utest_val(False, manifest.exists())

    (units / 'jobs.service').write_text('Retired.')
    plan = reconcile(source, manifest, units, adopt_existing=True, adopt=['jobs.service'], dry_run=True, control=control)
    utest_val(Reconciliation(installed=[], changed=['web.service'], unchanged=[], removed=['jobs.service']), plan)
    utest_val(['Remove: jobs.service', 'Update: web.service'], plan.lines())
    utest_val([], control.calls)
    utest_val(False, manifest.exists())
    utest_val('Old.', dest.read_text())

    result = reconcile(source, manifest, units, adopt_existing=True, adopt=['jobs.service'], control=control)
    utest_val(plan, result)
    utest_val(False, (units / 'jobs.service').exists())
    utest_val('New.', dest.read_text())


@utest_run
def test_empty_source() -> None:
  with fixture() as (source, manifest, units, control):
    (units / 'web.service').write_text('Web.')
    (units / 'unrelated.service').write_text('Unmanaged.')
    manifest.parent.mkdir()
    write_manifest(manifest, units, {'web.service'})
    utest_exc(DeployError, reconcile, source, manifest, units, control=control)
    utest_val(True, (units / 'web.service').exists())
    reconcile(source, manifest, units, allow_empty=True, control=control)
    utest_val(set(), read_manifest(manifest, units))
    utest_val(['unrelated.service'], sorted(p.name for p in units.iterdir()))


@utest_run
def test_source_validation() -> None:
  with fixture() as (source, manifest, units, control):
    (source / 'web.service').write_text('Web.')

    def check(path:Path, exc:DeployError) -> None:
      utest_exc(exc, reconcile, source, manifest, units, control=control)
      if path.is_dir() and not path.is_symlink(): path.rmdir()
      else: path.unlink()

    path = source / 'jobs.socket'
    path.write_text('Socket.')
    check(path, DeployError(f'Unsupported unit type: {path}.'))
    path = source / 'web.service.d'
    path.mkdir()
    check(path, DeployError(f'Drop-in directories are not supported: {path}.'))
    path = source / 'jobs@.service'
    path.write_text('Template.')
    check(path, DeployError("Invalid unit name: 'jobs@.service'."))
    path = source / 'link.service'
    path.symlink_to(source / 'web.service')
    check(path, DeployError(f'Expected a regular source file: {path}.'))
    utest_val([], control.calls)
    utest_val(False, manifest.parent.exists())


@utest_run
def test_manifest_and_destination_validation() -> None:
  with fixture() as (source, manifest, units, control):
    (source / 'web.service').write_text('Web.')
    manifest.parent.mkdir()
    valid = {'version': 1, 'unit_dir': str(units), 'units': []}
    cases:list[tuple[object,str]] = [
      ([], f'Manifest is not a JSON object: {manifest}.'),
      ({}, f'Unsupported manifest version: {manifest}: None.'),
      ({**valid, 'version': 2, 'extra': 0}, f'Unsupported manifest version: {manifest}: 2.'),
      ({**valid, 'version': True}, f'Unsupported manifest version: {manifest}: True.'),
      ({**valid, 'extra': 0}, f"Invalid manifest keys: {manifest}: ['extra', 'unit_dir', 'units', 'version']."),
      ({**valid, 'unit_dir': '/wrong'},
        f"Manifest unit directory mismatch: {manifest}: recorded '/wrong'; requested {str(units)!r}."),
      ({**valid, 'units': 'web.service'}, f'Manifest units is not a list: {manifest}.'),
      ({**valid, 'units': ['../jobs.service']}, "Invalid unit name: '../jobs.service'."),
      ({**valid, 'units': ['web.service', 'web.service']}, f'Duplicate unit names in manifest: {manifest}.'),
    ]
    for data, message in cases:
      manifest.write_text(json.dumps(data))
      utest_exc(DeployError(message), reconcile, source, manifest, units, control=control, _utest_label=message)
    manifest.write_text('{broken')
    utest_exc(DeployError, reconcile, source, manifest, units, control=control)
    manifest.unlink()

    (units / 'web.service').symlink_to(source / 'web.service')
    utest_exc(DeployError(f'Expected a regular installed file: {units / 'web.service'}.'),
      reconcile, source, manifest, units, adopt_existing=True, control=control)
    utest_val([], control.calls)


@utest_run
def test_lock_held_by_another_process() -> None:
  with fixture() as (source, manifest, units, control):
    (source / 'web.service').write_text('Web.')
    manifest.parent.mkdir()
    lock_path = str(manifest) + '.lock'
    holder_src = ('import fcntl, sys; f = open(sys.argv[1], "w"); fcntl.flock(f, fcntl.LOCK_EX); print(flush=True);'
      ' sys.stdin.read()')
    with Popen([sys.executable, '-c', holder_src, lock_path], stdin=PIPE, stdout=PIPE, text=True) as holder:
      assert holder.stdout is not None
      holder.stdout.readline() # Wait for the holder to acquire the lock.
      utest_exc(DeployError(f'Another reconciliation holds the lock: {lock_path}.'),
        reconcile, source, manifest, units, control=control)
      utest_val(False, (units / 'web.service').exists())
      holder.communicate() # Close stdin so that the holder exits and releases the lock.
    reconcile(source, manifest, units, control=control)
    utest_val(True, (units / 'web.service').exists())


for name in ('../jobs.service', '-jobs.service', '*.service', 'jobs.socket', 'jobs@.service', 'jobs@worker.service',
 '', '/jobs.service', 123):
  utest_exc(DeployError, unit_name, name)
