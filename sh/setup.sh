#!/usr/bin/env bash

set -e

script_path="$0"
script_dir=$(dirname "$script_path")

function fail { echo "$script_path: error: $@" 1>&2; exit 1; }

[[ "$script_dir" == "sh" ]] || fail 'script must be executed from the repository root directory.'

package="$1"
[[ -n "$package" ]] || fail 'empty package name.'
[[ "$package" == *' '* ]] && fail 'package name contains space.'

echo
echo '--------------------------------'
echo "package: $package"
cp "$package/setup.cfg" setup.cfg
