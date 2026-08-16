#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Check whether the uv version pinned in version.sh is the latest release.
# If a newer release exists, print updated values for version.sh to stdout.
# The checksums come from the sha256 digests in the GitHub release asset metadata.
# This is primarily run on the dev machine; it requires curl and jq.

set -euo pipefail

function fail() { echo "$1" >&2; exit 1; }

src_dir=$(dirname "$0")
cd "$src_dir"

source ./version.sh

release_json=$(curl -sSf https://api.github.com/repos/astral-sh/uv/releases/latest)
latest=$(jq -r '.tag_name' <<<"$release_json")
[[ -n "$latest" && "$latest" != "null" ]] || fail "Could not determine the latest uv release."

if [[ "$latest" == "$uv_version" ]]; then
  echo "uv $uv_version is the latest release."
  exit 0
fi

function asset_sha256() {
  local name="uv-$1-unknown-linux-gnu.tar.gz"
  local digest
  digest=$(jq -r --arg name "$name" '.assets[] | select(.name == $name) | .digest' <<<"$release_json")
  [[ "$digest" == sha256:* ]] || fail "Missing or malformed digest for asset $name: ${digest@Q}."
  echo "${digest#sha256:}"
}

sha256_x86_64=$(asset_sha256 x86_64)
sha256_aarch64=$(asset_sha256 aarch64)

echo "Pinned uv $uv_version is outdated; the latest release is $latest. Updated values for version.sh:" >&2
echo "uv_version=\"$latest\""
echo "uv_sha256_x86_64=\"$sha256_x86_64\""
echo "uv_sha256_aarch64=\"$sha256_aarch64\""
