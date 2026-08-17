# tap_backblaze

Backblaze B2 integration built on `pithy` and a direct client for the B2 native API.

* `tap_backblaze.api`: a client for the B2 native JSON-over-HTTP API: `B2Client`, response types, and the `B2Error` hierarchy.
* `tap_backblaze.creds`: the `B2Creds` credential type, loadable from and savable to JSON.
* `tap_backblaze.capabilities`: B2 capability names and the `file-ro`/`file-rw`/`file-rwd` groups.
* `tap_backblaze.key`: a command line tool for listing and creating B2 application keys.
* `tap_backblaze.fmt_creds`: parses application key text copied from the Backblaze website into JSON.
* `tap_backblaze.progress`: a TTY progress listener for uploads and downloads.
* `tap_backblaze.store`: `B2BackupStore`, an implementation of the `pithy.sqlite.backup.BackupStore` protocol.

The integration test suite in `test-integration/` exercises the client against the real B2 service;
it requires credentials and is run explicitly with `just test-backblaze`. See `test-integration/readme.md`.

This project is a work in progress and should be considered unstable.
