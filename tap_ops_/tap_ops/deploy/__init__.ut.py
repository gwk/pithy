# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from tempfile import TemporaryDirectory

from pithy.filestatus import file_stat, path_exists
from pithy.fs import list_dir, make_dirs, real_path
from pithy.io import read_from_path, write_to_path
from pithy.path import Path
from tap_ops.deploy import (activate, build_config, check, current_id, DeployError, disable, enable, finalize, Layout,
  list_builds, plan, prune, read_build, reload, start, status, stop, verify)
from tap_ops.deploy.config import DeployConfig
from utest import utest_exc, utest_run, utest_val


service = '[Service]\nExecStart=/service/current/venv/bin/python -m app\n\n[Install]\nWantedBy=multi-user.target\n'
triggered = '[Service]\nType=oneshot\nExecStart=/service/current/venv/bin/python -m app.sync\n'
timer = '[Timer]\nOnCalendar=minutely\n\n[Install]\nWantedBy=timers.target\n'


class Systemd:
  'A fake systemctl that tracks which units are active.'

  def __init__(self) -> None:
    self.active:set[str] = set()
    self.enabled:set[str] = set()
    self.calls:list[list[str]] = [] # All calls except `show` queries and reloads.

  def __call__(self, args:Sequence[str]) -> str:
    verb = args[0]
    if verb == 'show':
      if '--property=UnitFileState' in args: return ('enabled' if args[-1] in self.enabled else 'disabled') + '\n'
      return ('active' if args[-1] in self.active else 'inactive') + '\n'
    if verb == 'daemon-reload': return ''
    self.calls.append(list(args))
    names = [a for a in args[1:] if not a.startswith('-')]
    match verb:
      case 'stop': self.active.difference_update(names)
      case 'start': self.active.update(names)
      case 'enable': self.enabled.update(names)
      case 'disable': self.enabled.difference_update(names)
      case 'reload-or-restart': self.active.update(names)
      case _: raise ValueError(args)
    return ''

  def take_calls(self) -> list[list[str]]:
    calls = self.calls
    self.calls = []
    return calls


class Host:
  'A service root in a temporary directory, with fakes for the operations that require root.'

  def __init__(self, root:Path) -> None:
    self.layout = Layout(root=root / 'service', unit_dir=root / 'units')
    self.control = Systemd()
    self.owners:dict[str,tuple[int,int]] = {} # Path relative to the service root, to uid and gid.
    self.uids = {'web': 2001, 'logs': 2002}
    make_dirs(self.layout.unit_dir)


  def chown(self, path:str, uid:int, gid:int) -> None:
    self.owners[str(Path(path).relative_to(self.layout.root))] = (uid, gid)


  def user_info(self, name:str) -> tuple[int,int,str]:
    if name not in self.uids: raise DeployError(f'Unknown user: {name!r}.')
    return self.uids[name], self.uids[name], str(self.layout.root / name)


  def populate(self, build_id:str, units:dict[str,str], policy:str|None=None) -> Path:
    'Create an unfinalized build as a caller would, with a restrictive directory mode.'
    build_dir = self.layout.build_dir(build_id)
    make_dirs(build_dir / 'venv/bin')
    make_dirs(build_dir / 'units')
    make_dirs(build_dir / 'users/web/creds')
    os.chmod(build_dir, 0o700)
    write_to_path(build_dir / 'venv/bin/python', '')
    os.chmod(build_dir / 'venv/bin/python', 0o770)
    write_to_path(build_dir / 'users/web/creds/key', 'secret')
    os.chmod(build_dir / 'users/web/creds/key', 0o664)
    for name, content in units.items(): write_to_path(build_dir / 'units' / name, content)
    if policy is None:
      policy = 'version = 1\n' + '\n'.join(
        f'[units."{name}"]\nenable = {str("[Install]" in content).lower()}\nstart = {str("[Install]" in content).lower()}\n'
        for name, content in units.items())
    write_to_path(build_dir / 'deploy.toml', policy)
    return build_dir


  def finalize(self, build_id:str) -> None:
    finalize(self.layout, build_id, user_info=self.user_info, chown=self.chown, relabel=lambda path: None)


