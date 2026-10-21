#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Check selected tools at the locations maintained by the ops installers, without network access or package dependencies.
# Every tool must match its approved version exactly, including any approved prerelease suffix.
# The install locations are /opt/py/bin/python3, /opt/uv/bin/uv and /usr/local/bin/vector.
# SQLite is reported separately for /usr/local/bin/sqlite3 and the library loaded by /opt/py/bin/python3.
# This distinguishes an outdated SQLite installation from a Python build that still loads an older library.
# All selected checks report their results with maintenance instructions for failures; any failure makes the command exit nonzero.

set -euo pipefail

common_dir="$(cd "$(dirname "$0")" && pwd)"
source "$common_dir/../versions.sh"


main() {
  [[ $# -gt 0 ]] || fail 'Usage: check-version.sh all | TOOL... (python, sqlite, uv, vector).'
  local tool status=0 check_all=0
  for tool in "$@"; do
    case "$tool" in
      all) check_all=1 ;;
      python|sqlite|uv|vector) ;;
      *) fail "Unknown tool: $tool. Expected all, python, sqlite, uv or vector." ;;
    esac
  done
  if (( check_all )); then set -- python sqlite uv vector; fi
  for tool in "$@"; do
    case "$tool" in
      python)
        check 'python' "$py_point_version" Python 'Run build-python.sh.' \
          /opt/py/bin/python3 --version || status=1 ;;
      sqlite)
        check 'sqlite CLI' "$sqlite_version" '' 'Run build-sqlite.sh.' \
          /usr/local/bin/sqlite3 -noinit --version || status=1
        check 'sqlite loaded by Python' "$sqlite_version" '' \
          'Run build-sqlite.sh if needed, then rebuild Python with build-python.sh if it still loads the wrong SQLite.' \
          /opt/py/bin/python3 -c 'import sqlite3; print(sqlite3.sqlite_version)' || status=1 ;;
      uv)
        check 'uv' "$uv_version" uv 'Run install-uv.sh.' /opt/uv/bin/uv --version || status=1 ;;
      vector)
        check 'vector' "$vector_version" vector 'Run install-vector.sh.' /usr/local/bin/vector --version || status=1 ;;
    esac
  done
  return "$status"
}


check() {
  local label="$1" required="$2" prefix="$3" remedy="$4"
  shift 4
  local output name installed rest
  if ! output=$("$@"); then
    check_fail "Cannot read version using $1."
    return 1
  fi
  if [[ -n "$prefix" ]]; then
    read -r name installed rest <<< "$output"
    if [[ "$name" != "$prefix" ]]; then
      check_fail "Unexpected version output: $output"
      return 1
    fi
  else
    read -r installed rest <<< "$output"
  fi
  if [[ "$installed" != "$required" ]]; then
    check_fail "Installed $installed must match $required exactly."
    return 1
  fi
  echo "OK: $label $installed matches approved version $required."
}


check_fail() {
  echo "Error: $label: $*" >&2
  echo "$remedy Scripts are in $common_dir. Perform maintenance, then restart affected services and retry." >&2
}


fail() { echo "Error: $*" >&2; exit 1; }


main "$@"
