#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail

function fail { echo "error: $*" >&2; exit 1; }

[[ $# -ge 2 && $# -le 3 ]] || fail "usage: $0 {test|prod} package [-republish]"
stage="$1"
package="$2"
shift 2
[[ $# -eq 0 || "$1" == '-republish' ]] || fail "unknown option: $1"

case "$stage" in
  test) registry='https://test.pypi.org'; publish_url='https://test.pypi.org/legacy/'; check_url='https://test.pypi.org/simple/' ;;
  prod) registry='https://pypi.org'; publish_url='https://upload.pypi.org/legacy/'; check_url='https://pypi.org/simple/' ;;
  *) fail "unknown stage: $stage" ;;
esac

[[ "$package" =~ ^[a-z][a-z0-9_]*$ ]] || fail "invalid package name: $package"

cd "$(dirname "$0")/.."
version=$(python3 -I sh/extract-version.py "$package")
# Require a version bump unless explicitly republishing the latest release.
python3 sh/check-publish.py "$registry" "$package" "$version" "$@"

# A pure Python wheel is always named `py3-none-any`, but the tags of a native wheel depend on the build, so find it by glob.
# Remove this version's previous distributions first, so that the glob cannot match a wheel left by an earlier build.
sdist="${package}_/dist/${package}-${version}.tar.gz"
rm -f "$sdist" "${package}_/dist/${package}-${version}-"*.whl
sh/build.sh "$package"

wheels=("${package}_/dist/${package}-${version}-"*.whl)
[[ ${#wheels[@]} -eq 1 ]] || fail "expected one wheel for $package $version; found: ${wheels[*]}"
files=("$sdist" "${wheels[0]}")
for file in "${files[@]}"; do
  [[ -f "$file" ]] || fail "missing distribution: $file"
done

# Let uv use the invoking user's native-auth configuration and stored credentials.
unset UV_PUBLISH_TOKEN UV_PUBLISH_PASSWORD UV_PUBLISH_USERNAME UV_PUBLISH_URL UV_PUBLISH_INDEX UV_PUBLISH_CHECK_URL
exec uv publish --username __token__ --trusted-publishing never \
  --publish-url "$publish_url" --check-url "$check_url" "${files[@]}"