@contextmanager
def fixture() -> Iterator[Host]:
  with TemporaryDirectory() as tmp: yield Host(Path(real_path(tmp)))


def mode(path:Path) -> int: return file_stat(path, follow=False).st_mode & 0o7777


@utest_run
def test_finalize_sets_ownership_and_modes() -> None:
  with fixture() as host:
    build_dir = host.populate('b1', {'web.service': service})
    host.finalize('b1')
    utest_val((0, 0), host.owners['builds/b1'])
    utest_val((0, 0), host.owners['builds/b1/venv/bin/python'])
    utest_val((0, 0), host.owners['builds/b1/units/web.service'])
    utest_val((0, 0), host.owners['builds/b1/deploy.toml'])
    utest_val(0o644, mode(build_dir / 'deploy.toml'))
    utest_val((0, 0), host.owners['builds/b1/users'])
    utest_val((2001, 2001), host.owners['builds/b1/users/web'])
    utest_val((2001, 2001), host.owners['builds/b1/users/web/creds/key'])
    utest_val(0o755, mode(build_dir), 'build directory is opened')
    utest_val(0o755, mode(build_dir / 'venv/bin/python'), 'executable is readable by all and not group-writable')
    utest_val(0o640, mode(build_dir / 'users/web/creds/key'), 'user file is closed to others')
    utest_val(0o750, mode(build_dir / 'users/web'), 'user directory is closed to others')
    build = read_build(host.layout, 'b1')
    utest_val((['web.service'], ['web']), (build.units, build.users))
    utest_exc(DeployError(f'Build is already finalized: {build_dir}.'), host.finalize, 'b1')


@utest_run
def test_finalize_rejects_invalid_builds() -> None:
  with fixture() as host:
    build_dir = host.populate('extra', {'web.service': service})
    write_to_path(build_dir / 'notes.txt', '')
    utest_exc(DeployError(f"Unexpected entries in build: {build_dir}: ['notes.txt']."), host.finalize, 'extra')

    build_dir = host.populate('linked', {'web.service': service})
    os.link(build_dir / 'venv/bin/python', host.layout.root / 'cache-entry')
    utest_exc(DeployError(f'Build venv contains hard links; install with copies instead: {build_dir / 'venv/bin/python'}.'),
      host.finalize, 'linked')

    build_dir = host.populate('stranger', {'web.service': service})
    make_dirs(build_dir / 'users/admin')
    utest_exc(DeployError("Unknown user: 'admin'."), host.finalize, 'stranger')

    host.populate('empty', {})
    utest_exc(DeployError, host.finalize, 'empty')
    utest_exc(DeployError("Invalid build id: '../b'."), host.finalize, '../b')
    for build_id in ('extra', 'linked', 'stranger', 'empty'):
      utest_val(0o700, mode(host.layout.build_dir(build_id)), f'{build_id} stays closed')
    utest_exc(DeployError(f'Build is not finalized: {host.layout.build_dir('extra')}.'), activate, host.layout, 'extra',
      control=host.control)


@utest_run
def test_finalize_rejects_user_homed_outside_root() -> None:
  with fixture() as host:
    host.populate('b1', {'web.service': service})
    utest_exc(DeployError("User 'web' is not a service user: home is '/home/web'."),
      finalize, host.layout, 'b1', user_info=lambda name: (1000, 1000, '/home/web'), chown=host.chown,
      relabel=lambda path: None)


