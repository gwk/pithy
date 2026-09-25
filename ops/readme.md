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

From the Pithy root, run `python3 -m tap_ops.releases` to report newer upstream releases or version tags, with links to review them.
The command does not change approved versions or install anything.
