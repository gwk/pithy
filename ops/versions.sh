# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Approved releases. Keep declarations literal so both Bash and tap_ops.releases can read this file.
# Review new releases with: python3 -m tap_ops.releases -versions ops/versions.sh
# Update each release's version and archive checksums together after review and testing.
# SQLite also needs its release year in the archive path. Checksums are for the downloaded archives.

py_point_version="3.14.7"
py_sha256='3b48dac8fb59f62eaa67ac83c1eb12bda1b7a08406dd286e252c11a66be27f81'

sqlite_version='3.53.4'
sqlite_zip_remote_path='2026/sqlite-src-3530400.zip'
sqlite_sha3='b834d474b9b393d85a9e3ee4cc11f1329e007e9376a424ee740796f5c4bda3a8'

uv_version="0.12.19"
uv_sha256_linux_x86_64="23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8"
uv_sha256_linux_aarch64="0804e9b164c64b6914182d5920c08551958a095986f10a3731056df701126436"

vector_version='0.58.0'
vector_sha256_linux_aarch64='06d9f9768feb0cb5c7cdfc12e0b737b22f1220967f5455f391a395361b5799e5'
vector_sha256_linux_x86_64='a4634bea859a7ad7064ff3dd6f6ad7eb0e8dd4493cc41657d84da8dd66f09d09'
vector_sha256_macos_arm64='9182491597f1bdedb08d84a051616c62deea770a9d905b697712cc6526919449'
