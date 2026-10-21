# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Approved releases. Keep declarations literal so both Bash and tap_ops.releases can read this file.
# Review new releases with: python3 -m tap_ops.releases -versions ops/versions.sh
# Update each release's version and archive checksums together after review and testing.
# SQLite also needs its release year in the archive path. Checksums are for the downloaded archives.

# Python versions omit the git tag prefix v; prerelease suffixes aN, bN and rcN are supported.
py_point_version="3.15.1"
py_sha256='673ae7232d84c894729882c8257d300ef2d26523911bfd3917ec8ce7f526f99b'

sqlite_version='3.54.1'
sqlite_zip_remote_path='2026/sqlite-src-3540100.zip'
sqlite_sha3='877c6f4996ce7adb368686bce21638de9e3d91534832ad3d9d119037d1bc22ad'

uv_version="0.13.4"
uv_sha256_linux_x86_64="2b428396f12572d4429cf210ca234dd599a33b3af0958a4d5ed569d63e3f344f"
uv_sha256_linux_aarch64="1ae72b4718729e2ccc4f1ae2c6d1e531ca8467800e0546e9130b3886023a60ab"
uv_sha256_macos_arm64="e0b1d4743ce64c55d9f0f4a444afa6b81125680070ee04e853fcd0f6c1ebf8f1"
uv_sha256_macos_x86_64="7be2dcd316122f4b3e5a0a7889f6248266c14425374e105ff7dc9779184603a6"

vector_version='0.60.0'
vector_sha256_linux_aarch64='1540662d8bc33af5afd287f821ba930417e0f3124073bc9db6a29c59dda88dbb'
vector_sha256_linux_x86_64='89a9f134dcc35a6fbba9cb8ad0fec2d4802657bba6cb1c374a30660ef9456bdc'
vector_sha256_macos_arm64='aa5c9d89416b39f1a90a7f1a088a9ecbb8c8c3a5669fb86609c9d4a958fe1a28'
