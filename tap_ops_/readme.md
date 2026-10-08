# tap_ops

Service deployment and server operations. Requires Python 3.14+ and Pithy.

## Deployment

`tap_ops.deploy` deploys immutable builds beneath a service root, by default `/service`:

```
/service/
  builds/BUILD/
    build.json        Written last by `finalize`; a build without it cannot be activated.
    deploy.toml       The unit inventory, enablement, startup and readiness policy.
    venv/             The python environment.
    units/            The complete desired set of systemd .service and .timer files.
    users/USER/       Configuration and credentials owned by one service user.
  current             A relative symlink to the active build.
  systemd-units.json  Ownership record of the installed systemd units.
  USER/               Service user home directories. They hold persistent state only.
```

A build is created at its final path and never moved, so the venv and its scripts stay valid.
Unit files refer to the active build through `/service/current`, for example `ExecStart=/service/current/venv/bin/python -m app`
and `WorkingDirectory=/service/current/users/app/run`.
Systemd resolves the working directory when it starts a process, so a process stays in the build it started from.

Install `tap_ops` in each build's venv and run the steps with the copy in the build being activated, by its resolved path.
The deployer then does not depend on the build it replaces, and it is the version that the build itself pins.
Never run a step through `current`: `activate` moves that symlink, and a python started through it would import
from the new build for the rest of its run. When a build's own copy is broken, any other finalized build's venv,
or any other environment with `tap_ops` installed, serves as the deployer instead.
The caller creates and populates a build while services are running, then runs the steps as root:

```sh
sudo install -d -m 755 /service/builds
sudo mkdir -m 700 /service/builds/$BUILD   # Fail if the id already exists; private until finalized.
sudo chown "$USER" /service/builds/$BUILD
# Populate deploy.toml, venv/, units/ and users/USER/ as the unprivileged user.
py=/service/builds/$BUILD/venv/bin/python
sudo $py -P -m tap_ops.deploy finalize $BUILD
sudo $py -P -m tap_ops.deploy stop
sudo $py -P -m tap_ops.deploy activate $BUILD
# Run work that requires stopped services, such as database migrations.
sudo $py -P -m tap_ops.deploy start
sudo $py -P -m tap_ops.deploy verify
sudo $py -P -m tap_ops.deploy prune
```

* `finalize` validates the build and sets ownership. `deploy.toml`, `venv` and `units` become root-owned and readable by all.
  Each `users/USER` tree becomes private to that user and its group. USER must be an account whose home is `/service/USER`.
  The venv must not contain hard links, because changing their owner would also change the installer's cache;
  with uv, install using `--link-mode copy`.
  Compile the venv to bytecode before finalizing, with uv using `--compile-bytecode`:
  service users cannot write to a finalized venv, so they would otherwise recompile every module on each start.
* `stop` stops every managed unit: those in the manifest and those of every finalized build. Timers are stopped first.
* `activate` switches `current` atomically, reconciles the units as described below and applies `deploy.toml` enablement.
  It refuses to run while any managed unit is active.
  A process started through `current` keeps the unresolved path in its python search path,
  so one that outlived a switch would import from the new build.
* `start` checks installed state and starts only the current build's units with `start = true`.
  Timer-triggered services normally declare `start = false`.
* `verify` checks installed state, then watches directly started units with the current build's readiness rules.
  It uses the watcher described below and returns a nonzero exit status on failure.
* `check` requires the ownership manifest, installed file contents and modes, and live enablement to match the current build.
* `plan BUILD` reports proposed file changes and enable/disable actions without changing anything.
  Like `activate`, it accepts `-adopt-existing` and repeated `-adopt NAME`. Concurrent mutations can invalidate a plan.
* `enable` reapplies the current build's enablement policy, including disabling units declared with `enable = false`.
  `disable` disables all enabled units of that build. Neither command stops running units.
* `reload` checks installed state, reloads systemd, then reloads or restarts directly started units.
* `prune` removes unfinalized builds and old finalized builds. `-keep` sets how many to retain besides the current build.
* `status` shows live systemd state for all units in the current build, including timer-triggered services.
* `builds` lists the builds; `units` lists the current build's units, optionally filtered by `-kind`.

To roll back, run `stop`, `activate` the previous build, then `start` and `verify`, with that build's `tap_ops`.
The saved policy restores that build's inventory and readiness rules, independently of the current source checkout.
Builds created before `deploy.toml` was introduced require their original deployer; new code does not infer missing policy.

Each mutating step holds a nonblocking `pithy.advisory_lock` at `/service/deploy.lock`.
That lock ends when the command exits. The caller must hold a separate workflow lock from before source updates and build creation
until verification and pruning finish, including migrations and other application-specific work between steps.
All entry points that mutate the same deployment must participate in that workflow lock.
Keep lock files on a local filesystem and never unlink them: an advisory lock protects an open file description, not a filename.
`-root` and `-unit-dir` select other locations and must precede the step name.

## Deployment policy

