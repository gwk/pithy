set -eux

toml_test_version='2.2.0'
toml_test_sha256='f36b1310b03a95dfa6b92ef535018db8ccc997ba20e79f3fd28d0f97c9174f35'
toml_test_archive="toml-test-v${toml_test_version}-darwin-arm64.gz"

cd "$(dirname $0)/.."
mkdir -p _build
cd _build
curl --proto '=https' --tlsv1.2 -sSfLO \
  "https://github.com/toml-lang/toml-test/releases/download/v${toml_test_version}/${toml_test_archive}"
echo "${toml_test_sha256}  ${toml_test_archive}" | shasum -a 256 -c -
gunzip -c "${toml_test_archive}" > toml-test
chmod +x toml-test
cd ..
mkdir -p tomul_/test/toml-test-data
_build/toml-test copy -toml 1.0 tomul_/test/toml-test-data
