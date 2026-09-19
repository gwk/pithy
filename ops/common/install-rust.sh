#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Install a shared Rust toolchain on macOS or Fedora, as the invoking non-root user.
# Prerequisites: `brew install rustup` on macOS; `sudo dnf install rustup gcc` on Fedora.
# macOS also requires the Xcode command line tools for linking.
# Usage: install-rust.sh [install|upgrade] [PREFIX [TOOLCHAIN]]
# PREFIX defaults to /opt/rust. Installation defaults to stable; upgrade defaults to the installed default.
# Installation preserves an existing toolchain version. Use upgrade to explicitly update it.
#
# Only prefix creation needs sudo. The invoking user owns the installation; other users can read and execute it.
# Real toolchain binaries are exposed at PREFIX/cargo/bin, accommodating restricted users without shared caches.
# CARGO_HOME is set only within this script; builds should use each user's private default ~/.cargo.
# Fedora ships rustup-init, so bootstrap its manager separately from the exposed compiler binaries.
# No shell startup files are edited. The script prints the required environment settings.

set -euo pipefail

fail() { echo "Error:" "$@" >&2; exit 1; }
exe() { echo "+ $*"; "$@"; }

[[ $# -le 3 ]] || fail 'Usage: install-rust.sh [install|upgrade] [PREFIX [TOOLCHAIN]]'
action="${1:-install}"
prefix="${2:-/opt/rust}"
toolchain="${3:-}"
case "$action" in install|upgrade) ;; *) fail "Unknown action: $action." ;; esac
[[ "$prefix" == /* && "$prefix" != / ]] || fail 'PREFIX must be an absolute path other than /.'
[[ "$EUID" -ne 0 ]] || fail 'Run as your normal user; sudo is used only to create the install root.'
case "$(uname)" in Darwin|Linux) ;; *) fail "Unsupported platform: $(uname)." ;; esac

export RUSTUP_HOME="$prefix/rustup"
export CARGO_HOME="$prefix/cargo"
unset RUSTUP_TOOLCHAIN # Project or shell overrides must not choose the shared default's binaries.
umask 022

# Check prerequisites and conflicting paths before making changes.
if [[ -x "$prefix/manager/bin/rustup" ]]; then
  rustup="$prefix/manager/bin/rustup"
elif command -v rustup >/dev/null 2>&1; then
  rustup="$(command -v rustup)"
elif command -v rustup-init >/dev/null 2>&1; then
  rustup=''
else
  fail 'Install rustup first: `brew install rustup` on macOS or `sudo dnf install rustup gcc` on Fedora.'
fi
[[ ! -e "$CARGO_HOME/bin" || -L "$CARGO_HOME/bin" ]] || fail "$CARGO_HOME/bin exists and is not a symlink."
[[ ! -L "$prefix" ]] || fail "Install root must not be a symlink: $prefix."
if [[ "$action" == upgrade ]]; then
  [[ -x "$CARGO_HOME/bin/rustc" ]] || fail "No shared toolchain at $prefix; run install first."
fi

if [[ ! -d "$prefix" ]]; then
  exe sudo mkdir -p "$prefix"
  exe sudo chown "$(id -un):$(id -gn)" "$prefix"
fi
[[ -O "$prefix" ]] || fail "Install root must be owned by $(id -un): $prefix."
exe chmod 755 "$prefix"

if [[ -z "$rustup" ]]; then
  # Keep rustup's own proxy installation out of cargo/bin, which is a symlink to the real toolchain.
  CARGO_HOME="$prefix/manager" exe rustup-init -y --no-modify-path --default-toolchain none --profile default
  rustup="$prefix/manager/bin/rustup"
fi

# Run outside the checkout so rust-toolchain files and directory overrides cannot redirect `default`/`which`.
cd "$prefix"
if [[ "$action" == install ]]; then
  toolchain="${toolchain:-stable}"
  if "$rustup" which --toolchain "$toolchain" rustc >/dev/null 2>&1; then
    echo "Toolchain $toolchain is already installed; use upgrade to update it."
  else
    exe "$rustup" toolchain install --profile default --no-self-update "$toolchain"
  fi
else
  if [[ -z "$toolchain" ]]; then
    toolchain="$("$rustup" default)"
    toolchain="${toolchain% (default)}"
    [[ -n "$toolchain" && "$toolchain" != *$'\n'* ]] || fail 'Could not determine the default Rust toolchain.'
  fi
  exe "$rustup" update --no-self-update "$toolchain"
fi
exe "$rustup" default "$toolchain"
rustc="$("$rustup" which --toolchain "$toolchain" rustc)"
[[ -x "$rustc" ]] || fail "Missing installed compiler: $rustc."
toolchain_bin="$(dirname "$rustc")"
exe mkdir -p "$CARGO_HOME"
if [[ -L "$CARGO_HOME/bin" ]]; then exe rm "$CARGO_HOME/bin"; fi
exe ln -s "$toolchain_bin" "$CARGO_HOME/bin"
# Repair installs made with a restrictive umask, and keep shared code unwritable by other users.
# chmod's recursive traversal does not follow symlinks encountered within these directories.
exe chmod -R go+rX,go-w "$RUSTUP_HOME" "$CARGO_HOME"
if [[ -d "$prefix/manager" ]]; then exe chmod -R go+rX,go-w "$prefix/manager"; fi
exe "$CARGO_HOME/bin/rustc" --version
exe "$CARGO_HOME/bin/cargo" --version

printf '\nAdd to your shell profile:\n'
if [[ -x "$prefix/manager/bin/rustup" ]]; then
  printf 'export PATH="%s/cargo/bin:%s/manager/bin:$PATH"\n' "$prefix" "$prefix"
else
  printf 'export PATH="%s/cargo/bin:$PATH"\n' "$prefix"
fi
printf 'export RUSTUP_HOME=%q\n' "$RUSTUP_HOME"
echo 'Leave CARGO_HOME unset so each user keeps a private writable cache.'
