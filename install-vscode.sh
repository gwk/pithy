#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -eux

VSCODE_PLUMAGE="$HOME/.vscode-insiders/extensions/plumage"

rm -rf "$VSCODE_PLUMAGE"/*

mkdir -p "$VSCODE_PLUMAGE"

cp vscode/package.json "$VSCODE_PLUMAGE"
