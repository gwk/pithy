#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail

function fail() { echo "$1" >&2; exit 1; }

src_dir=$(dirname $0)
cd "$src_dir"

source ./version.sh

machine_arch=$(uname -m)

case "${machine_arch}" in
  "x86_64"|"amd64")
    uv_arch="x86_64"
    uv_sha256="$uv_sha256_x86_64" ;;
  "aarch64"|"arm64")
    uv_arch="aarch64"
    uv_sha256="$uv_sha256_aarch64" ;;
  *)
    fail "Unsupported architecture: ${machine_arch}" ;;
esac

set -x

uv_dl_dir="uv-${uv_arch}-unknown-linux-gnu"
uv_dl_name="${uv_dl_dir}.tar.gz"
uv_dl_url="https://github.com/astral-sh/uv/releases/download/${uv_version}/${uv_dl_name}"

mkdir -p download
rm -rf download/*

curl -L -o "download/${uv_dl_name}" "${uv_dl_url}"

echo "${uv_sha256}  download/${uv_dl_name}" | sha256sum -c -

tar -xzf "download/${uv_dl_name}" -C download

sudo install "download/${uv_dl_dir}/uv" "download/${uv_dl_dir}/uvx" /usr/local/bin

uv --version
