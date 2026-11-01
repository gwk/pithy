#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail

common_dir="$(cd "$(dirname "$0")" && pwd)"
source "$common_dir/../versions.sh"

outdated=0
if [[ $# -eq 1 && "$1" == -outdated ]]; then
  outdated=1
elif [[ $# -ne 0 ]]; then
  echo 'Usage: install-all.sh [-outdated]' >&2
  exit 1
fi

run_script() {
  printf '\n\nRunning %s\n' "$1"
  "$common_dir/$1" "${@:2}"
}

# Build SQLite first so Python links against the newly installed version.
sqlite_installed=''
if (( outdated )); then
  sqlite_installed="$(/usr/local/bin/sqlite3 -noinit --version 2>/dev/null)" || sqlite_installed=''
fi
if (( ! outdated )) || [[ "${sqlite_installed%% *}" != "$sqlite_version" ]]; then
  run_script build-sqlite.sh
fi
# Check the loaded SQLite after installation; a dynamically linked Python may already see the new library.
if (( ! outdated )) || ! run_script check-version.sh python sqlite; then
  run_script build-python.sh
fi

if (( ! outdated )) || [[ ! -x /opt/rust/cargo/bin/rustc ]]; then
  run_script install-rust.sh
else
  # Match the installed default, ignoring project toolchain overrides just as install-rust.sh does.
  rustup=/opt/rust/manager/bin/rustup
  if [[ ! -x "$rustup" ]]; then rustup="$(command -v rustup)"; fi
  rust_status="$(
    cd /opt/rust
    export RUSTUP_HOME=/opt/rust/rustup
    export CARGO_HOME=/opt/rust/cargo
    unset RUSTUP_TOOLCHAIN
    "$rustup" check --no-self-update
  )" || {
    rust_status_code=$?
    # rustup check returns 100 when an update is available, and 1 on error.
    [[ "$rust_status_code" == 100 ]] || exit "$rust_status_code"
  }
  printf '%s\n' "$rust_status"
  rust_default="$(
    cd /opt/rust
    RUSTUP_HOME=/opt/rust/rustup CARGO_HOME=/opt/rust/cargo "$rustup" default
  )"
  rust_default="${rust_default% (default)}"
  while IFS= read -r line; do
    case "$line" in
      "$rust_default - "[Uu]"pdate available"*) run_script install-rust.sh upgrade; break ;;
    esac
  done <<< "$rust_status"
fi

if (( ! outdated )) || ! run_script check-version.sh uv; then
  run_script install-uv.sh
fi
if (( ! outdated )) || ! run_script check-version.sh vector; then
  run_script install-vector.sh
fi