@utest_run
def test_deploy_sequence() -> None:
  with fixture() as host:
    layout, control = host.layout, host.control
    host.populate('b1', {'web.service': service, 'sync.service': triggered, 'sync.timer': timer})
    host.finalize('b1')
    utest_val(['sync.timer', 'web.service'], build_config(layout, 'b1').started)
    utest_exc(DeployError(f'No build is active: {layout.current}.'), start, layout, control=control)

    utest_val(None, activate(layout, 'b1', control=control))
    utest_val('b1', current_id(layout))
    utest_val('builds/b1', os.readlink(layout.current))
    utest_val(['sync.service', 'sync.timer', 'web.service'], list_dir(layout.unit_dir))
    utest_val([['enable', 'sync.timer', 'web.service']], control.take_calls())
    utest_val(['sync.timer', 'web.service'], start(layout, control=control))
    control.take_calls()

    # The timer has started its service. The second build drops both.
    control.active.add('sync.service')
    host.populate('b2', {'web.service': service.replace('app', 'app2')})
    host.finalize('b2')
    active = ['sync.service', 'sync.timer', 'web.service']
    utest_exc(DeployError(f'Units are active; stop them before activating a build: {active}.'),
      activate, layout, 'b2', control=control)
    utest_val('b1', current_id(layout), 'a refused activation leaves the build current')

    utest_val(['sync.timer', 'sync.service', 'web.service'], stop(layout, control=control))
    utest_val([['stop', 'sync.timer'], ['stop', 'sync.service', 'web.service']], control.take_calls(), 'timers stop first')
    utest_val([], stop(layout, control=control), 'stopping stopped units')
    utest_val([], control.take_calls())

    utest_val('b1', activate(layout, 'b2', control=control))
    utest_val('b2', current_id(layout))
    utest_val(['web.service'], list_dir(layout.unit_dir))
    utest_val(service.replace('app', 'app2'), read_from_path(layout.unit_dir / 'web.service'))
    utest_val(['web.service'], start(layout, control=control))
    utest_val(False, path_exists(layout.root / f'.current.{os.getpid()}', follow=False))

    # Roll back. The units of the newer build remain managed, so they must be stopped first.
    utest_exc(DeployError, activate, layout, 'b1', control=control)
    stop(layout, control=control)
    utest_val('b2', activate(layout, 'b1', control=control))
    utest_val(['sync.service', 'sync.timer', 'web.service'], list_dir(layout.unit_dir))
    utest_val(service, read_from_path(layout.unit_dir / 'web.service'))


@utest_run
def test_activate_keeps_current_on_unit_conflict() -> None:
  with fixture() as host:
    layout, control = host.layout, host.control
    host.populate('b1', {'web.service': service})
    host.finalize('b1')
    activate(layout, 'b1', control=control)
    host.populate('b2', {'web.service': service, 'other.service': service})
    host.finalize('b2')
    write_to_path(layout.unit_dir / 'other.service', 'Unmanaged.')
    utest_exc(DeployError(f'Unmanaged unit exists: {layout.unit_dir / 'other.service'}; use -adopt other.service to claim it.'),
      activate, layout, 'b2', control=control)
    utest_val('b1', current_id(layout))
    utest_val('b1', activate(layout, 'b2', adopt_existing=True, control=control))
    utest_val(service, read_from_path(layout.unit_dir / 'other.service'))


@utest_run
def test_prune() -> None:
  with fixture() as host:
    layout = host.layout
    for build_id in ('b1', 'b2', 'b3', 'b4'):
      host.populate(build_id, {'web.service': service})
      host.finalize(build_id)
    host.populate('b5', {'web.service': service})
    # Finalized timestamps have one second resolution, so ties are broken by id.
    activate(layout, 'b2', control=host.control)
    utest_val(['b1', 'b5'], prune(layout, 2), 'the oldest finalized build and the unfinalized build are removed')
    utest_val(['b2', 'b3', 'b4'], [build_id for build_id, _ in list_builds(layout)])
    utest_val(['b3', 'b4'], prune(layout, 0))
    utest_val([], prune(layout, 0), 'the current build is never removed')
    utest_val('b2', current_id(layout))


