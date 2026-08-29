#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail

function fail() { echo "$1" >&2; exit 1; }

src_dir=$(dirname $0)
cd "$src_dir"

machine_arch=$(uname -m)
vector_version='0.58.0'

case "${machine_arch}" in
  "aarch64"|"arm64")
    vector_arch="aarch64"
    vector_sha256='06d9f9768feb0cb5c7cdfc12e0b737b22f1220967f5455f391a395361b5799e5' ;;
  "x86_64"|"amd64")
    vector_arch="x86_64"
    vector_sha256='a4634bea859a7ad7064ff3dd6f6ad7eb0e8dd4493cc41657d84da8dd66f09d09' ;;
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
