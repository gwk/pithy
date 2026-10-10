# ops

Shell scripts for setting up computers: macOS developer machines and Fedora Linux servers.

* `common/`: scripts that apply to both platforms.
* `linux/`: server setup.
* `mac/`: macOS developer machine setup.

Run `common/install-rust.sh` to install Rust for building native Python packages.
The invoking user maintains the shared toolchain; each build user keeps a private Cargo cache.

Run `common/vector/install.bash` to install the approved Vector release on Linux (x86_64 or aarch64) or macOS (Apple Silicon).
The service setup script remains Linux-only at `linux/vector/setup.bash`.


## Install uv

From the repository root, run `ops/common/install-uv.sh` on macOS or Linux (ARM64 or x86_64).
It downloads the approved release from GitHub, verifies its SHA-256 checksum, and installs root-owned binaries in `/opt/uv/bin` using sudo.
The directories and binaries are readable and executable by all users; updates require sudo.
Downloads use a temporary directory that is removed on exit.

Add this to your shell profile and the environment used to launch agents:

```sh
export PATH="/opt/uv/bin:$PATH"
```

Server provisioning can invoke `/opt/uv/bin/uv` explicitly.
The installer leaves shell profiles unchanged and reports if `uv` on its inherited `PATH` resolves elsewhere.
Caches, Python installations and tool environments retain uv's per-user defaults.

To migrate from Homebrew, first run the installer and verify `/opt/uv/bin/uv --version`.
Then run `brew uninstall uv`, apply the PATH setting above, and start a new shell.
Confirm that `command -v uv` prints `/opt/uv/bin/uv` and `uv --version` reports the approved release.
On Linux, remove the old manually installed `/usr/local/bin/uv` and `/usr/local/bin/uvx` after verifying the new installation.

To upgrade, update the approved version and all platform checksums in `versions.sh`, then rerun the installer.
Use this installer for updates instead of `uv self update`.


## Versions

`versions.sh` holds the approved Python, SQLite, Vector and uv versions and download checksums used by their installers.
Update the version and associated download details together when approving a release.
Python versions omit the git tag prefix `v` and may include `aN`, `bN` or `rcN` suffixes.
An approved prerelease enables prerelease update checks within that minor series; final versions consider only final releases.
Ordering is numeric, with alpha before beta before release candidate before final.

## Check for updates

From the Pithy root, run `python3 -m tap_ops.releases` to compare installed, approved and latest upstream versions.
Installed versions come from `python3`, `sqlite3`, `vector` and `uv` on `PATH`; missing tools are shown as `installed none`.
Review links appear only when approved and latest versions differ.
Discrepancies have action suffixes for approval, installation and changes to `versions.sh`.
Only assignments that differ from `versions.sh` are printed, including archive checksums.
The command does not change approved versions or install anything.
