#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Download, build, and install CPython with modern openssl, readline, sqlite, and other dependencies.
# This script performs a regular Unix build on both macOS and Linux, instead of a framework build for macOS.

# Prerequisites:
# * Run common/build-sqlite.sh first to install a modern sqlite into /usr/local.
# * macOS: `brew install ca-certificates gdbm ncurses openssl pkg-config readline tcl-tk xz` then `brew upgrade`.
# * Linux: install the usual build toolchain and headers (clang, zlib, bzip2, xz, readline, gdbm, libffi, openssl).

# Run this as your normal (non-root) user. It escalates with sudo only to create the install prefix.
# The makefile compiles a large amount of stdlib bytecode during install;
# doing that under sudo produces root-owned files in both the install tree and the build tree.

# Optional configure arguments are passed through, e.g. --with-pydebug or --disable-optimizations.
# Pass -reuse-build as the first argument to skip the slow download, configure, and make steps
# and rerun only the install steps against the existing build tree; useful for iterating on install/symlink changes.

set -euo pipefail

source "$(dirname "$0")/../versions.sh"

py_version="${py_point_version%.*}"

fail() { echo "Error:" "$@" 1>&2; exit 1; }
exe() { echo "+ $*"; "$@"; }

[[ $EUID -ne 0 ]] || fail "Run this as your normal user, not root; the script escalates with sudo only where needed."


which pkg-config || {
  echo "Missing required tool."
  [[ $(uname) == "Darwin" ]]  && echo 'On macOS: `brew install gdbm gtk4 make openssl@3 readline pkg-config xz zstd`.'
  exit 1
}

reuse_build=0
if [[ "${1:-}" == '-reuse-build' ]]; then
  reuse_build=1
  shift
fi

# Warn if a newer point release exists; tolerate failure (offline, or no system python3 yet).
python3 "$(dirname "$0")/check-python-version.py" "$py_point_version" || true

prefix=/opt/py

case "$(uname)" in
  Darwin) platform=mac ;;
  Linux)  platform=linux ;;
  *) fail "Unsupported platform: $(uname)." ;;
esac
echo "platform: $platform; python: $py_point_version; prefix: $prefix."


# Install setup. This step happens early so that the sudo authorization is instant.

# Pre-create the prefix owned by us and group-writable, then run `make altinstall` as our normal user.
# This keeps root out of the bytecode compilation entirely, so nothing root-owned is produced.

install_group="${PY_INSTALL_GROUP:-$(
  if [[ $platform == mac ]]; then echo admin
  elif getent group operator >/dev/null 2>&1; then echo operator
  else id -gn; fi)}"
install_user="$(id -un)"
echo "install owner: $install_user:$install_group."

# Create install dir with sudo up front.

umask 022 # Set a conventional umask so that group/others can read/execute.

exe sudo mkdir -p "$prefix"
exe sudo chown "$install_user:$install_group" "$prefix"
exe sudo chmod 2775 "$prefix" # setgid so descendants inherit the group; group-writable for shared pip installs.

# Download, configure, and build, unless -reuse-build was passed.

cd "$(dirname "$0")/.." # The ops directory.
mkdir -p _build
cd _build

python_xz="Python-$py_point_version.tar.xz"
# Prerelease archives share the final release directory, e.g. 3.15.0/Python-3.15.0rc3.tar.xz.
py_release_version="${py_point_version%%[a-z]*}"
python_src_url="https://www.python.org/ftp/python/$py_release_version/$python_xz"
python_src_dir="Python-$py_point_version"

