# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Approved releases. Keep declarations literal so both Bash and tap_ops.releases can read this file.
# Review new releases with: python3 -m tap_ops.releases -versions ops/versions.sh
# Update each release's version and archive checksums together after review and testing.
# SQLite also needs its release year in the archive path. Checksums are for the downloaded archives.

# Python versions omit the git tag prefix v; prerelease suffixes aN, bN and rcN are supported.
py_point_version="3.15.0"
py_sha256='ba4bed1ba346b916890b76d9e320451420aa69f6408997d33c66482eeae3d575'

sqlite_version='3.54.0'
sqlite_zip_remote_path='2026/sqlite-src-3540000.zip'
sqlite_sha3='a5c29342ca185abcda332448fbb27c536661245be27e20199b46c49099b0e15e'

uv_version="0.13.0"
uv_sha256_linux_x86_64="1468ebd5a5541121837c5a2817b9972ba6090fa6caa3d142620850a47fb75154"
uv_sha256_linux_aarch64="3ccfb6af6e242433eb552f7d9676abd5412c6595c497e990d9c8cb7b5bd4d2c3"
uv_sha256_macos_arm64="a9c1b29002cf3c83f07fa9cd8a887a3be0107d90e23189721221e7257db8e3d6"
uv_sha256_macos_x86_64="5f44dcbde809b632f47c36fadb241cb4d6f9af71d0c8f172b5d2026d3dde742c"

vector_version='0.59.0'
vector_sha256_linux_aarch64='644f4db7d158b8ceaed05427599d0706ca59428b263fed985232d379ff89ca46'
vector_sha256_linux_x86_64='fb15878d1cd68445e0658792a8fa7ccf02ae8a353c6cc5d6fe867b171993e19f'
vector_sha256_macos_arm64='6f0cd290c90ea2cfc7cb3c10eca32fc897f0b958b60d48ad2867a91d5585363c'