@utest_run
def test_rollback_restores_policy_and_verification() -> None:
  with fixture() as host:
    layout, control = host.layout, host.control
    old_policy = '''version = 1
[verify]
settle = 2
timeout = 8
[units."web.service"]
enable = true
start = true
ready_log = 'old ready'
[units."sync.timer"]
enable = true
start = true
[units."sync.service"]
enable = false
start = false
'''
    host.populate('old', {'web.service': service, 'sync.timer': timer, 'sync.service': triggered}, old_policy)
    host.finalize('old')
    # The newer policy keeps the web unit installed but no longer starts or enables it.
    new_policy = '''version = 1
[units."web.service"]
enable = false
start = false
[units."worker.service"]
enable = true
start = true
ready_log = 'new ready'
'''
    host.populate('new', {'web.service': service, 'worker.service': service}, new_policy)
    host.finalize('new')
    activate(layout, 'old', control=control)
    start(layout, control=control)
    stop(layout, control=control)
    activate(layout, 'new', control=control)
    utest_val({'worker.service'}, control.enabled)
    utest_val(['worker.service'], start(layout, control=control))
    stop(layout, control=control)
    activate(layout, 'old', control=control)
    utest_val({'web.service', 'sync.timer'}, control.enabled)
    utest_val(['sync.timer', 'web.service'], start(layout, control=control))
    observed:list[DeployConfig] = []

    def watch(config:DeployConfig) -> int:
      observed.append(config)
      return 7

    utest_val(7, verify(layout, control=control, watch=watch), 'verification exit status propagates')
    utest_val(['sync.timer', 'web.service'], observed[0].started, 'triggered service is not watched')
    utest_val(('old ready', 2, 8), (observed[0].units['web.service'].ready_log, observed[0].settle, observed[0].timeout))
    control.take_calls()
    reload(layout, control=control)
    utest_val([['reload-or-restart', 'sync.timer', 'web.service']], control.take_calls())
    utest_val('active\n', status(layout, control=control))
    disable(layout, control=control)
    utest_val(set(), control.enabled)
    utest_exc(DeployError, check, layout, control=control)
    enable(layout, control=control)
    check(layout, control=control)


@utest_run
def test_plan_and_drift_checks() -> None:
  with fixture() as host:
    layout, control = host.layout, host.control
    host.populate('old', {'web.service': service, 'sync.service': triggered, 'sync.timer': timer})
    host.finalize('old')
    activate(layout, 'old', control=control)
    host.populate('new', {'web.service': service.replace('app', 'app2'), 'worker.service': service})
    host.finalize('new')
    control.take_calls()
    before = read_from_path(layout.manifest)
    changes, enabling, disabling = plan(layout, 'new', control=control)
    utest_val(['worker.service'], changes.installed)
    utest_val(['web.service'], changes.changed)
    utest_val(['sync.timer', 'sync.service'], changes.removed)
    utest_val((['worker.service'], []), (enabling, disabling))
    utest_val([], control.take_calls(), 'plan does not mutate systemd')
    utest_val(('old', before), (current_id(layout), read_from_path(layout.manifest)))
    write_to_path(layout.unit_dir / 'web.service', 'Drift.')
    utest_exc(DeployError, start, layout, control=control)
    utest_val(set(), control.active, 'file drift blocks startup')
    activate(layout, 'old', control=control)
    control.enabled.remove('web.service')
    utest_exc(DeployError, start, layout, control=control)
    enable(layout, control=control)
    check(layout, control=control)


@utest_run
def test_invalid_policy_leaves_current_untouched() -> None:
  with fixture() as host:
    layout, control = host.layout, host.control
    host.populate('old', {'web.service': service})
    host.finalize('old')
    activate(layout, 'old', control=control)
    build_dir = host.populate('bad', {'web.service': service})
    write_to_path(build_dir / 'deploy.toml', 'version = 1\n[units."web.service"]\nstart = true\n')
    control.take_calls()
    utest_exc(DeployError, host.finalize, 'bad')
    utest_val(False, path_exists(build_dir / 'build.json', follow=False))
    utest_val(('old', []), (current_id(layout), control.take_calls()))
