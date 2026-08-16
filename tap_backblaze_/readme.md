# tap_backblaze

Backblaze B2 integration built on `b2sdk` and `pithy`.

* `tap_backblaze.creds`: the `B2Creds` credential type, loadable from and savable to JSON.
* `tap_backblaze.capabilities`: B2 capability names and the `file-ro`/`file-rw`/`file-rwd` groups.
* `tap_backblaze.key`: a command line tool for listing and creating B2 application keys.
* `tap_backblaze.fmt_creds`: parses application key text copied from the Backblaze website into JSON.
* `tap_backblaze.progress`: a TTY progress listener for uploads and downloads.
* `tap_backblaze.store`: `B2BackupStore`, an implementation of the `pithy.sqlite.backup.BackupStore` protocol.

This project is a work in progress and should be considered unstable.