Check in a `deploy.toml` and copy it into each build beside `units/`:

```toml
version = 1

[verify]
settle = 20
timeout = 120

[units."web.service"]
enable = true
start = true
ready_log = 'server ready\.'
message_key = '_'

[units."cleanup.timer"]
enable = true
start = true

[units."cleanup.service"]
enable = false
start = false
```

Every unit must explicitly declare `enable` and `start` as booleans. Membership must exactly match the supplied service and timer files;
missing files, undeclared files, unknown fields and invalid regular expressions fail validation before finalization.
`enable` controls persistent boot enablement; the unit's `[Install]` section still defines the systemd installation targets.
A unit with `enable = true` must have an `[Install]` section, because systemd cannot enable a unit without one.
`start` controls direct startup and verification. Triggered services remain part of the managed inventory and are stopped before activation,
even though they are not directly started or watched.

Without `ready_log`, verification marks a unit ready when it observes an active state. With it, readiness requires a matching journal message.
The watcher reads logs from just before the earliest recent start among the watched units.
`message_key` selects the message field for JSON application logs, defaulting to `_`.
The optional `[verify]` table sets the stable observation window and overall timeout in seconds, defaulting to 20 and 120.

Validate source configuration before building with `python -m tap_ops.deploy validate conf/deploy.toml conf`.
This needs neither root nor systemd. The checked-in policy is desired state;
`systemd-units.json` is generated ownership and recovery state; systemd and installed files are live state.
Do not check the host manifest into source control or replace it with a desired-state file.

## Watching units

`tap_ops.systemd.watch` is the watcher behind `verify`. Run it directly to watch arbitrary units with explicit readiness rules:

```sh
sudo $py -P -m tap_ops.systemd.watch web worker -ready 'web=server ready\.' -message-key worker=message
```

It polls `systemctl show` and follows `journalctl` for the named units; the `.service` suffix is optional.
Warning and error records are printed as they arrive. The exit status is 0 only when every unit is ready with no failures or error records.
Pass `-h` for the remaining options. There is no installed command; invoke the module with a python that has `tap_ops`.

## Systemd unit reconciliation

`tap_ops.deploy activate` performs this reconciliation with the units of the build.
It can also be run directly, as root on the target Linux host:

```sh
sudo python3 -m tap_ops.systemd.reconciliation conf -manifest /service/systemd-units.json
```

`conf` is the complete desired set of regular `.service` and `.timer` files for the host.
The tool installs them into `/etc/systemd/system` with mode 0644 and removes units previously recorded in the manifest that are absent from `conf`.
Unit files whose content and mode already match are left untouched.
Other files in `conf` are ignored, but unit types that are not managed (such as `.socket` and `.path`) and drop-in directories are errors.
Obsolete timers are handled before obsolete services. Each obsolete unit is stopped if active, cleared if failed, then disabled and deleted.
Systemd is reloaded after installation. The caller remains responsible for enabling and starting desired units.
The tool prints one line per unit: `Remove`, `Install`, `Update` or `Unchanged`.
`tap_ops.systemd.reconciliation.reconcile` returns the same information as a `Reconciliation`, so that callers can restart only changed units.
Run reconciliation before removing old application packages or running database migrations.

The versioned JSON manifest records the unit directory and owned filenames, and is written with mode 0600.
The tool records the union of old and new ownership before mutations, then records only desired units after a successful reload.
Rerun after a failure: partial installation and deletion retain enough ownership information to retry.
The manifest and unit files are replaced atomically, and reconciliation holds a nonblocking advisory lock next to the manifest.
A run that finds the lock held fails immediately.
Callers must serialize the full deployment, including package changes and migrations.
Use one manifest per host: a second source directory reconciled against the same manifest would remove the units of the first.

## Adopting an existing deployment

Existing untracked destination files are rejected unless explicitly adopted:

```sh
sudo python3 -m tap_ops.systemd.reconciliation conf -adopt-existing -adopt jobs.service -dry-run
sudo python3 -m tap_ops.systemd.reconciliation conf -adopt-existing -adopt jobs.service
```

`-adopt-existing` claims names in the desired source set.
Each `-adopt NAME` claims a specific legacy unit, including an obsolete unit that should be removed immediately.
It is safe to repeat adoption of an already removed name.
The tool cannot discover historical ownership from a new checkout; inventory legacy units explicitly on first use.

`-dry-run` prints a plan without writes, locking or systemctl calls; concurrent changes can invalidate that plan.
An empty source directory requires `-allow-empty` to remove all managed units.
`-unit-dir` selects another destination, chiefly for tests; real deployments must use a directory searched by systemd.

Only literal service and timer filenames are supported in this first version.
Template and instance units, symlinks (including masks), aliases, drop-ins, vendor unit files, service directories, credentials and accounts are not managed.
Reconciliation does not stop retained services or restart them after replacing their unit files.
The manifest is an ownership record, not a record of application deployment success.
Preserve it across branch switches; do not share one unit between manifests.
