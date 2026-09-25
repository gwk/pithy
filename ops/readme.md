# ops

Shell scripts for setting up computers: macOS developer machines and Fedora Linux servers.

* `common/`: scripts that apply to both platforms.
* `linux/`: server setup.
* `mac/`: macOS developer machine setup.

Run `common/install-rust.sh` to install Rust for building native Python packages.
The invoking user maintains the shared toolchain; each build user keeps a private Cargo cache.


## Versions

`versions.sh` holds the approved Python, SQLite, Vector and uv versions and download checksums used by their installers.
Update the version and associated download details together when approving a release.

## Check for updates

From the Pithy root, run `python3 -m tap_ops.releases` to compare installed, approved and latest upstream versions.
Installed versions come from `python3`, `sqlite3`, `vector` and `uv` on `PATH`; missing tools are shown as `installed none`.
Review links appear only when approved and latest versions differ.
Discrepancies have action suffixes for approval, installation and changes to `versions.sh`.
Only assignments that differ from `versions.sh` are printed, including archive checksums.
The command does not change approved versions or install anything.
