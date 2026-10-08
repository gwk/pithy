# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Deploy builds: finalize a populated build, stop services, activate the build, start services, and prune old builds.
Run as root. See the package documentation for the directory layout.
'''

from subprocess import CalledProcessError
from typing import Literal

from pithy.cmdparse import Cmd, flag, opt, pos, sub
from pithy.path import Path

from ..systemd.reconciliation import print_plan
from . import (activate, build_config, check, current_id, deploy_lock, DeployError, disable, enable, finalize, Layout,
  list_builds, plan, prune, reload, start, status, stop, verify)
from .config import read_config


class Finalize(Cmd):
  'Validate a populated build, set its ownership and permissions, and mark it complete.'
  build:str = pos(doc='Build id: the name of a directory in ROOT/builds.')
  label:str = opt(default='', doc='Description to record with the build, such as the source revision.')


class Stop(Cmd):
  'Stop every managed unit: those installed and those of every finalized build.'


class Activate(Cmd):
  'Make a finalized build current, install its units and enable them. All managed units must be stopped.'
  build:str = pos(doc='Build id.')
  adopt:list[str] = opt(default_factory=list, doc='Claim a previously installed unit by name; repeat for multiple units.')
  adopt_existing:bool = flag('-adopt-existing', doc='Claim existing unit files whose names occur in the build.')


class Start(Cmd):
  'Check the active build and start the units declared for direct startup.'


class Check(Cmd):
  'Check installed unit files, ownership, and enablement against the active build.'


class Enable(Cmd):
  'Apply the active build enablement policy.'


class Disable(Cmd):
  'Disable the active build units.'


class Reload(Cmd):
  'Reload systemd and reload or restart the active build direct-start units.'


class Verify(Cmd):
  'Check and watch the active build using its readiness policy.'


class Plan(Cmd):
  'Show file and enablement changes for a target build without changing the host.'
  build:str = pos(doc='Finalized build id.')
  adopt:list[str] = opt(default_factory=list, doc='Claim a legacy unit in the proposed plan.')
  adopt_existing:bool = flag('-adopt-existing', doc='Claim existing unit files with names in the target build.')


class Validate(Cmd):
  'Validate a deployment config against its unit files, without requiring root or a build.'
  config:str = pos(doc='Deployment TOML path.')
  units:str = pos(doc='Directory containing the complete desired unit files.')


class Units(Cmd):
  'List units declared by the active build.'
  kind:Literal['all','service','timer','start','enabled'] = opt(default='all', doc='Which units to list.')


class Prune(Cmd):
  'Remove unfinalized builds and old finalized builds, retaining the current build.'
  keep:int = opt(default=2, doc='Number of finalized builds to retain in addition to the current build.')


class Status(Cmd):
  'Show live systemd state for all units of the active build.'


class Builds(Cmd):
  'List builds, marking the current build with an asterisk.'


class Deploy(Cmd):
  'Deploy immutable builds beneath a service root. Run as root.'
  root:str = opt(default='/service', doc='Service root directory.')
  unit_dir:str = opt('-unit-dir', default='/etc/systemd/system', doc='Systemd unit installation directory.')
  cmd:Finalize|Stop|Activate|Start|Prune|Status|Builds|Check|Enable|Disable|Reload|Verify|Plan|Validate|Units = sub()


def main() -> None:
  args = Deploy.parse_or_exit()
  layout = Layout(root=Path(args.root), unit_dir=Path(args.unit_dir))
  try:
    if isinstance(args.cmd, Builds): print_builds(layout)
    elif isinstance(args.cmd, Status): print(status(layout), end='', flush=True)
    elif isinstance(args.cmd, Validate):
      config = read_config(Path(args.cmd.config), Path(args.cmd.units))
      print(f'Valid deployment config: {len(config.units)} units.', flush=True)
    elif isinstance(args.cmd, Plan):
      files, enable_names, disable_names = plan(layout, args.cmd.build, adopt=args.cmd.adopt,
        adopt_existing=args.cmd.adopt_existing)
      print_plan(files)
      for name in disable_names: print(f'Disable: {name}', flush=True)
      for name in enable_names: print(f'Enable: {name}', flush=True)
    elif isinstance(args.cmd, Units):
      config = build_config(layout)
      match args.cmd.kind:
        case 'all': names = sorted(config.units)
        case 'service' | 'timer': names = sorted(n for n in config.units if n.endswith('.' + args.cmd.kind))
        case 'start': names = config.started
        case 'enabled': names = config.enabled
      for name in names: print(name, flush=True)
    else:
      with deploy_lock(layout): run_step(layout, args.cmd)
  except (DeployError, OSError, CalledProcessError) as exc:
    raise SystemExit(f'tap_ops.deploy: {exc}') from exc


def run_step(layout:Layout, cmd:Finalize|Stop|Activate|Start|Prune|Check|Enable|Disable|Reload|Verify) -> None:
  match cmd:
    case Finalize():
      build = finalize(layout, cmd.build, label=cmd.label)
      print(f'Finalized: {build.id}; units: {len(build.units)}; users: {', '.join(build.users) or 'none'}.', flush=True)
    case Stop():
      for name in stop(layout): print(f'Stopped: {name}', flush=True)
    case Activate():
      previous = activate(layout, cmd.build, adopt=cmd.adopt, adopt_existing=cmd.adopt_existing, on_plan=print_plan)
      print(f'Activated: {cmd.build}; previous: {previous or 'none'}.', flush=True)
    case Start():
      for name in start(layout): print(f'Started: {name}', flush=True)
    case Prune():
      for build_id in prune(layout, cmd.keep): print(f'Removed: {build_id}', flush=True)
    case Check():
      check(layout)
      print('Active build units match installed state.', flush=True)
    case Enable(): enable(layout)
    case Disable(): disable(layout)
    case Reload(): reload(layout)
    case Verify(): raise SystemExit(verify(layout))


def print_builds(layout:Layout) -> None:
  current = current_id(layout)
  for build_id, build in list_builds(layout):
    mark = '*' if build_id == current else ' '
    desc = f'{build.finalized}  {build.label}'.rstrip() if build else 'unfinalized'
    print(f'{mark} {build_id}  {desc}', flush=True)


if __name__ == '__main__': main()
