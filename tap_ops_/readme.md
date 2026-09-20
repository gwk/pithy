# tap_ops

Service deployment and server operations. Requires Python 3.14+ and Pithy.

## Systemd unit reconciliation

Run as root on the target Linux host:

```sh
sudo python3 -m tap_ops.deploy conf -manifest /service/manifest.json
```

`conf` is the complete desired set of regular `.service` and `.timer` files for the host.
The tool installs them into `/etc/systemd/system` with mode 0644 and removes units previously recorded in the manifest that are absent from `conf`.
Unit files whose content and mode already match are left untouched.
Other files in `conf` are ignored, but unit types that are not managed (such as `.socket` and `.path`) and drop-in directories are errors.
Obsolete timers are handled before obsolete services. Each obsolete unit is stopped if active, cleared if failed, then disabled and deleted.
Systemd is reloaded after installation. The caller remains responsible for enabling and starting desired units.
The tool prints one line per unit: `Remove`, `Install`, `Update` or `Unchanged`.
`tap_ops.deploy.reconcile` returns the same information as a `Reconciliation`, so that callers can restart only changed units.
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
sudo python3 -m tap_ops.deploy conf -adopt-existing -adopt jobs.service -dry-run
sudo python3 -m tap_ops.deploy conf -adopt-existing -adopt jobs.service
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
