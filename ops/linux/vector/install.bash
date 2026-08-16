#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail

function fail() { echo "$1" >&2; exit 1; }

src_dir=$(dirname $0)
cd "$src_dir"

machine_arch=$(uname -m)
vector_version='0.55.0'

case "${machine_arch}" in
  "x86_64"|"amd64")
    vector_arch="x86_64"
    vector_sha256='e0221681b1cd1f93c46008fde19c5ac5811718d10a803a4e320ff4e72ab9e4a9' ;;
  "aarch64"|"arm64")
    vector_arch="aarch64"
    vector_sha256='00ce049bd42291165eb207b413e9fa8afacacf2e8ac4312e7dc89488a6ec4e4c' ;;
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
