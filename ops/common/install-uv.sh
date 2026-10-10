#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Install the approved uv release on macOS or Linux into /opt/uv/bin.
# Downloads and verification run as the invoking user; sudo installs root-owned, shared binaries.
# Rerun after updating versions.sh to upgrade. No shell startup files are edited.
# The archive and extracted files stay in ops/_build for inspection; the next run replaces them.

set -euo pipefail

fail() { echo "Error:" "$@" >&2; exit 1; }

[[ $# -eq 0 ]] || fail 'Usage: install-uv.sh'
prefix=/opt/uv
for path in "$prefix" "$prefix/bin" "$prefix/bin/uv" "$prefix/bin/uvx"; do
  [[ ! -L "$path" ]] || fail "Install path must not be a symlink: $path."
done

cd "$(dirname "$0")/.." # The ops directory.
source versions.sh
mkdir -p _build
cd _build

machine_os=$(uname -s)
machine_arch=$(uname -m)

case "${machine_os}/${machine_arch}" in
  Linux/x86_64|Linux/amd64)
    uv_target="x86_64-unknown-linux-gnu"
    uv_sha256="$uv_sha256_linux_x86_64" ;;
  Linux/aarch64|Linux/arm64)
    uv_target="aarch64-unknown-linux-gnu"
    uv_sha256="$uv_sha256_linux_aarch64" ;;
  Darwin/aarch64|Darwin/arm64)
    uv_target="aarch64-apple-darwin"
    uv_sha256="$uv_sha256_macos_arm64" ;;
  Darwin/x86_64)
    uv_target="x86_64-apple-darwin"
    uv_sha256="$uv_sha256_macos_x86_64" ;;
  *)
    fail "Unsupported uv platform: ${machine_os}/${machine_arch}." ;;
esac

uv_dl_dir="uv-${uv_target}"
uv_dl_name="${uv_dl_dir}.tar.gz"
uv_dl_url="https://github.com/astral-sh/uv/releases/download/${uv_version}/${uv_dl_name}"

[[ -f "$uv_dl_name" ]] || curl --proto '=https' --tlsv1.2 -fsSL -o "$uv_dl_name" "$uv_dl_url"

if [[ "$machine_os" == Darwin ]]; then
  echo "${uv_sha256}  ${uv_dl_name}" | shasum -a 256 -c -
else
  echo "${uv_sha256}  ${uv_dl_name}" | sha256sum -c -
fi

rm -rf "$uv_dl_dir"
tar -xzf "$uv_dl_name"
[[ -d "$uv_dl_dir" ]] || fail "Missing uv directory: $uv_dl_dir."
"$uv_dl_dir/uv" --version

sudo install -d -o root -m 755 "$prefix" "$prefix/bin"
sudo install -o root -m 755 "$uv_dl_dir/uv" "$uv_dl_dir/uvx" "$prefix/bin"
"$prefix/bin/uv" --version

printf '\nAdd to your shell profile and agent environment:\nexport PATH="%s/bin:$PATH"\n' "$prefix"
active_uv=$(command -v uv || true)
if [[ "$active_uv" != "$prefix/bin/uv" ]]; then
  printf '\nCurrent PATH resolves uv to: %s\n' "${active_uv:-not found}"
  echo "Ensure $prefix/bin takes precedence, and remove the previous installation after verifying this one."
fi
