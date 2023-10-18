# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
import sys


def add_homebrew_to_dyld_paths() -> None:
  '''
  Inject the macOS (Apple Silicon) homebrew paths into the dyld paths.
  TODO: support Intel macs and linuxbrew.
  '''

  if os.name == "posix" and sys.platform == "darwin": # macOS.

    from ctypes.macholib.dyld import DEFAULT_FRAMEWORK_FALLBACK, DEFAULT_LIBRARY_FALLBACK  # type: ignore[import-not-found]

    # Insert the homebrew path after the user home path, but before the system paths.
    DEFAULT_FRAMEWORK_FALLBACK.insert(1, '/opt/homebrew/frameworks')

    # Insert the homebrew path /usr/local/lib, which as of python3.11 comes after ~/lib.
    usr_local_idx = DEFAULT_LIBRARY_FALLBACK.index('/usr/local/lib')
    DEFAULT_LIBRARY_FALLBACK.insert(usr_local_idx+1, '/opt/homebrew/lib')
