#!/usr/bin/env bash

set -e

if [[ "$1" == "-live" ]]; then
  echo "*** LIVE ***"
  shift
  url="https://upload.pypi.org/legacy/"
else
  echo "TEST"
  url="https://test.pypi.org/legacy/"
fi


for package in "$@"; do
  echo
  echo '--------------------------------'
  echo "package: $package"
  set -x
	twine upload --repository-url "$url" _build/dist/$package-*
  set +x
done
