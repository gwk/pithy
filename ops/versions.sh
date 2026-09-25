# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Approved releases. Keep declarations literal so both Bash and tap_ops.releases can read this file.
# Review new releases with: python3 -m tap_ops.releases -versions ops/versions.sh
# Update each release's version and archive checksums together after review and testing.
# SQLite also needs its release year in the archive path. Checksums are for the downloaded archives.

py_point_version="3.14.7"

sqlite_version='3.53.3'
sqlite_zip_remote_path='2026/sqlite-src-3530300.zip'
sqlite_sha3='2daecfa16e3b19e058dc2e2cb717b80ade361e0315aa5376c3619f66aa81e181'

vector_version='0.58.0'
vector_sha256_aarch64='06d9f9768feb0cb5c7cdfc12e0b737b22f1220967f5455f391a395361b5799e5'
vector_sha256_x86_64='a4634bea859a7ad7064ff3dd6f6ad7eb0e8dd4493cc41657d84da8dd66f09d09'

uv_version="0.11.31"
uv_sha256_x86_64="8cc1cd82d434ec565376f98bd938d4b715b5791a80ff2d3aa78821cf85091b4b"
uv_sha256_aarch64="d74f23949fd07be4970f293d06ca99d87cd2a78a341c3d7b7fc0df7bc2d8a145"
