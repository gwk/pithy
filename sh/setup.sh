#!/usr/bin/env bash

set -e

function fail { echo "$0: error: $@" 1>&2; exit 1; }

script_dir=$(dirname "$0")

[[ "$script_dir" == "sh" ]] || fail 'script must be executed from the repository root directory.'

package="$1"
[[ -n "$package" ]] || fail 'empty package name.'
[[ "$package" == *' '* ]] && fail 'package name contains space.'

echo
echo '--------------------------------'
echo "package: $package"
cp "$package/setup.cfg" setup.cfg
