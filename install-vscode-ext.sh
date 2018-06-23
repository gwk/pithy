#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -eux

VSCODE_EXT="$HOME/.vscode-insiders/extensions/craft"

rm -rf "$VSCODE_EXT"
mkdir -p "$VSCODE_EXT"
cp vscode/package.json "$VSCODE_EXT"
