#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail
shopt -s extglob # For the prune pattern below.

function fail() { echo "$1" >&2; exit 1; }

src_dir=$(dirname "$0")
cd "$src_dir"

source ../versions.sh

machine_os=$(uname -s)
machine_arch=$(uname -m)

case "${machine_os}/${machine_arch}" in
  Linux/aarch64|Linux/arm64)
    vector_target="aarch64-unknown-linux-gnu"
    vector_sha256="$vector_sha256_linux_aarch64" ;;
  Linux/x86_64|Linux/amd64)
    vector_target="x86_64-unknown-linux-gnu"
    vector_sha256="$vector_sha256_linux_x86_64" ;;
  Darwin/aarch64|Darwin/arm64)
    vector_target="arm64-apple-darwin"
    vector_sha256="$vector_sha256_macos_arm64" ;;
  *)
    fail "Unsupported Vector platform: ${machine_os}/${machine_arch}" ;;
esac

set -x

cd .. # The ops directory.
mkdir -p _build
cd _build

vector_dl_name="vector-${vector_version}-${vector_target}.tar.gz"
vector_dl_dir="vector-${vector_target}"

# Remove other versions and any previous extraction of this one, keeping only the current archive.
rm -rf vector-!("${vector_dl_name#vector-}")

[[ -f "$vector_dl_name" ]] || curl --proto '=https' --tlsv1.2 -sSfLO \
  "https://github.com/vectordotdev/vector/releases/download/v${vector_version}/${vector_dl_name}"
if [[ "$machine_os" == Darwin ]]; then
  echo "${vector_sha256}  ${vector_dl_name}" | shasum -a 256 -c -
else
  echo "${vector_sha256}  ${vector_dl_name}" | sha256sum -c -
fi

tar -xzf "${vector_dl_name}"
[[ -d "$vector_dl_dir" ]] || fail "Missing Vector directory: $vector_dl_dir."

[[ -d /usr/local/bin ]] || sudo mkdir -p /usr/local/bin
sudo install "${vector_dl_dir}/bin/vector" /usr/local/bin
