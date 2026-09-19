# ops

Shell scripts for setting up computers: macOS developer machines and Fedora Linux servers.

* `common/`: scripts that apply to both platforms.
* `linux/`: server setup.
* `mac/`: macOS developer machine setup.

Run `common/install-rust.sh` to install Rust for building native Python packages.
The invoking user maintains the shared toolchain; each build user keeps a private Cargo cache.
