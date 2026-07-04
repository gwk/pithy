#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Fetch standard JSON benchmark/conformance data into perf/pithy/json/fmt/data.
# Sources:
# * nativejson-benchmark: the de facto standard perf trio (canada, citm_catalog, twitter).
# * sajson testdata: assorted real-world API-response shapes.
# * JSONTestSuite: conformance edge cases, for future correctness testing.

set -euo pipefail

[[ -z "${EXTERNAL_DIR:-}" ]] && EXTERNAL_DIR=~/external

external_dir=$(realpath "$EXTERNAL_DIR")
proj_dir=$(realpath "$0"/../..)

cd "$external_dir"

if [[ -d nativejson-benchmark ]]; then
  (cd nativejson-benchmark && git pull)
else
  git clone https://github.com/miloyip/nativejson-benchmark
fi

if [[ -d sajson ]]; then
  (cd sajson && git pull)
else
  git clone https://github.com/chadaustin/sajson
fi

if [[ -d JSONTestSuite ]]; then
  (cd JSONTestSuite && git pull)
else
  git clone https://github.com/nst/JSONTestSuite
fi

cd "$proj_dir"

data_dir=perf/pithy/json/fmt/data

mkdir -p "$data_dir/nativejson-benchmark" "$data_dir/sajson" "$data_dir/JSONTestSuite"

cp "$external_dir/nativejson-benchmark/data/canada.json" \
   "$external_dir/nativejson-benchmark/data/citm_catalog.json" \
   "$external_dir/nativejson-benchmark/data/twitter.json" \
   "$data_dir/nativejson-benchmark/"

cp "$external_dir"/sajson/testdata/*.json "$data_dir/sajson/"

cp -R "$external_dir/JSONTestSuite/test_parsing" "$external_dir/JSONTestSuite/test_transform" "$data_dir/JSONTestSuite/"

echo "Updated $data_dir:"
du -sh "$data_dir"/*