if [[ $reuse_build == 1 ]]; then
  [[ $# -eq 0 ]] || fail "-reuse-build: configure arguments are unused when reusing the existing build: $*."
  [[ -f "$python_src_dir/_build/Makefile" ]] || fail "-reuse-build: no existing build at ops/_build/$python_src_dir/_build."
  cd "$python_src_dir/_build"
  echo "reusing existing build: $PWD."
else

  # Download source.

  [[ -f "$python_xz" ]] || exe curl -fLO "$python_src_url"
  if [[ $platform == mac ]]; then
    echo "$py_sha256  $python_xz" | shasum -a 256 -c -
  else
    echo "$py_sha256  $python_xz" | sha256sum -c -
  fi

  # No sudo needed for cleanup: because we never install as root, the source tree is never littered with root-owned files.
  exe rm -rf "$python_src_dir"
  exe tar --xz -xf "$python_xz"
  [[ -d "$python_src_dir" ]] || fail "Missing Python source directory: $python_src_dir."

  cd "$python_src_dir"
  mkdir -p _build
  cd _build

  # Configure.

  export CC=clang
  export CXX=clang++

  cflags='-I/usr/local/include' # For locally built sqlite and anything else in /usr/local.
  ldflags='-L/usr/local/lib'

  configure_flags=(
    --prefix="$prefix"
    --cache-file=config.cache
    --with-pkg-config=yes
    --enable-loadable-sqlite-extensions
    --enable-optimizations
    --with-computed-gotos
    --with-lto
  )
  # Note: we explicitly specify computed gotos so that if the compiler does not support them, the build fails.
  # Doing so also makes it more obvious from sysconfig results that computed gotos are enabled.

  if [[ $platform == mac ]]; then
    # If MACOSX_DEPLOYMENT_TARGET is unset, the setup.py readline hack fails and libedit is used instead of readline.
    # We avoid libedit because it fails to display the 0xff UTF-8 character properly (NOTE: this may no longer be true).
    export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-15.1}"

    brew_path() { # package subpath.
      local pkg="$1"; shift
      local p; p="$(brew --prefix "$pkg")" || fail "brew --prefix $pkg failed."
      echo "$p/$*"
    }

    cflags+=' -Wstrict-prototypes -Wno-deprecated-declarations -Wno-unreachable-code' # Warning flags; these drift over time.
    cflags+=" -I$(brew_path gdbm include)"
    ldflags+=" -L$(brew_path gdbm lib)"
    cflags+=" -I$(brew_path tcl-tk include/tcl-tk)" # For tkinter.
    ldflags+=" -L$(brew_path tcl-tk lib)"           # For tkinter.

    # pkg-config paths provided by homebrew. We locate openssl via --with-openssl rather than pkg-config.
    export PKG_CONFIG_PATH="$(brew_path readline lib/pkgconfig):$(brew_path xz lib/pkgconfig)"

    configure_flags+=(
      --disable-framework
      --with-openssl="$(brew --prefix openssl@3)"
    )
    jobs=$(sysctl -n hw.logicalcpu)
  else
    # Linux: embed an rpath so the interpreter finds the locally built libraries (e.g. sqlite) at runtime.
    ldflags+=' -Wl,-rpath,/usr/local/lib'
    export LD=clang
    jobs=$(nproc)
  fi

  export CFLAGS="$cflags"
  export LDFLAGS="$ldflags"

  echo "CFLAGS: $CFLAGS"
  echo "LDFLAGS: $LDFLAGS"
  if [[ $platform == mac ]]; then
    echo "PKG_CONFIG_PATH: $PKG_CONFIG_PATH"
    echo "MACOSX_DEPLOYMENT_TARGET: $MACOSX_DEPLOYMENT_TARGET"
  fi

  exe ../configure "${configure_flags[@]}" "$@"

  # Build.

  exe make -j"$jobs"
  echo "Build done."
fi

echo

# Install.

# altinstall installs only the versioned executables (pythonX.Y, pipX.Y), not the `python3` symlink and manpage;
# we create the unversioned symlinks ourselves below. It also runs ensurepip, which refuses to run as root.
# Executables and pip-installed console scripts land in $prefix/bin on both platforms.

grep -Eq '^PYTHONFRAMEWORKDIR=[[:space:]]*no-framework[[:space:]]*$' Makefile ||
  fail "Framework builds are no longer supported. Rebuild without -reuse-build or --enable-framework."

bin_dir="$prefix/bin"

# Remove the old framework bin symlink before installing, preserving the framework and its installed packages.
if [[ -L "$bin_dir" ]]; then
  case "$(readlink "$bin_dir")" in
    Python.framework/Versions/*/bin|"$prefix"/Python.framework/Versions/*/bin) exe unlink "$bin_dir" ;;
    *) fail "Unexpected bin directory symlink: $bin_dir. Remove it before installing." ;;
  esac
