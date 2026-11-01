# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Approved releases. Keep declarations literal so both Bash and tap_ops.releases can read this file.
# Review new releases with: python3 -m tap_ops.releases -versions ops/versions.sh
# Update each release's version and archive checksums together after review and testing.
# SQLite also needs its release year in the archive path. Checksums are for the downloaded archives.

# Python versions omit the git tag prefix v; prerelease suffixes aN, bN and rcN are supported.
py_point_version="3.15.2"
py_sha256='8b5536d280142ecf6cdfe15d12a21ba1c65e300bbf7b28a8d0cdb849575797de'

sqlite_version='3.54.1'
sqlite_zip_remote_path='2026/sqlite-src-3540100.zip'
sqlite_sha3='877c6f4996ce7adb368686bce21638de9e3d91534832ad3d9d119037d1bc22ad'

uv_version="0.13.6"
uv_sha256_linux_x86_64="f29c3e94ffabd7e6f3ba521dba169a9b7ec12100bf3257087f0f24f6123f3645"
uv_sha256_linux_aarch64="229e194255c7958d86d56e8790d969a6f74736592133f0dfd0076f754c642c1d"
uv_sha256_macos_arm64="60fbd5c8a1ed681845eea28d9d622fcde03c51e91a43465b64a1e17db1ed3472"
uv_sha256_macos_x86_64="63ba17fdda55ad1a230d4b37fc6017ffa10c23688c83818bd3bfdf914c652a02"

vector_version='0.61.0'
vector_sha256_linux_aarch64='4f6e3093c0963611c8e31478137adca07920e729bdcc734d4ba7ab6f948a7e9f'
vector_sha256_linux_x86_64='84a27c3ad6b772fdb05bb76ea01a31498bfc8f5e71f32cc78a0d96841f1aa827'
vector_sha256_macos_arm64='5e747594bb12c8d9ab85c16f2fb5e9fa35bc92911e17099a9721f7d833ae3503'
