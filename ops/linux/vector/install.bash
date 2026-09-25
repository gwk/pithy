#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail

function fail() { echo "$1" >&2; exit 1; }

src_dir=$(dirname $0)
cd "$src_dir"

source ../../versions.sh

machine_arch=$(uname -m)

case "${machine_arch}" in
  "aarch64"|"arm64")
    vector_arch="aarch64"
    vector_sha256="$vector_sha256_aarch64" ;;
  "x86_64"|"amd64")
    vector_arch="x86_64"
    vector_sha256="$vector_sha256_x86_64" ;;
  *)
    fail "Unsupported architecture: ${machine_arch}" ;;
esac

set -x

mkdir -p download
cd download

# TODO: support platforms other than Linux.

vector_dl_name="vector-${vector_version}-${vector_arch}-unknown-linux-gnu.tar.gz"
curl --proto '=https' --tlsv1.2 -sSfLO \
  "https://github.com/vectordotdev/vector/releases/download/v${vector_version}/${vector_dl_name}"
echo "${vector_sha256}  ${vector_dl_name}" | sha256sum -c -

tar -xzf "${vector_dl_name}"

vector_dl_dir="vector-${vector_arch}-unknown-linux-gnu"
sudo install "${vector_dl_dir}/bin/vector" /usr/local/bin