fi
exe make altinstall
echo "Altinstall done."
echo

[[ -x "$bin_dir/python$py_version" ]] || fail "Expected altinstall executable missing: $bin_dir/python$py_version."

# Add the unversioned `python`/`python3` names alongside the versioned one from altinstall.
# The targets are relative because each unversioned name sits in the same dir as its versioned target.
for name in python python3; do
  exe ln -sf "python$py_version" "$bin_dir/$name"
done

# pip. altinstall runs ensurepip, but ensurepip installs nothing when site-packages already holds an equal or newer pip
# (e.g. when rebuilding over an existing prefix), in which case no pip scripts are written to the bin dir.
# Upgrading pip normally regenerates them (pip special-cases installing itself to emit `pip`, `pip3`, and `pip3.X`),
# but that too is a no-op when the installed pip is already the latest, so force-reinstall if any script is still missing.
py_versioned="$bin_dir/python$py_version"
exe "$py_versioned" -m pip install --upgrade pip
if [[ ! -x "$bin_dir/pip" || ! -x "$bin_dir/pip3" || ! -x "$bin_dir/pip$py_version" ]]; then
  exe "$py_versioned" -m pip install --force-reinstall pip
fi
for name in pip pip3 "pip$py_version"; do
  [[ -x "$bin_dir/$name" ]] || fail "Expected pip executable missing: $bin_dir/$name."
done

hash -r # Refresh the shell's command hash so the new python is found.

# Permissions for sudo-less pip.

# Make the whole installation group-writable so any member of $install_group can pip install without sudo.
# We own everything because we ran altinstall ran as us, so no sudo is needed here.
# Use g+rwX so directories and existing executables get the execute bit but plain data files do not.
exe chgrp -R "$install_group" "$prefix"
exe chmod -R g+rwX "$prefix"

py="$prefix/bin/python3"

# Verify.

check_import() {
  local out
  if out="$("$py" -c "$1" 2>&1)"; then
    echo "ok:   $2${out:+ - $out}"
  else
    echo "NOTE: $2 unavailable."
  fi
}

echo
echo "verifying modules:"
check_import 'import lzma' 'lzma (xz)'
check_import 'import readline; print("backend:", readline.backend)' 'readline'
check_import 'import ssl; print(ssl.OPENSSL_VERSION)' 'ssl (openssl)'
check_import 'import sqlite3; print(sqlite3.sqlite_version)' 'sqlite3'
check_import 'import dbm.gnu' 'dbm.gnu (gdbm)'
check_import 'import tkinter; print("tk", tkinter.TkVersion)' 'tkinter'

case ":$PATH:" in
  *":$prefix/bin:"*) echo "PATH contains $prefix/bin." ;;
  *) echo "NOTE: PATH does not contain $prefix/bin; add it before /usr/bin so this python3 overrides the system one." ;;
esac

echo
which_check() {
  local out
  if out="$(which "$1" 2>&1)"; then
    if [[ "$out" == "$prefix/bin/$1" ]]; then echo "ok:   which $1 -> $out"
    else echo "NOTE: which $1 -> $out (expected $prefix/bin/$1)."
    fi
  else
    echo "NOTE: which $1 found nothing."
  fi
}
which_check python
which_check pip

echo
echo "Done. Python $py_point_version installed to $prefix."
