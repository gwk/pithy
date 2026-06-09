set -eux

cd "$(dirname $0)/.."
mkdir -p _build
cd _build
python -m inish.github download-release toml-lang/toml-test -assets 'toml-test-v.*-darwin-arm64\.gz'
gunzip -c toml-test-v*.gz > toml-test
chmod +x toml-test
cd ..
mkdir -p tomul_/test/toml-test-data
_build/toml-test copy -toml 1.0 tomul_/test/toml-test-data
