#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail

function fail() { echo "$1" >&2; exit 1; }

src_dir=$(dirname $0)
cd "$src_dir"

machine_arch=$(uname -m)
vector_version='0.57.0'

case "${machine_arch}" in
  "x86_64"|"amd64")
    vector_arch="x86_64"
    vector_sha256='4d156e6859e235b366f5b77121ae59d5440c93acab215c45f30f3fc839d20f65' ;;
  "aarch64"|"arm64")
    vector_arch="aarch64"
    vector_sha256='6290f6fae406b61272cdf849e9cc9fa015761efbb592d2359d86ec4345d10aa3' ;;
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
